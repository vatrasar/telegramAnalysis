#!/usr/bin/env python3
"""
Thread Vector Indexer with OpenRouter & Local Embedding Support.
Embeds conversation threads and computes cosine similarity for psychological concept retrieval.

Supported modes:
1. OpenRouter / OpenAI API: Uses standard library urllib (zero dependencies needed).
2. Local Sentence-Transformers: Runs on local GPU (RTX 4060) or CPU.
3. Zero-dependency Fallback: SQLite FTS5 BM25 search.
"""

import os
import sys
import json
import sqlite3
import struct
import argparse
import urllib.request
import urllib.error
from typing import List, Dict, Any, Tuple, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # project/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # project
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "embeddings_config.json")
DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"


def load_config() -> Dict[str, Any]:
    """Load configuration from config/embeddings_config.json in workspace root if present."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Failed to parse {CONFIG_PATH}: {e}")
    return {}


def is_local_ml_available() -> bool:
    """Check if local sentence-transformers package is installed."""
    try:
        import sentence_transformers
        return True
    except ImportError:
        return False


def init_vector_table(conn: sqlite3.Connection):
    """Create table for vector embeddings in SQLite."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_embeddings (
        thread_id TEXT PRIMARY KEY,
        start_date TEXT,
        participants TEXT,
        dialogue_text TEXT,
        embedding BLOB
    );
    """)
    conn.commit()


def serialize_vector(vec: List[float]) -> bytes:
    """Pack float array into compact binary blob."""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(blob: bytes) -> List[float]:
    """Unpack binary blob back into float array."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def dot_product(v1: List[float], v2: List[float]) -> float:
    """Compute dot product / cosine similarity between normalized vectors."""
    # Assuming normalized vectors from API or model
    dot = sum(x * y for x, y in zip(v1, v2))
    # Normalize if needed
    norm1 = sum(x * x for x in v1) ** 0.5
    norm2 = sum(y * y for y in v2) ** 0.5
    if norm1 > 0 and norm2 > 0:
        return dot / (norm1 * norm2)
    return dot


def fetch_openrouter_embeddings(texts: List[str], model: str, api_key: str, endpoint: str) -> List[List[float]]:
    """
    Fetch embeddings from OpenRouter via standard urllib.request.
    Guaranteed zero external library dependencies and restricted purely to /embeddings.
    """
    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
        raise ValueError("Invalid or placeholder OpenRouter API key found in configuration.")

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Telegram Psychological Analysis Agent"
    }

    payload = {
        "model": model,
        "input": texts
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            data_items = resp_body.get("data", [])
            # Sort by index to preserve order
            data_items.sort(key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in data_items]
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenRouter HTTP {e.code} Error: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"OpenRouter Connection Error: {e}")


def index_threads(db_path: str, model_override: Optional[str] = None):
    """Embed all threads in the database using OpenRouter or local sentence-transformers."""
    config = load_config()
    provider = config.get("provider", "local").lower()
    
    conn = sqlite3.connect(db_path)
    init_vector_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT thread_id, start_date, participants, dialogue_text FROM threads")
    rows = cur.fetchall()
    if not rows:
        print("[!] No threads found in database. Build the database first with db_builder.py.")
        conn.close()
        return False

    print(f"[*] Found {len(rows)} threads to embed.")
    batch_metadata = []
    batch_texts = []

    for r in rows:
        t_id, s_date, parts, text = r
        clean_text = text[:4000]  # Respect token limits for embedding models
        batch_texts.append(clean_text)
        batch_metadata.append((t_id, s_date, parts, text))

    # Mode 1: OpenRouter API
    if provider in ("openrouter", "api", "openai"):
        api_key = config.get("api_key", "")
        model = model_override or config.get("model", "openai/text-embedding-3-small")
        endpoint = config.get("endpoint", DEFAULT_OPENROUTER_ENDPOINT)
        batch_size = int(config.get("batch_size", 50))

        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"[*] Using OpenRouter Provider:")
        print(f"    - Endpoint:   {endpoint}")
        print(f"    - Model:      {model}")
        print(f"    - API Key:    {masked_key} (used strictly for /embeddings)")
        print(f"    - Batch Size: {batch_size}")

        all_embeddings: List[List[float]] = []
        for i in range(0, len(batch_texts), batch_size):
            chunk = batch_texts[i:i + batch_size]
            print(f"[*] Embedding batch {i // batch_size + 1}/{(len(batch_texts) + batch_size - 1) // batch_size} ({len(chunk)} threads)...")
            emb_chunk = fetch_openrouter_embeddings(chunk, model, api_key, endpoint)
            all_embeddings.extend(emb_chunk)

    # Mode 2: Local Sentence-Transformers
    elif provider == "local":
        if not is_local_ml_available():
            print("[!] 'provider' is set to 'local', but 'sentence-transformers' is not installed.")
            print("    Options:")
            print("    1. Install local ML: pip install sentence-transformers")
            print("    2. OR configure OpenRouter in project/config/embeddings_config.json")
            print("    (Note: Fast FTS5 search is currently active without any installation).")
            conn.close()
            return False

        from sentence_transformers import SentenceTransformer
        model_name = model_override or config.get("model", DEFAULT_LOCAL_MODEL)
        print(f"[*] Using Local SentenceTransformer Model: {model_name}...")
        model = SentenceTransformer(model_name)
        embeddings = model.encode(batch_texts, normalize_embeddings=True, show_progress_bar=True)
        all_embeddings = embeddings.tolist()

    else:
        print(f"[!] Unknown provider '{provider}' in configuration.")
        conn.close()
        return False

    # Insert embeddings
    insert_rows = []
    for (t_id, s_date, parts, text), emb in zip(batch_metadata, all_embeddings):
        blob = serialize_vector(emb)
        insert_rows.append((t_id, s_date, parts, text, blob))

    cur.executemany("""
    INSERT OR REPLACE INTO thread_embeddings (thread_id, start_date, participants, dialogue_text, embedding)
    VALUES (?, ?, ?, ?, ?);
    """, insert_rows)

    conn.commit()
    conn.close()
    print(f"[+] Successfully indexed {len(insert_rows)} threads into SQLite vector store.")
    return True


def search_semantic_batch(db_path: str, queries: List[str], top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """Search conversation threads by multiple semantic concepts in a single batch pass."""
    if not queries:
        return {}

    config = load_config()
    provider = config.get("provider", "local").lower()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_embeddings'")
    if cur.fetchone()[0] == 0:
        table_exists = False
    else:
        cur.execute("SELECT count(*) FROM thread_embeddings")
        table_exists = cur.fetchone()[0] > 0

    if not table_exists:
        # Check if we should automatically run index
        has_openrouter = provider in ("openrouter", "api") and config.get("api_key") and "YOUR_OPENROUTER_API_KEY" not in config.get("api_key", "")
        has_local = provider == "local" and is_local_ml_available()

        if has_openrouter or has_local:
            print("[*] Vectors not yet indexed. Generating embeddings now...")
            conn.close()
            index_threads(db_path)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
        else:
            # Fallback to FTS5 for each query
            results_map: Dict[str, List[Dict[str, Any]]] = {}
            for query in queries:
                clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
                words = clean_q.split()
                if not words:
                    results_map[query] = []
                    continue
                match_query = " OR ".join(words)
                try:
                    cur.execute("""
                    SELECT thread_id, start_date, participants, dialogue_text, bm25(threads_fts) as rank
                    FROM threads_fts
                    WHERE threads_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?;
                    """, (match_query, top_k))
                    q_res = []
                    for r in cur.fetchall():
                        q_res.append({
                            "thread_id": r[0],
                            "start_date": r[1],
                            "participants": r[2],
                            "dialogue_text": r[3],
                            "score": round(-float(r[4]), 3)
                        })
                    results_map[query] = q_res
                except Exception:
                    results_map[query] = []
            conn.close()
            return results_map

    # Generate query embeddings in batch
    if provider in ("openrouter", "api", "openai"):
        api_key = config.get("api_key", "")
        model = config.get("model", "openai/text-embedding-3-small")
        endpoint = config.get("endpoint", DEFAULT_OPENROUTER_ENDPOINT)
        query_vecs = fetch_openrouter_embeddings(queries, model, api_key, endpoint)
    else:
        from sentence_transformers import SentenceTransformer
        model_name = config.get("model", DEFAULT_LOCAL_MODEL)
        model = SentenceTransformer(model_name)
        query_vecs = model.encode(queries, normalize_embeddings=True).tolist()

    # Read stored thread vectors once
    cur.execute("SELECT thread_id, start_date, participants, dialogue_text, embedding FROM thread_embeddings")
    thread_rows = []
    for r in cur.fetchall():
        thread_rows.append((r[0], r[1], r[2], r[3], deserialize_vector(r[4])))
    conn.close()

    results_map: Dict[str, List[Dict[str, Any]]] = {}
    for q_text, q_vec in zip(queries, query_vecs):
        scored = []
        for t_id, s_date, parts, text, emb in thread_rows:
            sim = dot_product(q_vec, emb)
            scored.append({
                "thread_id": t_id,
                "start_date": s_date,
                "participants": parts,
                "dialogue_text": text,
                "score": round(float(sim), 4)
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        results_map[q_text] = scored[:top_k]

    return results_map


def search_semantic(db_path: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search conversation threads by a single semantic concept."""
    res = search_semantic_batch(db_path, [query], top_k=top_k)
    return res.get(query, [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed conversation threads for semantic psychological search.")
    parser.add_argument("--db", default="chat_index.db", help="Path to SQLite database")
    parser.add_argument("--index", action="store_true", help="Run indexing on threads")
    parser.add_argument("--search", type=str, help="Semantic search query")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--model", type=str, help="Override model name")
    args = parser.parse_args()

    if args.index:
        index_threads(args.db, args.model)
    elif args.search:
        results = search_semantic(args.db, args.search, args.top_k)
        print(f"\n--- Top {len(results)} Semantic Matches for: '{args.search}' ---")
        for i, res in enumerate(results, 1):
            print(f"\n[{i}] Thread: {res['thread_id']} | Date: {res['start_date'][:10]} | Score: {res['score']}")
            print(f"Participants: {res['participants']}")
            print(res["dialogue_text"])
            print("-" * 50)
    else:
        parser.print_help()
