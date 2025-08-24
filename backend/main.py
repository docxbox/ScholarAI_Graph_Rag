import uvicorn
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from retriever import GraphRetriever
import os
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Generator
from neo4j.exceptions import ServiceUnavailable
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Neo4j Config ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

graph_retriever = None

# --- FastAPI Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_retriever
    try:
        graph_retriever = GraphRetriever(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
        graph_retriever.driver.verify_connectivity()
        logger.info("Connected to Neo4j.")
        yield
    except ServiceUnavailable as e:
        logger.error(f"Could not connect to Neo4j: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable.")
    finally:
        if graph_retriever:
            graph_retriever.close()
            logger.info("Closed Neo4j connection.")

# --- FastAPI App Init ---
app = FastAPI(
    title="Scholar API",
    description="API for querying research papers and their connections.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Vite default port
    "http://localhost:8080",  
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class QueryRequest(BaseModel):
    query: str

class Source(BaseModel):
    paper_id: str
    paper_title: str
    pdf_url: str
    chunk_text: str

class GraphNode(BaseModel):
    id: str
    type: str

class GraphEdge(BaseModel):
    source: str
    target: str
    type: str

class Graph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class StructuredResponse(BaseModel):
    sources: List[Source]
    graph: Graph

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# --- Data Preparation Helper ---
def _prepare_structured_data(context_data: List[Dict[str, Any]]) -> tuple[StructuredResponse, str]:
    sources = []
    graph_nodes = {}
    graph_edges = {}
    context_for_llm = ""
    seen_chunks = set()

    for r in context_data:
        if isinstance(r.get("graph_data"), str):
            try:
                r["graph_data"] = json.loads(r["graph_data"])
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse graph_data JSON: {e}")
                r["graph_data"] = {}

        if r["chunk_text"] not in seen_chunks:
            s = Source(
                paper_id=r["paper_id"],
                paper_title=r["paper_title"],
                pdf_url=r["pdf_url"],
                chunk_text=r["chunk_text"],
            )
            sources.append(s)
            context_for_llm += f"Paper: {r['paper_title']}\nChunk: {r['chunk_text']}\n\n"
            seen_chunks.add(r["chunk_text"])

        gd = r.get("graph_data") or {}
        for e in gd.get("entities", []):
            graph_nodes[e["name"]] = GraphNode(id=e["name"], type=e["type"])
        for rel in gd.get("relationships", []):
            key = (rel["source"], rel["target"], rel["type"])
            graph_edges[key] = GraphEdge(
                source=rel["source"], target=rel["target"], type=rel["type"]
            )

    structured_response = StructuredResponse(
        sources=sources,
        graph=Graph(nodes=list(graph_nodes.values()), edges=list(graph_edges.values())),
    )
    return structured_response, context_for_llm

# --- Streaming Endpoint ---
@app.post("/query")
async def query_endpoint(request: QueryRequest) -> StreamingResponse:
    if not graph_retriever:
        raise HTTPException(status_code=503, detail="Database connection not available.")

    def response_generator() -> Generator[str, None, None]:
        try:
            query_embedding = graph_retriever.get_query_embedding(request.query)
            top_chunks = graph_retriever.vector_search(query_embedding)
            context_data = graph_retriever.graph_expansion(top_chunks)
            structured_data, context_for_llm = _prepare_structured_data(context_data)

            #yield graph
            graph_payload = {
                "type": "graph",
                "nodes": [node.model_dump() for node in structured_data.graph.nodes],
                "edges": [edge.model_dump() for edge in structured_data.graph.edges],
            }
            yield f"data: {json.dumps(graph_payload)}\n\n"

            # Then yield metadata
            sources_payload = {
                "type": "metadata",
                "sources": [source.model_dump() for source in structured_data.sources],
            }
            yield f"data: {json.dumps(sources_payload)}\n\n"

            #stream LLM answer
            for token in graph_retriever.query_llm(context_for_llm, request.query, stream=True):
                text_payload = {"type": "text", "chunk": token}
                yield f"data: {json.dumps(text_payload)}\n\n"

        except Exception as e:
            logger.error(f"Error during query: {e}")
            yield f"data: {json.dumps({'error': 'Something went wrong'})}\n\n"
        finally:
            yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(response_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
