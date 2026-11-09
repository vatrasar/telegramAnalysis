#!/usr/bin/env python3
"""
Telegram Multi-Chat Database Builder & Thread Disentangler.
Converts one or more Telegram desktop export JSON files into an analytical SQLite database
with conversation threads reconstructed via reply DAGs, anchor resolution,
and forward burst propagation (RAT-FBP).

Supports multi-file workflows:
- Multiple chats with different people stored cleanly in the same database without collisions.
- Merging multi-part export files from the same chat.
- Incremental imports without wiping existing chats (unless --clean is passed).
"""

import os
import sys
import glob
import json
import re
import sqlite3
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

BURST_THRESHOLD_SECONDS = 180       # 3 minutes: burst continuation threshold
INFERRED_RESPONSE_SECONDS = 3600    # 60 minutes: inferred response without explicit quote
SESSION_GAP_SECONDS = 7200          # 2 hours: silence threshold for new conversation session
LONG_SILENCE_SECONDS = 86400        # 24 hours: threshold for relationship silence analysis


def extract_text(raw_text: Any) -> str:
    """Extract plain text from Telegram JSON text field (string or rich-text list)."""
    if isinstance(raw_text, str):
        return raw_text.strip()
    elif isinstance(raw_text, list):
        parts = []
        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts).strip()
    return ""


def parse_iso_date(date_str: str) -> Tuple[datetime, int]:
    """Parse ISO date string and return datetime object and unix epoch timestamp."""
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        clean = date_str.replace("Z", "").replace(" ", "T")
        dt = datetime.fromisoformat(clean)
    return dt, int(dt.timestamp())


def derive_chat_id(data: Dict[str, Any], filepath: str, explicit_id: Optional[str] = None) -> str:
    """Generate a clean, collision-free chat identifier."""
    if explicit_id:
        clean = re.sub(r"[^\w]+", "_", explicit_id).strip("_").lower()
        return clean if clean.startswith("c_") else f"c_{clean}"

    raw_id = data.get("id")
    if raw_id is not None and str(raw_id).strip() != "":
        clean_id = str(raw_id).strip().replace("-", "m")
        return f"c_{clean_id}"

    # Fallback to sanitized filename stem
    base = os.path.splitext(os.path.basename(filepath))[0]
    clean_stem = re.sub(r"[^\w]+", "_", base).strip("_").lower()
    return f"c_{clean_stem}" if clean_stem else "c_default"


def create_schema(conn: sqlite3.Connection):
    """Initialize relational and FTS5 tables in SQLite with multi-chat support."""
    cur = conn.cursor()

    # Chats catalog
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id TEXT PRIMARY KEY,
        chat_name TEXT NOT NULL,
        chat_type TEXT,
        source_files TEXT NOT NULL,
        total_messages INTEGER NOT NULL,
        total_threads INTEGER NOT NULL,
        start_date TEXT,
        end_date TEXT
    );
    """)

    # Metadata table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # Messages table (composite primary key on chat_id + message id)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        chat_id TEXT NOT NULL,
        id INTEGER NOT NULL,
        date TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        sender TEXT NOT NULL,
        sender_id TEXT,
        reply_to_id INTEGER,
        thread_id TEXT NOT NULL,
        parent_id INTEGER,
        link_type TEXT NOT NULL,
        text TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        word_count INTEGER NOT NULL,
        PRIMARY KEY (chat_id, id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_thread ON messages(chat_id, thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_sender ON messages(chat_id, sender);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_reply ON messages(chat_id, reply_to_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread_global ON messages(thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts_global ON messages(timestamp);")

    # Threads table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        anchor_message_id INTEGER,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        start_timestamp INTEGER NOT NULL,
        end_timestamp INTEGER NOT NULL,
        duration_seconds INTEGER NOT NULL,
        message_count INTEGER NOT NULL,
        participants TEXT NOT NULL,
        initiator TEXT NOT NULL,
        gap_before_seconds INTEGER,
        dialogue_text TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_chat ON threads(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_start ON threads(start_timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_gap ON threads(gap_before_seconds);")

    # Silence / Gaps table (calculated strictly within each individual chat)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS silence_gaps (
        gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        silence_start_date TEXT NOT NULL,
        silence_end_date TEXT NOT NULL,
        silence_duration_seconds INTEGER NOT NULL,
        silence_duration_hours REAL NOT NULL,
        last_sender TEXT NOT NULL,
        initiator TEXT NOT NULL,
        after_thread_id TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gaps_chat ON silence_gaps(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gaps_duration ON silence_gaps(silence_duration_seconds);")

    # Full-Text Search (FTS5) for messages
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message_id UNINDEXED,
        chat_id UNINDEXED,
        date UNINDEXED,
        sender UNINDEXED,
        thread_id UNINDEXED,
        text,
        tokenize = 'unicode61'
    );
    """)

    # Full-Text Search (FTS5) for threads
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
        thread_id UNINDEXED,
        chat_id UNINDEXED,
        start_date UNINDEXED,
        participants UNINDEXED,
        dialogue_text,
        tokenize = 'unicode61'
    );
    """)

    conn.commit()


def disentangle_threads(
    messages: List[Dict[str, Any]],
    chat_id: str,
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Apply Reply-Anchored Threading with Forward Burst Propagation (RAT-FBP)
    scoped to a single chat stream.
    """
    valid_msgs = []
    for m in messages:
        if m.get("type") != "message":
            continue
        text = extract_text(m.get("text", ""))
        if not text:
            media_type = m.get("media_type") or m.get("photo") or m.get("file")
            if media_type:
                text = f"[{m.get('media_type', 'Media/Attachment')}]"
            else:
                continue

        sender = m.get("from") or m.get("actor") or "Unknown"
        sender_id = str(m.get("from_id") or "")
        msg_id = m.get("id")
        date_str = m.get("date")

        reply_to_id = m.get("reply_to_message_id")
        if not reply_to_id and isinstance(m.get("reply_to"), dict):
            reply_to_id = m.get("reply_to", {}).get("reply_to_message_id")

        if msg_id is None or not date_str:
            continue

        dt, ts = parse_iso_date(date_str)
        valid_msgs.append({
            "chat_id": chat_id,
            "id": int(msg_id),
            "date": date_str,
            "datetime": dt,
            "timestamp": ts,
            "sender": sender,
            "sender_id": sender_id,
            "reply_to_id": int(reply_to_id) if reply_to_id else None,
            "text": text,
            "char_count": len(text),
            "word_count": len(text.split())
        })

    valid_msgs.sort(key=lambda x: x["timestamp"])
    msg_dict = {m["id"]: m for m in valid_msgs}

    # First pass: establish parentage & link types
    last_msg_per_sender: Dict[str, int] = {}
    last_msg_overall: Optional[Dict[str, Any]] = None

    for m in valid_msgs:
        m_id = m["id"]
        ts = m["timestamp"]
        sender = m["sender"]
        reply_to = m["reply_to_id"]

        parent_id: Optional[int] = None
        link_type = "root"

        gap_before = ts - last_msg_overall["timestamp"] if last_msg_overall else 0
        m["gap_before"] = gap_before

        if reply_to and reply_to in msg_dict:
            parent_id = reply_to
            link_type = "explicit_reply"
        elif last_msg_overall and last_msg_overall["sender"] == sender and (ts - last_msg_overall["timestamp"] <= burst_threshold):
            parent_id = last_msg_overall["id"]
            link_type = "burst_continuation"
        elif (
            sender in last_msg_per_sender
            and (ts - msg_dict[last_msg_per_sender[sender]]["timestamp"] <= burst_threshold)
        ):
            parent_id = last_msg_per_sender[sender]
            link_type = "burst_continuation"
        elif last_msg_overall and gap_before <= inferred_gap:
            parent_id = last_msg_overall["id"]
            link_type = "inferred_response"
        else:
            link_type = "session_root" if gap_before >= session_gap else "topic_root"
            parent_id = None

        m["parent_id"] = parent_id
        m["link_type"] = link_type
        last_msg_per_sender[sender] = m_id
        last_msg_overall = m

    # Second pass: Thread assignment & Topic clustering
    thread_map: Dict[int, str] = {}
    anchor_map: Dict[str, Optional[int]] = {}
    thread_prefix = f"{chat_id}_t"
    session_prefix = f"{chat_id}_s"

    for m in valid_msgs:
        m_id = m["id"]
        p_id = m["parent_id"]
        l_type = m["link_type"]

        if l_type == "explicit_reply" and p_id:
            parent_m = msg_dict[p_id]
            if parent_m["link_type"] in ("explicit_reply", "inferred_response") or (p_id in thread_map and thread_map[p_id].startswith(thread_prefix)):
                t_id = thread_map[p_id]
            else:
                t_id = f"{thread_prefix}{p_id}"
                anchor_map[t_id] = p_id
        elif p_id and p_id in thread_map:
            t_id = thread_map[p_id]
        else:
            t_id = f"{session_prefix}{m_id}"
            anchor_map[t_id] = None

        thread_map[m_id] = t_id
        m["thread_id"] = t_id

    threads_data: Dict[str, Dict[str, Any]] = {}
    for m in valid_msgs:
        t_id = m["thread_id"]
        if t_id not in threads_data:
            threads_data[t_id] = {
                "thread_id": t_id,
                "anchor_id": anchor_map.get(t_id),
                "messages": []
            }
        threads_data[t_id]["messages"].append(m)

    return valid_msgs, threads_data


def insert_chat_data(
    conn: sqlite3.Connection,
    chat_id: str,
    chat_name: str,
    chat_type: str,
    source_files: List[str],
    raw_messages: List[Dict[str, Any]],
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS
) -> Tuple[int, int, int]:
    """Process and insert a single chat's messages, threads, and silence gaps."""
    processed_msgs, threads_data = disentangle_threads(
        raw_messages,
        chat_id,
        burst_threshold=burst_threshold,
        inferred_gap=inferred_gap,
        session_gap=session_gap
    )
    if not processed_msgs:
        print(f"[!] Warning: No valid messages found for chat '{chat_name}' ({chat_id}). Skipping.")
        return 0, 0, 0

    cur = conn.cursor()

    # Clean existing data for this chat_id to ensure clean idempotency
    cur.execute("DELETE FROM chats WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM messages WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM threads WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM silence_gaps WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM messages_fts WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM threads_fts WHERE chat_id = ?;", (chat_id,))

    # If vector table exists, clean old embeddings for this chat
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_embeddings';")
    if cur.fetchone()[0] > 0:
        cur.execute("DELETE FROM thread_embeddings WHERE chat_id = ?;", (chat_id,))

    # If triage table exists, clean old triage entries for this chat
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] > 0:
        cur.execute("DELETE FROM thread_triage WHERE chat_id = ?;", (chat_id,))

    msg_dict = {m["id"]: m for m in processed_msgs}
    start_date = processed_msgs[0]["date"]
    end_date = processed_msgs[-1]["date"]

    # 1. Insert messages
    msg_rows = [
        (
            m["chat_id"], m["id"], m["date"], m["timestamp"], m["sender"], m["sender_id"],
            m["reply_to_id"], m["thread_id"], m["parent_id"], m["link_type"],
            m["text"], m["char_count"], m["word_count"]
        )
        for m in processed_msgs
    ]
    cur.executemany("""
    INSERT INTO messages (chat_id, id, date, timestamp, sender, sender_id, reply_to_id, thread_id, parent_id, link_type, text, char_count, word_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, msg_rows)

    fts_rows = [
        (m["id"], m["chat_id"], m["date"], m["sender"], m["thread_id"], m["text"])
        for m in processed_msgs
    ]
    cur.executemany("""
    INSERT INTO messages_fts (message_id, chat_id, date, sender, thread_id, text)
    VALUES (?, ?, ?, ?, ?, ?);
    """, fts_rows)

    # 2. Compile and insert threads & silence gaps
    thread_rows = []
    thread_fts_rows = []
    gap_rows = []

    sorted_threads = sorted(threads_data.values(), key=lambda x: x["messages"][0]["timestamp"])
    prev_thread_end_ts: Optional[int] = None
    prev_thread_last_sender: Optional[str] = None

    for t_obj in sorted_threads:
        t_id = t_obj["thread_id"]
        msgs = t_obj["messages"]
        anchor_id = t_obj["anchor_id"]

        first_msg = msgs[0]
        last_msg = msgs[-1]
        t_start_date = first_msg["date"]
        t_start_ts = first_msg["timestamp"]
        t_end_date = last_msg["date"]
        t_end_ts = last_msg["timestamp"]
        duration = t_end_ts - t_start_ts
        initiator = first_msg["sender"]

        all_senders = {m["sender"] for m in msgs}
        if anchor_id and anchor_id in msg_dict:
            all_senders.add(msg_dict[anchor_id]["sender"])
        participants = sorted(list(all_senders))

        gap_before = None
        if prev_thread_end_ts is not None:
            gap_before = t_start_ts - prev_thread_end_ts
            if gap_before >= LONG_SILENCE_SECONDS:
                duration_hrs = round(gap_before / 3600.0, 1)
                gap_rows.append((
                    chat_id,
                    datetime.fromtimestamp(prev_thread_end_ts).isoformat(),
                    t_start_date,
                    gap_before,
                    duration_hrs,
                    prev_thread_last_sender or "Unknown",
                    initiator,
                    t_id
                ))

        # Build formatted dialogue text with anchor message at top if present
        dialogue_lines = []
        if anchor_id and anchor_id in msg_dict:
            anc = msg_dict[anchor_id]
            dialogue_lines.append(f"[Anchor #{anc['id']} | {anc['date'][:16]}] {anc['sender']}: {anc['text']}")
            dialogue_lines.append("----------------------------------------")

        for m in msgs:
            prefix = ""
            if m["link_type"] == "explicit_reply":
                prefix = f"[Reply to #{m['parent_id']}] "
            elif m["link_type"] == "burst_continuation":
                prefix = "[+] "
            dialogue_lines.append(f"[{m['date'][:16]}] {m['sender']}: {prefix}{m['text']}")

        dialogue_text = "\n".join(dialogue_lines)

        thread_rows.append((
            t_id, chat_id, anchor_id, t_start_date, t_end_date, t_start_ts, t_end_ts,
            duration, len(msgs), ",".join(participants), initiator,
            gap_before, dialogue_text
        ))

        thread_fts_rows.append((
            t_id, chat_id, t_start_date, ",".join(participants), dialogue_text
        ))

        prev_thread_end_ts = max(prev_thread_end_ts or 0, t_end_ts)
        prev_thread_last_sender = last_msg["sender"]

    cur.executemany("""
    INSERT INTO threads (thread_id, chat_id, anchor_message_id, start_date, end_date, start_timestamp, end_timestamp, duration_seconds, message_count, participants, initiator, gap_before_seconds, dialogue_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, thread_rows)

    cur.executemany("""
    INSERT INTO threads_fts (thread_id, chat_id, start_date, participants, dialogue_text)
    VALUES (?, ?, ?, ?, ?);
    """, thread_fts_rows)

    cur.executemany("""
    INSERT INTO silence_gaps (chat_id, silence_start_date, silence_end_date, silence_duration_seconds, silence_duration_hours, last_sender, initiator, after_thread_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, gap_rows)

    # 3. Insert or update chats catalog
    cur.execute("""
    INSERT INTO chats (chat_id, chat_name, chat_type, source_files, total_messages, total_threads, start_date, end_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        chat_id, chat_name, chat_type, ", ".join(source_files),
        len(processed_msgs), len(threads_data), start_date, end_date
    ))

    return len(processed_msgs), len(threads_data), len(gap_rows)


def build_databases(
    input_patterns: List[str],
    db_path: str,
    clean: bool = False,
    chat_id_override: Optional[str] = None,
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS
):
    """
    Parse one or more JSON export files and build/update the SQLite multi-chat analytical database.
    """
    resolved_files: List[str] = []
    for pat in input_patterns:
        if os.path.isdir(pat):
            found = glob.glob(os.path.join(pat, "*.json"))
            resolved_files.extend(sorted(found))
        else:
            expanded = glob.glob(pat)
            if expanded:
                resolved_files.extend(sorted(expanded))
            elif os.path.exists(pat):
                resolved_files.append(pat)

    # Deduplicate while preserving order
    unique_files = []
    seen_files = set()
    for f in resolved_files:
        abs_f = os.path.abspath(f)
        if abs_f not in seen_files:
            seen_files.add(abs_f)
            unique_files.append(f)

    if not unique_files:
        print(f"[!] Error: No JSON files found matching patterns: {input_patterns}")
        sys.exit(1)

    print(f"[*] Discovered {len(unique_files)} export file(s) for ingestion.")

    if clean and os.path.exists(db_path):
        print(f"[*] --clean specified: Removing existing database at {db_path}")
        os.remove(db_path)

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    # Read and group files by resolved chat_id
    chats_grouped: Dict[str, Dict[str, Any]] = {}

    for filepath in unique_files:
        print(f"[*] Reading: {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[!] Warning: Could not read {filepath}: {e}. Skipping.")
            continue

        c_id = derive_chat_id(data, filepath, chat_id_override if len(unique_files) == 1 else None)
        c_name = data.get("name") or os.path.splitext(os.path.basename(filepath))[0]
        c_type = data.get("type", "personal_chat")
        msgs = data.get("messages", [])

        if c_id not in chats_grouped:
            chats_grouped[c_id] = {
                "chat_id": c_id,
                "chat_name": c_name,
                "chat_type": c_type,
                "source_files": [filepath],
                "messages": list(msgs)
            }
        else:
            # Merge multi-part files for the same chat
            chats_grouped[c_id]["source_files"].append(filepath)
            chats_grouped[c_id]["messages"].extend(msgs)

    total_all_msgs = 0
    total_all_threads = 0
    total_all_gaps = 0

    print(f"[*] Grouped into {len(chats_grouped)} distinct chat stream(s). Disentangling...")

    for c_id, chat_info in chats_grouped.items():
        # Deduplicate messages by ID within the same chat (handles multi-part exports)
        raw_msgs = chat_info["messages"]
        seen_msg_ids: Set[Any] = set()
        deduped_msgs = []
        for m in raw_msgs:
            m_id = m.get("id")
            if m_id is not None:
                if m_id not in seen_msg_ids:
                    seen_msg_ids.add(m_id)
                    deduped_msgs.append(m)
            else:
                deduped_msgs.append(m)

        print(f"\n---> Ingesting Chat '{chat_info['chat_name']}' (ID: {c_id})")
        print(f"     Source files: {', '.join(chat_info['source_files'])}")
        print(f"     Raw items: {len(raw_msgs)} (Deduped: {len(deduped_msgs)})")

        n_msgs, n_threads, n_gaps = insert_chat_data(
            conn=conn,
            chat_id=c_id,
            chat_name=chat_info["chat_name"],
            chat_type=chat_info["chat_type"],
            source_files=chat_info["source_files"],
            raw_messages=deduped_msgs,
            burst_threshold=burst_threshold,
            inferred_gap=inferred_gap,
            session_gap=session_gap
        )

        total_all_msgs += n_msgs
        total_all_threads += n_threads
        total_all_gaps += n_gaps

        print(f"     [+] Disentangled: {n_msgs} messages | {n_threads} threads | {n_gaps} silences (>24h)")

    # Update summary metadata
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM messages;")
    db_total_msgs = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM threads;")
    db_total_threads = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM chats;")
    db_total_chats = cur.fetchone()[0]

    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", ("total_chats", str(db_total_chats)))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", ("total_messages", str(db_total_msgs)))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", ("total_threads", str(db_total_threads)))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", ("schema_version", "2.0"))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", ("last_updated", datetime.now().isoformat()))

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print(f"✨ Successfully built/updated database at: {db_path}")
    print(f"   - Total Indexed Chats:    {db_total_chats}")
    print(f"   - Total Messages in DB:   {db_total_msgs}")
    print(f"   - Total Threads in DB:    {db_total_threads}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build analytical SQLite DB from one or more Telegram chat exports (multi-chat support)."
    )
    parser.add_argument(
        "json_files",
        nargs="+",
        help="Path(s) to Telegram export JSON files or wildcards (e.g. rozmowy/*.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="chat.db",
        help="Output SQLite database path (default: chat.db)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean/recreate database from scratch, removing existing data"
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        help="Explicitly specify or override chat_id for imported file (single chat only)"
    )
    parser.add_argument(
        "--burst-threshold",
        type=int,
        default=BURST_THRESHOLD_SECONDS,
        help=f"Max gap in seconds for burst continuation by same sender (default: {BURST_THRESHOLD_SECONDS})"
    )
    parser.add_argument(
        "--inferred-gap",
        type=int,
        default=INFERRED_RESPONSE_SECONDS,
        help=f"Max gap in seconds for inferred reply between conversation turns (default: {INFERRED_RESPONSE_SECONDS})"
    )
    parser.add_argument(
        "--session-gap",
        type=int,
        default=SESSION_GAP_SECONDS,
        help=f"Min gap in seconds to partition into a new conversation session (default: {SESSION_GAP_SECONDS})"
    )
    args = parser.parse_args()

    build_databases(
        input_patterns=args.json_files,
        db_path=args.output,
        clean=args.clean,
        chat_id_override=args.chat_id,
        burst_threshold=args.burst_threshold,
        inferred_gap=args.inferred_gap,
        session_gap=args.session_gap
    )
