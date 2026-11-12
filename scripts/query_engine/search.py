"""Message and thread search operations (FTS5 full-text and vector semantic)."""

import sqlite3
from typing import List, Dict, Any, Optional

from .formatters import format_message_text

try:
    from vector_indexer import search_semantic, search_semantic_batch
except ImportError:
    search_semantic = None
    search_semantic_batch = None


def get_search_messages(
    db_path: str,
    query: str,
    limit: int = 15,
    chat_id: Optional[str] = None,
    sender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search individual messages using FTS5 with optional sender filter."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
    if not clean_q:
        conn.close()
        return []

    terms = clean_q.split()
    fts_query = " AND ".join(f'"{t}"' for t in terms)

    try:
        sql = """
        SELECT mf.message_id, mf.chat_id, coalesce(c.chat_name, mf.chat_id) as chat_name,
               mf.date, mf.sender, mf.thread_id, mf.text
        FROM messages_fts mf
        LEFT JOIN chats c ON mf.chat_id = c.chat_id
        WHERE messages_fts MATCH ?
        """
        p: List[Any] = [fts_query]
        if chat_id:
            sql += " AND mf.chat_id = ? "
            p.append(chat_id)
        if sender:
            sql += " AND mf.sender LIKE ? "
            p.append(f"%{sender}%")
        sql += " ORDER BY rank LIMIT ?; "
        p.append(limit)

        cur.execute(sql, p)
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        sql = """
        SELECT m.id, m.chat_id, coalesce(c.chat_name, m.chat_id), m.date, m.sender, m.thread_id, m.text
        FROM messages m
        LEFT JOIN chats c ON m.chat_id = c.chat_id
        WHERE m.text LIKE ?
        """
        p = [f"%{clean_q}%"]
        if chat_id:
            sql += " AND m.chat_id = ? "
            p.append(chat_id)
        if sender:
            sql += " AND m.sender LIKE ? "
            p.append(f"%{sender}%")
        sql += " ORDER BY m.date DESC LIMIT ?; "
        p.append(limit)
        cur.execute(sql, p)
        rows = cur.fetchall()

    conn.close()
    return [
        {
            "message_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "date": r[3],
            "sender": r[4],
            "thread_id": r[5],
            "text": r[6]
        }
        for r in rows
    ]


def print_search_messages(query: str, rows: List[Dict[str, Any]]) -> None:
    """Print ASCII search results for individual messages."""
    print("\n" + "=" * 70)
    print(f"🔍 MESSAGE SEARCH: '{query}' ({len(rows)} matches)")
    print("=" * 70)
    if not rows:
        print("No matching messages found.")
        return

    for r in rows:
        c_label = f" | Chat: {r.get('chat_name', r.get('chat_id'))}" if r.get("chat_name") else ""
        fmt_text = format_message_text(r['text'], r.get('message_id'))
        print(f"\n[#{r['message_id']} | {r['date'][:16].replace('T', ' ')}{c_label}] {r['sender']} (Thread: {r['thread_id']}):")
        print(f"   {fmt_text}")


def get_search_threads_fts(
    db_path: str,
    query: str,
    limit: int = 5,
    chat_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search complete threads using FTS5."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
    terms = clean_q.split()
    fts_query = " AND ".join(f'"{t}"' for t in terms)

    try:
        sql = """
        SELECT tf.thread_id, tf.chat_id, coalesce(c.chat_name, tf.chat_id) as chat_name,
               tf.start_date, tf.participants, tf.dialogue_text
        FROM threads_fts tf
        LEFT JOIN chats c ON tf.chat_id = c.chat_id
        WHERE threads_fts MATCH ?
        """
        p: List[Any] = [fts_query]
        if chat_id:
            sql += " AND tf.chat_id = ? "
            p.append(chat_id)
        sql += " ORDER BY rank LIMIT ?; "
        p.append(limit)
        cur.execute(sql, p)
        rows = cur.fetchall()
    except Exception:
        sql = """
        SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.start_date, t.participants, t.dialogue_text
        FROM threads t
        LEFT JOIN chats c ON t.chat_id = c.chat_id
        WHERE t.dialogue_text LIKE ?
        """
        p = [f"%{clean_q}%"]
        if chat_id:
            sql += " AND t.chat_id = ? "
            p.append(chat_id)
        sql += " ORDER BY t.start_date DESC LIMIT ?; "
        p.append(limit)
        cur.execute(sql, p)
        rows = cur.fetchall()

    conn.close()
    return [
        {
            "thread_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "start_date": r[3],
            "participants": r[4],
            "dialogue_text": r[5]
        }
        for r in rows
    ]


def print_search_threads_fts(query: str, rows: List[Dict[str, Any]]) -> None:
    """Print ASCII search results for full dialogue threads."""
    print("\n" + "=" * 70)
    print(f"🔍 THREAD SEARCH (FTS5): '{query}' ({len(rows)} matches)")
    print("=" * 70)
    if not rows:
        print("No matching threads found.")
        return

    for i, r in enumerate(rows, 1):
        c_label = f" | Chat: {r.get('chat_name', r.get('chat_id'))}" if r.get("chat_name") else ""
        print(f"\n[{i}] Thread: {r['thread_id']}{c_label} | Date: {r['start_date'][:10]} | Parts: {r['participants']}")
        lines = r["dialogue_text"].split("\n")
        preview = "\n".join(lines[:6])
        if len(lines) > 6:
            preview += f"\n   ... ({len(lines) - 6} more messages in thread)"
        print(preview)
        print("-" * 50)


def get_semantic_batch_results(
    db_path: str,
    concepts: List[str],
    top_k: int = 5,
    chat_id: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Execute batch semantic search over multiple psychological concepts."""
    if search_semantic_batch is not None:
        return search_semantic_batch(db_path, concepts, top_k=top_k, chat_filter=chat_id)
    elif search_semantic is not None:
        return {c: search_semantic(db_path, c, top_k=top_k, chat_filter=chat_id) for c in concepts}
    else:
        print("[!] vector_indexer module not available for semantic queries.")
        return {c: [] for c in concepts}


def print_semantic_results(concept: str, results: List[Dict[str, Any]]) -> None:
    """Print ASCII view of vector semantic search results."""
    print("\n" + "=" * 70)
    print(f"🧠 SEMANTIC CONCEPT MATCHES: '{concept}'")
    print("=" * 70)
    if not results:
        print("No semantic matches found.")
        return

    for i, res in enumerate(results, 1):
        c_label = f" | Chat: {res.get('chat_name', res.get('chat_id'))}" if res.get("chat_name") else ""
        print(f"\n[{i}] Thread: {res['thread_id']}{c_label} | Date: {res['start_date'][:10]} | Relevance Score: {res['score']}")
        print(f"Participants: {res['participants']}")
        lines = res["dialogue_text"].split("\n")
        preview = "\n".join(lines[:6])
        if len(lines) > 6:
            preview += f"\n   ... ({len(lines) - 6} more messages in thread)"
        print(preview)
        print("-" * 50)
