#spark_processor.py 
import os
import json
import uuid
import time
import re
import requests
import fitz  
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_replace
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, FloatType

from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

load_dotenv()

# --LLM / Embeddings config --------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

#Ollama
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")

#OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
YOUR_SITE_URL = os.getenv("YOUR_SITE_URL", "")
YOUR_SITE_NAME = os.getenv("YOUR_SITE_NAME", "")

# Embeddings (Ollama)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5")

# ------ Prompt for graph extraction ---
GRAPH_PROMPT = """
From the academic text below, extract structured knowledge as entities and relationships.

Entity types:
- Method
- Dataset
- Tool
- Metric
- ScientificConcept

Relationship types:
- USES_METHOD
- EVALUATED_ON
- COMPARES
- IMPROVES
- BASED_ON

Output format:
Return ONLY a valid JSON object structured like this:
{{
  "entities": [
    {{"name": "BERT", "type": "Tool"}},
    {{"name": "SQuAD", "type": "Dataset"}}
  ],
  "relationships": [
    {{"source": "BERT", "target": "SQuAD", "type": "EVALUATED_ON"}}
  ]
}}
Rules:
- Only include entities/relations explicitly stated or clearly implied.
- No speculation or hallucination.
- No explanations, comments, or markdown.
- Ensure valid JSON.
- Use exact entity names from text.

Input Text:
{text}

Output JSON only:
"""

#Utilities 
def extract_pdf_text(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"[WARN] extract_pdf_text failed for {pdf_path}: {e}")
        return ""

def _extract_json_block(s: str):
    """Best-effort: capture largest {...} block."""
    m = re.search(r"\{.*\}", s, re.S)
    return m.group(0) if m else None

def _call_ollama(prompt: str, retries=2, delay=2):
    for i in range(retries):
        try:
            r = requests.post(
                OLLAMA_API_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as e:
            print(f"[WARN] Ollama call failed ({i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
    return ""

def _call_openrouter(prompt: str, retries=2, delay=2):
    if not OPENROUTER_API_KEY:
        return ""
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    for i in range(retries):
        try:
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                extra_headers={
                    "HTTP-Referer": YOUR_SITE_URL,
                    "X-Title": YOUR_SITE_NAME,
                },
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            print(f"[WARN] OpenRouter call failed ({i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
    return ""

def extract_graph_data(text: str) -> dict:
    """Graph extraction from summary (shorter = faster)."""
    snippet = text[:3000]  
    prompt = GRAPH_PROMPT.format(text=snippet)
    if LLM_PROVIDER == "ollama":
        raw = _call_ollama(prompt)
    elif LLM_PROVIDER == "openrouter":
        raw = _call_openrouter(prompt)
    else:
        raw = ""

    block = _extract_json_block(raw) if raw else None
    if not block:
        return {"entities": [], "relationships": []}
    try:
        return json.loads(block)
    except Exception as e:
        print(f"[WARN] JSON parse failed: {e}")
        return {"entities": [], "relationships": []}

#Faster embed 
def embed_chunks_parallel(embedder, chunks, workers=8):
    """Parallel embedding calls to Ollama."""
    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(embedder.embed_query, chunks[i]): i for i in range(len(chunks))
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = [float(x) for x in future.result()]
            except Exception as e:
                print(f"[WARN] embedding failed for chunk {idx}: {e}")
                results[idx] = []
    return results

# Main processing pipeline 
def process_arxiv_data(records: list, output_path: str):
    spark = SparkSession.builder.appName("ArxivDataProcessor").getOrCreate()
    df = spark.createDataFrame(records)

    # Extract PDFs in pandas
    pdf_df = df.toPandas()
    pdf_df["full_text"] = pdf_df["pdf_path"].apply(lambda p: extract_pdf_text(p) if p else "")
    df = spark.createDataFrame(pdf_df)

    df = (
        df.withColumn("clean_summary", regexp_replace(col("summary"), r"\s+", " "))
          .withColumn("clean_full_text", regexp_replace(col("full_text"), r"\s+", " "))
          .filter(col("summary").isNotNull())
    )

    rows = df.select(
        "arxiv_id", "title", "authors", "published", "categories", "pdf_url",
        "clean_summary", "clean_full_text"
    ).collect()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)

    out_rows = []
    for r in rows:
        paper_id = r["arxiv_id"]
        metadata = {
            "title": r["title"],
            "authors": r["authors"],
            "published": r["published"],
            "categories": r["categories"],
            "pdf_url": r["pdf_url"],
        }
        full_text = f"{r['clean_summary'] or ''}\n\n{r['clean_full_text'] or ''}"

        #extract graph only from summary
        start = time.time()
        graph_data = extract_graph_data(r['clean_summary'] or full_text[:2000])
        print(f"[TIMER] Graph extraction took {time.time()-start:.2f}s")

        #Split into chunks
        chunks = splitter.split_text(full_text)

        #FAST: parallel embeddings
        start = time.time()
        embeddings = embed_chunks_parallel(embedder, chunks, workers=6) if chunks else []
        print(f"[TIMER] Embedded {len(chunks)} chunks in {time.time()-start:.2f}s")

        for i, chunk in enumerate(chunks):
            emb = embeddings[i] if i < len(embeddings) else []
            out_rows.append({
                "paper_id": paper_id,
                "chunk_id": f"{paper_id}_chunk_{i}",
                "chunk_text": chunk,
                "embedding": emb,
                "metadata": json.dumps(metadata),
                "graph_data": json.dumps(graph_data),
            })

    if not out_rows:
        print("[INFO] No processed rows; skipping Parquet write.")
        return None

    schema = StructType([
        StructField("paper_id", StringType(), True),
        StructField("chunk_id", StringType(), True),
        StructField("chunk_text", StringType(), True),
        StructField("embedding", ArrayType(FloatType()), True),
        StructField("metadata", StringType(), True),
        StructField("graph_data", StringType(), True),
    ])
    out_df = spark.createDataFrame(out_rows, schema=schema)

    print(f"[INFO] Writing Parquet to {output_path}")
    out_df.write.mode("overwrite").parquet(output_path)
    print("[INFO] Done.")
    return out_df

if __name__ == "__main__":
    from arxiv_retriever import retrieve_arxiv_papers
    artifacts_dir = "artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)
    parquet_path = os.path.join(artifacts_dir, f"processed_{uuid.uuid4().hex}.parquet")

    results = retrieve_arxiv_papers("Machine Learning", max_results=3, download_pdfs=True)
    if results:
        process_arxiv_data(results, parquet_path)
        #cleanup PDFs
        for it in results:
            p = it.get("pdf_path")
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass