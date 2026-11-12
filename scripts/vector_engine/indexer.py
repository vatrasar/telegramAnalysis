"""Thread vector indexing and SQLite table initialization."""

import sqlite3
from typing import List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.config import load_config
from .client import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENROUTER_ENDPOINT,
    is_local_ml_available,
    serialize_vector,
    fetch_openrouter_embeddings,
)


def init_vector_table(conn: sqlite3.Connection) -> None:
    """Create table for vector embeddings in SQLite with multi-chat support."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_embeddings (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT,
        start_date TEXT,
        participants TEXT,
        dialogue_text TEXT,
        content_hash TEXT,
        embedding BLOB
    );
    """)
    cur.execute("PRAGMA table_info(thread_embeddings);")
    cols = {c[1] for c in cur.fetchall()}
    if "content_hash" not in cols:
        cur.execute("ALTER TABLE thread_embeddings ADD COLUMN content_hash TEXT;")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chat ON thread_embeddings(chat_id);")
    conn.commit()


def index_threads(
    db_path: str,
    model_override: Optional[str] = None,
    chat_filter: Optional[str] = None,
    force: bool = False,
    concurrency_override: Optional[int] = None
) -> bool:
    """Embed threads in the database using OpenRouter or local sentence-transformers.

    Supports incremental indexing (only unindexed threads) unless force=True.
    Uses concurrent batching and real-time chunk checkpoints for OpenRouter API.
    """
    config = load_config()
    provider = config.get("provider", "openrouter").lower()

    conn = sqlite3.connect(db_path)
    init_vector_table(conn)
    cur = conn.cursor()

    # Clean orphaned embeddings (threads that no longer exist or whose ID changed)
    cur.execute("DELETE FROM thread_embeddings WHERE thread_id NOT IN (SELECT thread_id FROM threads);")
    conn.commit()

    query = """
    SELECT t.thread_id, t.chat_id, t.start_date, t.participants, t.dialogue_text, t.content_hash
    FROM threads t
    """
    params: List[Any] = []

    if not force:
        query += """
        LEFT JOIN thread_embeddings te ON t.thread_id = te.thread_id 
        WHERE (te.thread_id IS NULL OR te.content_hash IS NULL OR te.content_hash != t.content_hash)
        """
    else:
        query += " WHERE 1=1 "

    if chat_filter:
        query += " AND (t.chat_id = ? OR t.chat_id IN (SELECT chat_id FROM chats WHERE chat_name = ? OR chat_name LIKE ?)) "
        params.extend([chat_filter, chat_filter, f"%{chat_filter}%"])

    cur.execute(query, params)
    rows = cur.fetchall()

    if not rows:
        print("[+] All selected conversation threads are already embedded and up to date. (Use --force to re-embed).")
        conn.close()
        return True

    print(f"[*] Found {len(rows)} new or modified threads to embed (unchanged threads skipped).")
    batch_metadata = []
    batch_texts = []

    for r in rows:
        t_id, c_id, s_date, parts, text, c_hash = r
        clean_text = text[:4000]  # Respect token limits for embedding models
        batch_texts.append(clean_text)
        batch_metadata.append((t_id, c_id, s_date, parts, text, c_hash))

    # Mode 1: OpenRouter API
    if provider in ("openrouter", "api", "openai"):
        api_key = config.get("api_key", "")
        model = model_override or config.get("model", "openai/text-embedding-3-small")
        endpoint = config.get("endpoint", DEFAULT_OPENROUTER_ENDPOINT)
        batch_size = int(config.get("batch_size", 50))
        concurrency = concurrency_override or int(config.get("concurrency", 4))

        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"[*] Using OpenRouter Provider:")
        print(f"    - Endpoint:    {endpoint}")
        print(f"    - Model:       {model}")
        print(f"    - API Key:     {masked_key} (used strictly for /embeddings)")
        print(f"    - Batch Size:  {batch_size}")
        print(f"    - Concurrency: {concurrency} workers")

        chunks = []
        for i in range(0, len(batch_texts), batch_size):
            chunk_texts = batch_texts[i:i + batch_size]
            chunk_meta = batch_metadata[i:i + batch_size]
            chunks.append((i // batch_size + 1, chunk_texts, chunk_meta))

        total_chunks = len(chunks)
        print(f"[*] Embedding {len(batch_texts)} threads across {total_chunks} batches (concurrency: {concurrency})...")

        def fetch_chunk_worker(cid: int, c_texts: List[str], c_meta: List[Any]):
            emb_chunk = fetch_openrouter_embeddings(c_texts, model, api_key, endpoint)
            return cid, c_meta, emb_chunk

        saved_count = 0
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_chunk = {
                executor.submit(fetch_chunk_worker, cid, ctexts, cmeta): cid
                for cid, ctexts, cmeta in chunks
            }

            for future in as_completed(future_to_chunk):
                cid = future_to_chunk[future]
                chunk_id, c_meta, emb_chunk = future.result()

                insert_rows = []
                for (t_id, c_id, s_date, parts, text, c_hash), emb in zip(c_meta, emb_chunk):
                    blob = serialize_vector(emb)
                    insert_rows.append((t_id, c_id, s_date, parts, text, c_hash, blob))

                cur.executemany("""
                INSERT OR REPLACE INTO thread_embeddings (thread_id, chat_id, start_date, participants, dialogue_text, content_hash, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """, insert_rows)
                conn.commit()
                saved_count += len(insert_rows)
                print(f"[+] Saved batch {chunk_id}/{total_chunks} ({len(insert_rows)} threads) to database. [Progress: {saved_count}/{len(batch_texts)}]")

        conn.close()
        print(f"[+] Successfully indexed {saved_count} threads into SQLite vector store.")
        return True

    # Mode 2: Local Sentence-Transformers
    elif provider == "local":
        if not is_local_ml_available():
            print("[!] 'provider' is set to 'local', but 'sentence-transformers' is not installed.")
            print("    Options:")
            print("    1. Install local ML: pip install sentence-transformers")
            print("    2. OR configure OpenRouter in config/embeddings_config.json")
            print("    (Note: Fast FTS5 search is currently active without any installation).")
            conn.close()
            return False

        from sentence_transformers import SentenceTransformer
        model_name = model_override or config.get("model", DEFAULT_LOCAL_MODEL)
        print(f"[*] Using Local SentenceTransformer Model: {model_name}...")
        model = SentenceTransformer(model_name)
        embeddings = model.encode(batch_texts, normalize_embeddings=True, show_progress_bar=True)
        all_embeddings = embeddings.tolist()

        insert_rows = []
        for (t_id, c_id, s_date, parts, text, c_hash), emb in zip(batch_metadata, all_embeddings):
            blob = serialize_vector(emb)
            insert_rows.append((t_id, c_id, s_date, parts, text, c_hash, blob))

        cur.executemany("""
        INSERT OR REPLACE INTO thread_embeddings (thread_id, chat_id, start_date, participants, dialogue_text, content_hash, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, insert_rows)

        conn.commit()
        conn.close()
        print(f"[+] Successfully indexed {len(insert_rows)} threads into SQLite vector store.")
        return True

    else:
        print(f"[!] Unknown provider '{provider}' in configuration.")
        conn.close()
        return False
