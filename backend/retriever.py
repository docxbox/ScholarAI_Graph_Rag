# retriever.py
import os
import json
import time
import argparse
import requests
from typing import Iterable, List
import textwrap

from neo4j import GraphDatabase
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

load_dotenv()
CURRENT_DATE_TIME = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# --- Vector index ---
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "chunk_embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5")

# --- LLM selection ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Ollama
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")

# OpenRouter
from openai import OpenAI
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
YOUR_SITE_URL = os.getenv("YOUR_SITE_URL", "")
YOUR_SITE_NAME = os.getenv("YOUR_SITE_NAME", "")
with open("Prompt_template/prompt.txt", "r") as f:
    RAG_PROMPT = f.read()



class GraphRetriever:
    def __init__(self, uri, user, password, database):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)

    def close(self):
        self.driver.close()

    #Vector search
    def get_query_embedding(self, query: str) -> List[float]:
        emb = self.embedder.embed_query(query)
        return [float(x) for x in emb]

    def vector_search(self, query_embedding: List[float], top_k=5) -> List[str]:
        with self.driver.session(database=self.database) as s:
            res = s.run(
                """
                CALL db.index.vector.queryNodes($index, $k, $q)
                YIELD node, score
                RETURN node.id AS chunk_id
                """,
                index=VECTOR_INDEX_NAME, k=top_k, q=query_embedding
            )
            return [r["chunk_id"] for r in res]

    # Graph expansion 
    def graph_expansion(self, chunk_ids: List[str], depth=2):
        """
        Expand from the seed chunks via MENTIONS / HAS_CHUNK up to 'depth'.
        Returns distinct (paper, chunk) pairs and optional properties.
        """
        with self.driver.session(database=self.database) as s:
            res = s.run(
                f"""
                UNWIND $ids AS cid
                MATCH (c:Chunk {{id: cid}})
                // expand without subquery to avoid deprecation warnings
                OPTIONAL MATCH path = (c)-[:MENTIONS|HAS_CHUNK*1..{depth}]-(c2:Chunk)
                WITH c, collect(DISTINCT coalesce(c2, c)) AS allc
                UNWIND allc AS chunk
                MATCH (chunk)<-[:HAS_CHUNK]-(p:Paper)
                RETURN DISTINCT
                  p.id        AS paper_id,
                  p.title     AS paper_title,
                  coalesce(p.pdf_url, "") AS pdf_url,
                  chunk.text  AS chunk_text,
                  coalesce(chunk.graph_data, "") AS graph_data
                """
                , ids=chunk_ids
            )
            return [r.data() for r in res]

    #LLM
    def _ollama_complete(self, prompt: str, stream=False) -> Iterable[str] | str:
        if not stream:
            r = requests.post(
                OLLAMA_API_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            r.raise_for_status()
            return r.json().get("response", "").strip()

        def gen():
            r = requests.post(
                OLLAMA_API_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                headers={"Content-Type": "application/json"},
                timeout=120,
                stream=True,
            )
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    j = json.loads(line.decode("utf-8"))
                    yield j.get("response", "")
                except Exception:
                    continue
        return gen()

    def _openrouter_complete(self, prompt: str, stream=False) -> Iterable[str] | str:
        if not OPENROUTER_API_KEY:
            return "Error: OPENROUTER_API_KEY not set."
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        if not stream:
            comp = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                extra_headers={"HTTP-Referer": YOUR_SITE_URL, "X-Title": YOUR_SITE_NAME},
            )
            return comp.choices[0].message.content
        else:
            comp = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                stream=True,
                extra_headers={"HTTP-Referer": YOUR_SITE_URL, "X-Title": YOUR_SITE_NAME},
            )
            def gen():
                for chunk in comp:
                    yield (chunk.choices[0].delta.content or "")
            return gen()

    def query_llm(self, context: str, query: str, stream=False):
        prompt = RAG_PROMPT.format(context=context, query=query, CURRENT_DATE_TIME=CURRENT_DATE_TIME)
        if LLM_PROVIDER == "ollama":
            return self._ollama_complete(prompt, stream=stream)
        elif LLM_PROVIDER == "openrouter":
            return self._openrouter_complete(prompt, stream=stream)
        else:
            return "Error: invalid LLM_PROVIDER."

#CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", type=str)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--stream", action="store_true")
    args = ap.parse_args()

    retr = GraphRetriever(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    try:
        q_emb = retr.get_query_embedding(args.query)
        seeds = retr.vector_search(q_emb, top_k=args.k)
        ctx_rows = retr.graph_expansion(seeds, depth=args.depth)

        # assemble context 
        seen = set()
        context_parts = []
        total_len = 0
        for r in ctx_rows:
            ch = r.get("chunk_text") or ""
            if not ch or ch in seen:
                continue
            part = f"Paper: {r.get('paper_title','N/A')}\nChunk: {ch}\n"
            if total_len + len(part) > 8000:
                break
            context_parts.append(part)
            seen.add(ch)
            total_len += len(part)
        context = "\n".join(context_parts)

        print("--- Answer ---")
        if args.stream:
            for tok in retr.query_llm(context, args.query, stream=True):
                print(tok, end="", flush=True)
            print()
        else:
            ans = retr.query_llm(context, args.query, stream=False)
            print(ans)
    finally:
        retr.close()

if __name__ == "__main__":
    main()