"""Chat ingestion, database population, and delta tracking."""

import os
import sys
import glob
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

from common.text import compute_file_sha256
from db_engine.constants import (
    BURST_THRESHOLD_SECONDS,
    INFERRED_RESPONSE_SECONDS,
    SESSION_GAP_SECONDS,
    LONG_SILENCE_SECONDS,
    MAX_THREAD_MESSAGES,
    derive_chat_id,
)
from db_engine.schema import create_schema
from db_engine.threading import disentangle_threads


def insert_chat_data(
    conn: sqlite3.Connection,
    chat_id: str,
    chat_name: str,
    chat_type: str,
    source_files: List[str],
    raw_messages: List[Dict[str, Any]],
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS,
    max_thread_messages: int = MAX_THREAD_MESSAGES
) -> Tuple[int, int, int]:
    """Process and insert a single chat's messages, threads, and silence gaps."""
    processed_msgs, threads_data = disentangle_threads(
        raw_messages,
        chat_id,
        burst_threshold=burst_threshold,
        inferred_gap=inferred_gap,
        session_gap=session_gap,
        max_thread_messages=max_thread_messages
    )
    if not processed_msgs:
        print(f"[!] Warning: No valid messages found for chat '{chat_name}' ({chat_id}). Skipping.")
        return 0, 0, 0

    cur = conn.cursor()

    # Clean existing relational & FTS data for this chat_id to ensure clean idempotency
    cur.execute("DELETE FROM chats WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM messages WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM threads WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM silence_gaps WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM messages_fts WHERE chat_id = ?;", (chat_id,))
    cur.execute("DELETE FROM threads_fts WHERE chat_id = ?;", (chat_id,))

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

    prev_m: Optional[Dict[str, Any]] = None
    for m in processed_msgs:
        if prev_m is not None:
            gap_sec = m["timestamp"] - prev_m["timestamp"]
            if gap_sec >= LONG_SILENCE_SECONDS:
                duration_hrs = round(gap_sec / 3600.0, 1)
                gap_rows.append((
                    chat_id,
                    prev_m["date"],
                    m["date"],
                    gap_sec,
                    duration_hrs,
                    prev_m["sender"],
                    m["sender"],
                    m["thread_id"]
                ))
        prev_m = m

    sorted_threads = sorted(threads_data.values(), key=lambda x: x["messages"][0]["timestamp"])
    prev_thread_end_ts: Optional[int] = None

    for t_obj in sorted_threads:
        t_id = t_obj["thread_id"]
        parent_thread_id = t_obj.get("parent_thread_id")
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
        content_hash = hashlib.sha256(dialogue_text.encode("utf-8")).hexdigest()

        thread_rows.append((
            t_id, chat_id, parent_thread_id, anchor_id, t_start_date, t_end_date, t_start_ts, t_end_ts,
            duration, len(msgs), ",".join(participants), initiator,
            gap_before, dialogue_text, content_hash
        ))

        thread_fts_rows.append((
            t_id, chat_id, t_start_date, ",".join(participants), dialogue_text
        ))

        prev_thread_end_ts = max(prev_thread_end_ts or 0, t_end_ts)

    cur.executemany("""
    INSERT INTO threads (thread_id, chat_id, parent_thread_id, anchor_message_id, start_date, end_date, start_timestamp, end_timestamp, duration_seconds, message_count, participants, initiator, gap_before_seconds, dialogue_text, content_hash)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, thread_rows)

    cur.executemany("""
    INSERT INTO threads_fts (thread_id, chat_id, start_date, participants, dialogue_text)
    VALUES (?, ?, ?, ?, ?);
    """, thread_fts_rows)

    cur.executemany("""
    INSERT INTO silence_gaps (chat_id, silence_start_date, silence_end_date, silence_duration_seconds, silence_duration_hours, last_sender, initiator, after_thread_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, gap_rows)

    # 3. Invalidate stale embeddings & triage records
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_embeddings';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        DELETE FROM thread_embeddings 
        WHERE chat_id = ? 
          AND thread_id NOT IN (SELECT thread_id FROM threads WHERE chat_id = ?);
        """, (chat_id, chat_id))
        cur.execute("PRAGMA table_info(thread_embeddings);")
        te_cols = {c[1] for c in cur.fetchall()}
        if "content_hash" in te_cols:
            cur.execute("""
            DELETE FROM thread_embeddings
            WHERE chat_id = ?
              AND thread_id IN (
                  SELECT te.thread_id
                  FROM thread_embeddings te
                  JOIN threads t ON te.thread_id = t.thread_id
                  WHERE te.chat_id = ? AND (te.content_hash IS NULL OR te.content_hash != t.content_hash)
              );
            """, (chat_id, chat_id))

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        DELETE FROM thread_triage 
        WHERE chat_id = ? 
          AND thread_id NOT IN (SELECT thread_id FROM threads WHERE chat_id = ?);
        """, (chat_id, chat_id))
        cur.execute("PRAGMA table_info(thread_triage);")
        tr_cols = {c[1] for c in cur.fetchall()}
        if "content_hash" in tr_cols:
            cur.execute("""
            DELETE FROM thread_triage
            WHERE chat_id = ?
              AND thread_id IN (
                  SELECT tr.thread_id
                  FROM thread_triage tr
                  JOIN threads t ON tr.thread_id = t.thread_id
                  WHERE tr.chat_id = ? AND (tr.content_hash IS NULL OR tr.content_hash != t.content_hash)
              );
            """, (chat_id, chat_id))

    # 4. Insert or update chats catalog
    cur.execute("""
    INSERT INTO chats (chat_id, chat_name, chat_type, source_files, total_messages, total_threads, start_date, end_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        chat_id, chat_name, chat_type, ", ".join(source_files),
        len(processed_msgs), len(threads_data), start_date, end_date
    ))

    # 5. Update source_files_manifest
    max_id = max([m["id"] for m in processed_msgs]) if processed_msgs else None
    now_iso = datetime.now().isoformat()
    for sf in source_files:
        abs_sf = os.path.abspath(sf)
        if os.path.exists(abs_sf):
            f_size = os.path.getsize(abs_sf)
            f_mtime = datetime.fromtimestamp(os.path.getmtime(abs_sf)).isoformat()
            f_hash = compute_file_sha256(abs_sf)
            cur.execute("""
            INSERT OR REPLACE INTO source_files_manifest 
            (file_path, chat_id, file_hash, file_size, last_modified, message_count, max_message_id, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (abs_sf, chat_id, f_hash, f_size, f_mtime, len(processed_msgs), max_id, now_iso))

    cur.execute("UPDATE chat_descriptors SET needs_recheck = 1 WHERE chat_id = ?;", (chat_id,))

    return len(processed_msgs), len(threads_data), len(gap_rows)


def build_databases(
    input_patterns: List[str],
    db_path: str,
    clean: bool = False,
    chat_id_override: Optional[str] = None,
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS,
    max_thread_messages: int = MAX_THREAD_MESSAGES
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
            chats_grouped[c_id]["source_files"].append(filepath)
            chats_grouped[c_id]["messages"].extend(msgs)

    total_all_msgs = 0
    total_all_threads = 0
    total_all_gaps = 0

    print(f"[*] Grouped into {len(chats_grouped)} distinct chat stream(s). Disentangling...")

    for c_id, chat_info in chats_grouped.items():
        can_skip = False
        if not clean:
            cur = conn.cursor()
            cur.execute("SELECT total_messages, total_threads FROM chats WHERE chat_id = ?;", (c_id,))
            c_row = cur.fetchone()
            if c_row and c_row[0] > 0:
                all_files_match = True
                cur.execute("SELECT count(*) FROM source_files_manifest WHERE chat_id = ?;", (c_id,))
                manifest_count = cur.fetchone()[0]
                if manifest_count == len(chat_info["source_files"]):
                    for sf in chat_info["source_files"]:
                        abs_sf = os.path.abspath(sf)
                        if not os.path.exists(abs_sf):
                            all_files_match = False
                            break
                        cur.execute(
                            "SELECT file_hash, file_size FROM source_files_manifest WHERE file_path = ? AND chat_id = ?;",
                            (abs_sf, c_id)
                        )
                        mf = cur.fetchone()
                        if not mf:
                            all_files_match = False
                            break
                        expected_hash, expected_size = mf
                        current_size = os.path.getsize(abs_sf)
                        if current_size != expected_size:
                            all_files_match = False
                            break
                        current_hash = compute_file_sha256(abs_sf)
                        if current_hash != expected_hash:
                            all_files_match = False
                            break
                    if all_files_match:
                        can_skip = True

        if can_skip:
            print(f"\n---> [UNCHANGED] Chat '{chat_info['chat_name']}' (ID: {c_id})")
            print(f"     Source files match manifest. Skipping re-ingestion.")
            total_all_msgs += c_row[0]
            total_all_threads += c_row[1]
            continue

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

        print(f"\n---> [INGESTING] Chat '{chat_info['chat_name']}' (ID: {c_id})")
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
            session_gap=session_gap,
            max_thread_messages=max_thread_messages
        )

        total_all_msgs += n_msgs
        total_all_threads += n_threads
        total_all_gaps += n_gaps

        print(f"     [+] Disentangled: {n_msgs} messages | {n_threads} threads | {n_gaps} silences (>24h)")

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
