"""Semantic search algorithms with FTS5 BM25 fallback."""

import sys
import sqlite3
from typing import List, Dict, Any, Optional

from common.config import load_config
from .client import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENROUTER_ENDPOINT,
    is_local_ml_available,
    deserialize_vector,
    dot_product,
    fetch_openrouter_embeddings,
)
from .indexer import index_threads


def search_semantic_batch(
    db_path: str,
    queries: List[str],
    top_k: int = 5,
    chat_filter: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Search conversation threads by multiple semantic concepts in a single batch pass."""
    if not queries:
        return {}

    config = load_config()
    provider = config.get("provider", "openrouter").lower()

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
            index_threads(db_path, chat_filter=chat_filter)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
        else:
            # Fallback to FTS5 for each query
            print(f"\n[!] WARNING: Database '{db_path}' contains NO vector embeddings!", file=sys.stderr)
            print("    Embedding configuration in config/embeddings_config.json is missing or placeholder.", file=sys.stderr)
            print("    Falling back to lexical FTS5 (BM25) search. Real semantic embeddings were NOT used.", file=sys.stderr)
            print("    To fix: Complete setup ('python3 project/scripts/setup_config.py') and run vector indexing ('python3 project/scripts/vector_indexer.py --db <db> --index').\n", file=sys.stderr)
            results_map: Dict[str, List[Dict[str, Any]]] = {}
            for query in queries:
                clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
                words = clean_q.split()
                if not words:
                    results_map[query] = []
                    continue
                terms = []
                for w in words:
                    terms.append(f'"{w}"')
                    if len(w) >= 5:
                        stem = w[:-2] if w.endswith(('ść', 'ch', 'em', 'om', 'ów', 'mi')) else (w[:-1] if w.endswith(('a', 'e', 'y', 'i', 'o', 'u', 'ę', 'ą')) else w)
                        if len(stem) >= 3:
                            terms.append(f'"{stem}"*')
                match_query = " OR ".join(terms)
                try:
                    sql = """
                    SELECT tf.thread_id, tf.chat_id, coalesce(c.chat_name, tf.chat_id) as chat_name,
                           tf.start_date, tf.participants, tf.dialogue_text, bm25(threads_fts) as rank
                    FROM threads_fts tf
                    LEFT JOIN chats c ON tf.chat_id = c.chat_id
                    WHERE threads_fts MATCH ?
                    """
                    p = [match_query]
                    if chat_filter:
                        sql += " AND (tf.chat_id = ? OR c.chat_name = ? OR c.chat_name LIKE ?) "
                        p.extend([chat_filter, chat_filter, f"%{chat_filter}%"])
                    sql += " ORDER BY rank ASC LIMIT ?; "
                    p.append(top_k)

                    cur.execute(sql, p)
                    q_res = []
                    for r in cur.fetchall():
                        q_res.append({
                            "thread_id": r[0],
                            "chat_id": r[1],
                            "chat_name": r[2],
                            "start_date": r[3],
                            "participants": r[4],
                            "dialogue_text": r[5],
                            "score": round(-float(r[6]), 3)
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

    # Read stored thread vectors
    sql = """
    SELECT te.thread_id, te.chat_id, coalesce(c.chat_name, te.chat_id) as chat_name,
           te.start_date, te.participants, te.dialogue_text, te.embedding
    FROM thread_embeddings te
    LEFT JOIN chats c ON te.chat_id = c.chat_id
    """
    params = []
    if chat_filter:
        sql += " WHERE te.chat_id = ? OR c.chat_name = ? OR c.chat_name LIKE ? "
        params.extend([chat_filter, chat_filter, f"%{chat_filter}%"])

    cur.execute(sql, params)
    thread_rows = []
    for r in cur.fetchall():
        thread_rows.append((r[0], r[1], r[2], r[3], r[4], r[5], deserialize_vector(r[6])))
    conn.close()

    results_map: Dict[str, List[Dict[str, Any]]] = {}
    for q_text, q_vec in zip(queries, query_vecs):
        scored = []
        for t_id, c_id, c_name, s_date, parts, text, emb in thread_rows:
            sim = dot_product(q_vec, emb)
            scored.append({
                "thread_id": t_id,
                "chat_id": c_id,
                "chat_name": c_name,
                "start_date": s_date,
                "participants": parts,
                "dialogue_text": text,
                "score": round(float(sim), 4)
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        results_map[q_text] = scored[:top_k]

    return results_map


def search_semantic(
    db_path: str,
    query: str,
    top_k: int = 5,
    chat_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search conversation threads by a single semantic concept."""
    res = search_semantic_batch(db_path, [query], top_k=top_k, chat_filter=chat_filter)
    return res.get(query, [])
