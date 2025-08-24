# graph_pipe.py
import os
import re
import json
import argparse
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "chunk_embeddings")
VECTOR_NODE_LABEL = "Chunk"
VECTOR_PROPERTY_KEY = "embedding"
VECTOR_DIMENSIONS = int(os.getenv("VECTOR_DIMENSIONS", "768"))

class Neo4jUploader:
    def __init__(self, uri, user, password, database):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def upload_data(self, df: pd.DataFrame, batch_size=500):
        with self.driver.session(database=self.database) as s:
            self._ensure_vector_index(s)
            records = df.to_dict("records")
            print(f"[INFO] Uploading {len(records)} rows in batches of {batch_size} ...")
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                try:
                    s.execute_write(self._upload_batch, batch)
                    print(f"[INFO] Batch {(i//batch_size)+1}/{(len(records)+batch_size-1)//batch_size} uploaded.")
                except Exception as e:
                    print(f"[ERROR] Batch {(i//batch_size)+1} failed: {e}")

    def _ensure_vector_index(self, session):
        res = session.run("SHOW INDEXES YIELD name WHERE name = $name", name=VECTOR_INDEX_NAME)
        if res.single():
            print(f"[INFO] Vector index '{VECTOR_INDEX_NAME}' exists.")
            return
        print(f"[INFO] Creating vector index '{VECTOR_INDEX_NAME}' ...")
        q = f"""
        CREATE VECTOR INDEX `{VECTOR_INDEX_NAME}`
        FOR (c:{VECTOR_NODE_LABEL}) ON (c.{VECTOR_PROPERTY_KEY})
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: {VECTOR_DIMENSIONS},
            `vector.similarity_function`: 'cosine'
          }}
        }}
        """
        session.run(q).consume()
        print("[INFO] Vector index created.")

    @staticmethod
    def _sanitize_rel_type(t: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]+", "_", (t or "RELATED_TO").upper())

    @staticmethod
    def _upload_batch(tx, records):
        # Pre-parse JSON and sanitize
        for r in records:
            r["metadata"] = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {})
            gd = json.loads(r["graph_data"]) if isinstance(r["graph_data"], str) else (r["graph_data"] or {})
            if not isinstance(gd, dict):
                gd = {"entities": [], "relationships": []}
            for rel in gd.get("relationships", []):
                rel["type"] = Neo4jUploader._sanitize_rel_type(rel.get("type", "RELATED_TO"))
            r["graph_data_raw"] = json.dumps(gd)  # serialize for Cypher
            r["graph_data"] = gd                  # still needed for Entity processing


        # Paper + Chunk + Entity + MENTIONS 
        cypher = """
        UNWIND $batch AS row
        WITH row
        MERGE (p:Paper {id: row.paper_id})
          ON CREATE SET
            p.title = row.metadata.title,
            p.published = row.metadata.published,
            p.pdf_url = coalesce(row.metadata.pdf_url, "")
        MERGE (c:Chunk {id: row.chunk_id})
            ON CREATE SET
                c.text = row.chunk_text,
                c.embedding = row.embedding,
                c.graph_data = row.graph_data_raw
            ON MATCH SET
                c.text = coalesce(c.text, row.chunk_text),
                c.graph_data = coalesce(c.graph_data, row.graph_data_raw)

        MERGE (p)-[:HAS_CHUNK]->(c)

        WITH row, c
        FOREACH (e IN coalesce(row.graph_data.entities, []) |
          MERGE (ent:Entity {name: e.name})
            ON CREATE SET ent.type = e.type
          MERGE (c)-[:MENTIONS]->(ent)
        )
        """
        tx.run(cypher, batch=records)

        # entity-entity relationships
        for r in records:
            rels = r["graph_data"].get("relationships", [])
            for rel in rels:
                if not (rel.get("source") and rel.get("target") and rel.get("type")):
                    continue
                cy = f"""
                MATCH (s:Entity {{name: $sname}})
                MATCH (t:Entity {{name: $tname}})
                MERGE (s)-[:`{rel['type']}`]->(t)
                """
                tx.run(cy, sname=rel["source"], tname=rel["target"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Parquet path produced by spark_processor.py")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"[ERROR] Parquet not found: {args.path}")
        return

    print(f"[INFO] Reading {args.path}")
    df = pd.read_parquet(args.path)

    up = Neo4jUploader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    try:
        up.upload_data(df)
        print("[INFO] Upload complete.")
    finally:
        up.close()

if __name__ == "__main__":
    main()