"""Thread message chunking, JIT embedding, and context-window snippet extraction."""

import sys
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

from common.config import load_config
from .client import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENROUTER_ENDPOINT,
    is_local_ml_available,
    serialize_vector,
    deserialize_vector,
    dot_product,
    fetch_openrouter_embeddings,
)

DEFAULT_CHUNK_SIZE: int = 5
DEFAULT_CONTEXT_WINDOW: int = 5
SHORT_THREAD_THRESHOLD: int = 15


def init_chunk_vector_table(conn: sqlite3.Connection) -> None:
    """Initialize table for 5-message thread chunk vector embeddings."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_chunk_embeddings (
        chunk_id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start_msg_id INTEGER NOT NULL,
        end_msg_id INTEGER NOT NULL,
        start_msg_idx INTEGER NOT NULL,
        end_msg_idx INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,
        content_hash TEXT,
        embedding BLOB NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunk_emb_thread ON thread_chunk_embeddings(thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunk_emb_chat ON thread_chunk_embeddings(chat_id);")
    conn.commit()


def get_thread_messages(conn: sqlite3.Connection, thread_id: str) -> List[Dict[str, Any]]:
    """Fetch chronological messages for a single thread."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, chat_id, date, timestamp, sender, text
        FROM messages
        WHERE thread_id = ?
        ORDER BY timestamp ASC, id ASC
    """, (thread_id,))
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "chat_id": r[1],
            "date": r[2],
            "timestamp": r[3],
            "sender": r[4],
            "text": r[5] or ""
        }
        for r in rows
    ]


def chunk_thread_messages(
    messages: List[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> List[Dict[str, Any]]:
    """Partition chronological messages into discrete packets (chunks) of N messages."""
    chunks = []
    if not messages:
        return chunks

    for idx, i in enumerate(range(0, len(messages), chunk_size)):
        slice_msgs = messages[i : i + chunk_size]
        chunk_lines = [
            f"[{m['sender']}]: {m['text']}"
            for m in slice_msgs
            if m.get("text") and m["text"].strip()
        ]
        # In case all messages in slice were media or empty text
        chunk_text = "\n".join(chunk_lines) if chunk_lines else f"[{slice_msgs[0]['sender']}]: <media/action>"
        chunks.append({
            "chunk_index": idx,
            "start_msg_idx": i,
            "end_msg_idx": i + len(slice_msgs) - 1,
            "start_msg_id": slice_msgs[0]["id"],
            "end_msg_id": slice_msgs[-1]["id"],
            "chunk_text": chunk_text,
            "msg_count": len(slice_msgs)
        })
    return chunks


def ensure_thread_chunks_embedded(
    db_path: str,
    thread_id: str,
    chat_id: str,
    content_hash: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Retrieve or JIT-embed 5-message chunks for a specific thread.

    Cached in thread_chunk_embeddings. Re-indexes only if chunks are missing
    or content_hash has changed.
    """
    conn = sqlite3.connect(db_path)
    init_chunk_vector_table(conn)
    cur = conn.cursor()

    cur.execute("""
        SELECT chunk_id, chunk_index, start_msg_id, end_msg_id, start_msg_idx, end_msg_idx,
               chunk_text, content_hash, embedding
        FROM thread_chunk_embeddings
        WHERE thread_id = ?
        ORDER BY chunk_index ASC
    """, (thread_id,))
    rows = cur.fetchall()

    # Check if cache is fresh
    cache_valid = False
    if rows:
        cached_hash = rows[0][7]
        if content_hash and cached_hash == content_hash:
            cache_valid = True
        elif not content_hash and cached_hash:
            cache_valid = True

    if cache_valid:
        conn.close()
        return [
            {
                "chunk_id": r[0],
                "chunk_index": r[1],
                "start_msg_id": r[2],
                "end_msg_id": r[3],
                "start_msg_idx": r[4],
                "end_msg_idx": r[5],
                "chunk_text": r[6],
                "content_hash": r[7],
                "vector": deserialize_vector(r[8])
            }
            for r in rows
        ]

    # Cache miss or stale: build chunks from messages
    messages = get_thread_messages(conn, thread_id)
    if not messages:
        conn.close()
        return []

    chunks = chunk_thread_messages(messages, chunk_size=DEFAULT_CHUNK_SIZE)
    if not chunks:
        conn.close()
        return []

    if config is None:
        config = load_config()

    provider = config.get("provider", "openrouter").lower()
    texts_to_embed = [c["chunk_text"] for c in chunks]

    # Generate embeddings
    chunk_vecs = []
    try:
        if provider in ("openrouter", "api", "openai"):
            api_key = config.get("api_key", "")
            if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
                conn.close()
                return []
            model = config.get("model", "openai/text-embedding-3-small")
            endpoint = config.get("endpoint", DEFAULT_OPENROUTER_ENDPOINT)
            chunk_vecs = fetch_openrouter_embeddings(texts_to_embed, model, api_key, endpoint)
        elif provider == "local" and is_local_ml_available():
            from sentence_transformers import SentenceTransformer
            model_name = config.get("model", DEFAULT_LOCAL_MODEL)
            model = SentenceTransformer(model_name)
            chunk_vecs = model.encode(texts_to_embed, normalize_embeddings=True).tolist()
        else:
            conn.close()
            return []
    except Exception as exc:
        print(f"[!] Warning: JIT chunk embedding failed for thread {thread_id}: {exc}", file=sys.stderr)
        conn.close()
        return []

    # Store into SQLite cache
    cur.execute("DELETE FROM thread_chunk_embeddings WHERE thread_id = ?", (thread_id,))
    out_chunks = []
    for c, vec in zip(chunks, chunk_vecs):
        cid = f"{thread_id}_c{c['chunk_index']}"
        blob = serialize_vector(vec)
        cur.execute("""
            INSERT OR REPLACE INTO thread_chunk_embeddings
            (chunk_id, thread_id, chat_id, chunk_index, start_msg_id, end_msg_id,
             start_msg_idx, end_msg_idx, chunk_text, content_hash, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid, thread_id, chat_id, c["chunk_index"],
            c["start_msg_id"], c["end_msg_id"],
            c["start_msg_idx"], c["end_msg_idx"],
            c["chunk_text"], content_hash, blob
        ))
        c_copy = dict(c)
        c_copy["chunk_id"] = cid
        c_copy["content_hash"] = content_hash
        c_copy["vector"] = vec
        out_chunks.append(c_copy)

    conn.commit()
    conn.close()
    return out_chunks


def merge_cluster_windows(
    windows: List[Tuple[int, int]],
    merge_gap: int = 1
) -> List[Tuple[int, int]]:
    """Merge overlapping or adjacent message index windows into continuous clusters."""
    if not windows:
        return []
    sorted_wins = sorted(windows, key=lambda w: w[0])
    merged = [sorted_wins[0]]
    for cur_start, cur_end in sorted_wins[1:]:
        prev_start, prev_end = merged[-1]
        if cur_start <= prev_end + merge_gap:
            # Overlapping or adjacent: merge
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append((cur_start, cur_end))
    return merged


def format_snippet_messages(messages: List[Dict[str, Any]]) -> str:
    """Format a contiguous list of messages into an inspection snippet."""
    lines = []
    for m in messages:
        date_str = m["date"][11:16] if len(m["date"]) >= 16 else m["date"]
        txt = m["text"].strip() if m.get("text") else "<empty>"
        lines.append(f"[#{m['id']} | {date_str}] {m['sender']}: {txt}")
    return "\n".join(lines)


def resolve_thread_snippet(
    db_path: str,
    thread_id: str,
    chat_id: str,
    query_vec: List[float],
    content_hash: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    min_score: Optional[float] = None,
    context_window: int = DEFAULT_CONTEXT_WINDOW
) -> Dict[str, Any]:
    """Identify whether a query matches a localized cluster or spans across the thread.

    Returns:
    - If single cluster: returns focused snippet (+/- 5 messages context buffer).
    - If multiple distant clusters: falls back to full thread ("wtedy niech wczytuje caly watek").
    - If short thread (<= 15 msgs): returns full thread.
    """
    conn = sqlite3.connect(db_path)
    messages = get_thread_messages(conn, thread_id)
    conn.close()

    total_msgs = len(messages)
    if total_msgs == 0:
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "empty_thread",
            "score": 0.0,
            "start_msg_id": None,
            "end_msg_id": None,
            "msg_count": 0,
            "total_messages": 0,
            "formatted_snippet": "",
            "cluster_count": 0,
        }

    # Short threads do not need slicing
    if total_msgs <= SHORT_THREAD_THRESHOLD:
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "short_thread",
            "score": 0.0,
            "start_msg_id": messages[0]["id"],
            "end_msg_id": messages[-1]["id"],
            "msg_count": total_msgs,
            "total_messages": total_msgs,
            "formatted_snippet": format_snippet_messages(messages),
            "cluster_count": 1,
        }

    # Retrieve or compute chunk embeddings
    chunks = ensure_thread_chunks_embedded(db_path, thread_id, chat_id, content_hash, config)
    if not chunks:
        # Fallback to preview/full thread if chunk embedding unavailable
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "no_chunk_embeddings",
            "score": 0.0,
            "start_msg_id": messages[0]["id"],
            "end_msg_id": messages[-1]["id"],
            "msg_count": total_msgs,
            "total_messages": total_msgs,
            "formatted_snippet": format_snippet_messages(messages),
            "cluster_count": 0,
        }

    # Score each 5-message chunk against query vector
    scored_chunks = []
    for c in chunks:
        c_vec = c.get("vector")
        if c_vec:
            sim = dot_product(query_vec, c_vec)
            scored_chunks.append({
                "chunk": c,
                "score": float(sim)
            })

    if not scored_chunks:
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "vector_calculation_error",
            "score": 0.0,
            "start_msg_id": messages[0]["id"],
            "end_msg_id": messages[-1]["id"],
            "msg_count": total_msgs,
            "total_messages": total_msgs,
            "formatted_snippet": format_snippet_messages(messages),
            "cluster_count": 0,
        }

    # Match thresholding
    threshold = min_score if min_score is not None else 0.50
    matched = [sc for sc in scored_chunks if sc["score"] >= threshold]

    # If no chunk strictly crossed threshold, pick the single top-scoring chunk if reasonable
    if not matched:
        best_sc = max(scored_chunks, key=lambda x: x["score"])
        if best_sc["score"] >= 0.35:
            matched = [best_sc]
        else:
            return {
                "thread_id": thread_id,
                "is_full_thread": True,
                "reason": "low_similarity",
                "score": round(best_sc["score"], 4),
                "start_msg_id": messages[0]["id"],
                "end_msg_id": messages[-1]["id"],
                "msg_count": total_msgs,
                "total_messages": total_msgs,
                "formatted_snippet": format_snippet_messages(messages),
                "cluster_count": 0,
            }

    # Build expanded context windows (+/- context_window messages)
    windows = []
    for sc in matched:
        c = sc["chunk"]
        w_start = max(0, c["start_msg_idx"] - context_window)
        w_end = min(total_msgs - 1, c["end_msg_idx"] + context_window)
        windows.append((w_start, w_end))

    # Merge overlapping or close clusters
    merged_clusters = merge_cluster_windows(windows, merge_gap=2)

    top_chunk_score = max(sc["score"] for sc in matched)

    # Multi-cluster rule requested by user:
    # If there are multiple distant clusters across the thread, load full thread!
    if len(merged_clusters) > 1:
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "multi_cluster_fallback",
            "score": round(top_chunk_score, 4),
            "start_msg_id": messages[0]["id"],
            "end_msg_id": messages[-1]["id"],
            "msg_count": total_msgs,
            "total_messages": total_msgs,
            "formatted_snippet": format_snippet_messages(messages),
            "cluster_count": len(merged_clusters),
        }

    # Single localized cluster
    c_start, c_end = merged_clusters[0]
    sliced_msgs = messages[c_start : c_end + 1]

    # If the single cluster spans almost the entire thread (>= 80%), treat as full thread
    if len(sliced_msgs) >= int(total_msgs * 0.8):
        return {
            "thread_id": thread_id,
            "is_full_thread": True,
            "reason": "cluster_covers_full_thread",
            "score": round(top_chunk_score, 4),
            "start_msg_id": messages[0]["id"],
            "end_msg_id": messages[-1]["id"],
            "msg_count": total_msgs,
            "total_messages": total_msgs,
            "formatted_snippet": format_snippet_messages(messages),
            "cluster_count": 1,
        }

    return {
        "thread_id": thread_id,
        "is_full_thread": False,
        "reason": "single_cluster",
        "score": round(top_chunk_score, 4),
        "start_msg_id": sliced_msgs[0]["id"],
        "end_msg_id": sliced_msgs[-1]["id"],
        "start_idx": c_start,
        "end_idx": c_end,
        "msg_count": len(sliced_msgs),
        "total_messages": total_msgs,
        "formatted_snippet": format_snippet_messages(sliced_msgs),
        "cluster_count": 1,
    }
