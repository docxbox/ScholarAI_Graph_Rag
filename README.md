📚 ScholarAI Graph-RAG

Scholar Graph-RAG is an AI-powered research assistant that combines knowledge graphs, arXiv papers, and large language models into a seamless exploration tool.
It allows researchers to ask natural-language questions, retrieve relevant papers, visualize connections between concepts, and receive AI-generated insights in a clean chat-style interface.

<img width="1180" height="658" alt="image" src="https://github.com/user-attachments/assets/c271d573-69b5-4557-a8d7-ac9e1213c787" />



🚀 Features

Graph-RAG Retrieval: Combines vector search + knowledge graph traversal for deep context.

Natural Language Querying: Ask complex research questions, get grounded answers.

Interactive Graph: Explore papers, entities, and relationships visually.

Chat Interface: Conversational AI that streams responses in real time.

Research Metadata: View paper titles, PDF links, and key context alongside the chat.

History Sidebar: Navigate past queries like a modern AI assistant.

🏗️ System Architecture
1. Offline Data Pipeline

arxiv_retriever.py – fetches papers & PDFs from arXiv API.

spark_processor.py – processes PDFs into chunks, embeddings, and graph entities using PySpark + Ollama/OpenRouter.

graph_pipe.py – loads processed data into Neo4j as a searchable knowledge graph.

2. Online API Server

FastAPI backend (main.py, retriever.py) serves queries.

Vector search via Neo4j’s vector index.

Expands retrieved nodes into connected entities/papers.

Streams responses from LLM (Ollama/OpenRouter).

3. Frontend (React)

Left panel → Chat history.

Center panel → Conversation + AI answers + paper metadata.

Right panel → Graph visualization.

🛠️ Tech Stack

Backend: FastAPI, Neo4j, PySpark, PyMuPDF, LangChain, Ollama/OpenRouter

Frontend: React + Tailwind (with modern design)

Database: Neo4j (graph DB + vector index)

Infrastructure: Docker (optional for deployment)

⚡ Quick Start
1. Clone the Repository
git clone https://github.com/YOUR-USERNAME/scholar-graph-rag.git
cd scholar-graph-rag

2. Backend Setup
cd backend
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt


Set up .env file:

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword
NEO4J_DATABASE=neo4j
LLM_PROVIDER=openrouter   # or ollama
EMBED_MODEL=nomic-embed-text
GEN_MODEL=gpt-oss-20b


Run backend:

uvicorn main:app --reload --host 0.0.0.0 --port 8000

3. Frontend Setup
cd frontend
npm install
npm run dev

