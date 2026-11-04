#!/usr/bin/env python3
"""
Telegram Chat Database Builder & Thread Disentangler.
Converts Telegram desktop export (result.json) into an analytical SQLite database
with conversation threads reconstructed via reply DAGs, anchor resolution,
and forward burst propagation.
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

BURST_THRESHOLD_SECONDS = 180  # 3 minutes: burst continuation threshold
SESSION_GAP_SECONDS = 7200     # 2 hours: silence threshold for new conversation session
LONG_SILENCE_SECONDS = 86400   # 24 hours: threshold for relationship silence analysis


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


def create_schema(conn: sqlite3.Connection):
    """Initialize relational and FTS5 tables in SQLite."""
    cur = conn.cursor()
    
    # Metadata table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # Messages table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
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
        word_count INTEGER NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_reply ON messages(reply_to_id);")

    # Threads table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_start ON threads(start_timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_gap ON threads(gap_before_seconds);")

    # Silence / Gaps table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS silence_gaps (
        gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
        silence_start_date TEXT NOT NULL,
        silence_end_date TEXT NOT NULL,
        silence_duration_seconds INTEGER NOT NULL,
        silence_duration_hours REAL NOT NULL,
        last_sender TEXT NOT NULL,
        initiator TEXT NOT NULL,
        after_thread_id TEXT
    );
    """)

    # Full-Text Search (FTS5) for fast keyword search with BM25
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message_id UNINDEXED,
        date UNINDEXED,
        sender UNINDEXED,
        thread_id UNINDEXED,
        text,
        tokenize = 'unicode61'
    );
    """)

    # FTS for threads (allows searching whole conversation threads directly)
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
        thread_id UNINDEXED,
        start_date UNINDEXED,
        participants UNINDEXED,
        dialogue_text,
        tokenize = 'unicode61'
    );
    """)

    conn.commit()


def disentangle_threads(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Apply Reply-Anchored Threading with Forward Burst Propagation (RAT-FBP).
    Disentangles interleaved multi-topic chats where participants juggle many topics simultaneously.
    """
    # 1. Normalize and sort valid messages chronologically
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

    # 2. First pass: establish parentage & link types
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
        elif last_msg_overall and last_msg_overall["sender"] == sender and (ts - last_msg_overall["timestamp"] <= BURST_THRESHOLD_SECONDS):
            # Same sender sent their previous message within burst window
            parent_id = last_msg_overall["id"]
            link_type = "burst_continuation"
        elif sender in last_msg_per_sender:
            prev_id = last_msg_per_sender[sender]
            if ts - msg_dict[prev_id]["timestamp"] <= BURST_THRESHOLD_SECONDS:
                parent_id = prev_id
                link_type = "burst_continuation"
        elif last_msg_overall and gap_before <= 300:
            parent_id = last_msg_overall["id"]
            link_type = "inferred_response"
        else:
            link_type = "session_root" if gap_before >= SESSION_GAP_SECONDS else "topic_root"
            parent_id = None

        m["parent_id"] = parent_id
        m["link_type"] = link_type
        last_msg_per_sender[sender] = m_id
        last_msg_overall = m

    # 3. Second pass: Thread assignment & Topic clustering
    # Each explicit reply to an original message defines a focused thread topic for that anchor message.
    # Burst continuations inherit their parent's thread topic.
    thread_map: Dict[int, str] = {}
    anchor_map: Dict[str, Optional[int]] = {}

    for m in valid_msgs:
        m_id = m["id"]
        p_id = m["parent_id"]
        l_type = m["link_type"]

        if l_type == "explicit_reply" and p_id:
            parent_m = msg_dict[p_id]
            # If parent was itself an explicit reply or in an existing thread_topic, continue it
            if parent_m["link_type"] in ("explicit_reply", "inferred_response") or (p_id in thread_map and thread_map[p_id].startswith("thread_")):
                t_id = thread_map[p_id]
            else:
                # Parent was an original message/burst; this reply starts a focused thread on p_id
                t_id = f"thread_{p_id}"
                anchor_map[t_id] = p_id
            thread_map[m_id] = t_id
        elif p_id and p_id in thread_map:
            t_id = thread_map[p_id]
            thread_map[m_id] = t_id
        else:
            # Standalone root or session root
            t_id = f"session_{m_id}"
            thread_map[m_id] = t_id
            anchor_map[t_id] = None

        m["thread_id"] = t_id

    # 4. Compile Thread objects with anchor messages included in the transcript
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


def build_database(json_path: str, db_path: str):
    """Parse JSON and construct the complete SQLite analytical database."""
    print(f"[*] Reading export file: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chat_name = data.get("name", "Telegram Chat")
    raw_messages = data.get("messages", [])
    print(f"[*] Loaded {len(raw_messages)} raw items. Disentangling threads...")

    processed_msgs, threads_data = disentangle_threads(raw_messages)
    print(f"[*] Disentangled into {len(processed_msgs)} messages across {len(threads_data)} distinct threads.")

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    create_schema(conn)
    cur = conn.cursor()

    msg_dict = {m["id"]: m for m in processed_msgs}

    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("chat_name", chat_name))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("total_messages", str(len(processed_msgs))))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("total_threads", str(len(threads_data))))

    # Insert messages & FTS
    msg_rows = []
    fts_rows = []

    for m in processed_msgs:
        msg_rows.append((
            m["id"], m["date"], m["timestamp"], m["sender"], m["sender_id"],
            m["reply_to_id"], m["thread_id"], m["parent_id"], m["link_type"],
            m["text"], m["char_count"], m["word_count"]
        ))
        fts_rows.append((
            m["id"], m["date"], m["sender"], m["thread_id"], m["text"]
        ))

    cur.executemany("""
    INSERT INTO messages (id, date, timestamp, sender, sender_id, reply_to_id, thread_id, parent_id, link_type, text, char_count, word_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, msg_rows)

    cur.executemany("""
    INSERT INTO messages_fts (message_id, date, sender, thread_id, text)
    VALUES (?, ?, ?, ?, ?);
    """, fts_rows)

    # Compile Threads and Silence Gaps
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
        start_date = first_msg["date"]
        start_ts = first_msg["timestamp"]
        end_date = last_msg["date"]
        end_ts = last_msg["timestamp"]
        duration = end_ts - start_ts
        initiator = first_msg["sender"]
        
        all_senders = {m["sender"] for m in msgs}
        if anchor_id and anchor_id in msg_dict:
            all_senders.add(msg_dict[anchor_id]["sender"])
        participants = sorted(list(all_senders))

        gap_before = None
        if prev_thread_end_ts is not None:
            gap_before = start_ts - prev_thread_end_ts
            if gap_before >= LONG_SILENCE_SECONDS:
                duration_hrs = round(gap_before / 3600.0, 1)
                gap_rows.append((
                    datetime.fromtimestamp(prev_thread_end_ts).isoformat(),
                    start_date,
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
            t_id, anchor_id, start_date, end_date, start_ts, end_ts,
            duration, len(msgs), ",".join(participants), initiator,
            gap_before, dialogue_text
        ))

        thread_fts_rows.append((
            t_id, start_date, ",".join(participants), dialogue_text
        ))

        prev_thread_end_ts = max(prev_thread_end_ts or 0, end_ts)
        prev_thread_last_sender = last_msg["sender"]

    cur.executemany("""
    INSERT INTO threads (thread_id, anchor_message_id, start_date, end_date, start_timestamp, end_timestamp, duration_seconds, message_count, participants, initiator, gap_before_seconds, dialogue_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, thread_rows)

    cur.executemany("""
    INSERT INTO threads_fts (thread_id, start_date, participants, dialogue_text)
    VALUES (?, ?, ?, ?);
    """, thread_fts_rows)

    cur.executemany("""
    INSERT INTO silence_gaps (silence_start_date, silence_end_date, silence_duration_seconds, silence_duration_hours, last_sender, initiator, after_thread_id)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, gap_rows)

    conn.commit()
    conn.close()
    print(f"[+] Successfully built SQLite database at: {db_path}")
    print(f"    - Messages: {len(msg_rows)}")
    print(f"    - Clean Disentangled Threads: {len(thread_rows)}")
    print(f"    - Long Silences (>24h): {len(gap_rows)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build analytical SQLite DB from Telegram chat export.")
    parser.add_argument("json_file", help="Path to Telegram export result.json")
    parser.add_argument("--output", "-o", default="chat_index.db", help="Output SQLite database path")
    args = parser.parse_args()

    build_database(args.json_file, args.output)
