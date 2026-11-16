"""Inspection of individual threads, thread slices, and standalone messages."""

import math
import sqlite3
from typing import List, Dict, Any, Optional

from .formatters import format_message_text


def get_thread(
    db_path: str,
    identifier: str,
    chat_id: Optional[str] = None,
    full: bool = False,
    forward: bool = False,
    backward: bool = False
) -> Optional[Dict[str, Any]]:
    """Fetch full dialogue transcript of a thread by thread_id or message_id."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(threads);")
    cols = {c[1] for c in cur.fetchall()}
    has_parent = "parent_thread_id" in cols
    parent_col = ", t.parent_thread_id" if has_parent else ", NULL"

    target_thread_id = identifier
    cur.execute(f"""
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.anchor_message_id,
           t.start_date, t.end_date, t.message_count, t.participants, t.initiator, t.dialogue_text
           {parent_col}
    FROM threads t
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    WHERE t.thread_id = ?;
    """, (target_thread_id,))
    row = cur.fetchone()

    if not row:
        try:
            msg_id = int(identifier)
            sql = "SELECT thread_id, chat_id FROM messages WHERE id = ?"
            p: List[Any] = [msg_id]
            if chat_id:
                sql += " AND chat_id = ?"
                p.append(chat_id)
            cur.execute(sql, p)
            m_rows = cur.fetchall()
            if m_rows:
                target_thread_id = m_rows[0][0]
                cur.execute(f"""
                SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.anchor_message_id,
                       t.start_date, t.end_date, t.message_count, t.participants, t.initiator, t.dialogue_text
                       {parent_col}
                FROM threads t
                LEFT JOIN chats c ON t.chat_id = c.chat_id
                WHERE t.thread_id = ?;
                """, (target_thread_id,))
                row = cur.fetchone()
        except ValueError:
            pass

    if not row:
        conn.close()
        return None

    actual_tid = row[0]
    parent_tid = row[10]
    children: List[str] = []
    if has_parent:
        cur.execute("SELECT thread_id FROM threads WHERE parent_thread_id = ? ORDER BY start_timestamp ASC;", (actual_tid,))
        children = [r[0] for r in cur.fetchall()]

    chain_tids = [actual_tid]
    chain_mode = "single"

    if (full or forward or backward) and has_parent:
        # Walk up to root thread
        curr_tid = actual_tid
        while True:
            cur.execute("SELECT parent_thread_id FROM threads WHERE thread_id = ?;", (curr_tid,))
            p_row = cur.fetchone()
            if not p_row or not p_row[0]:
                break
            curr_tid = p_row[0]
        root_tid = curr_tid

        # Walk down from root to gather all child partitions in sequence
        full_chain = [root_tid]
        curr_p = root_tid
        while True:
            cur.execute("SELECT thread_id FROM threads WHERE parent_thread_id = ? ORDER BY start_timestamp ASC, start_date ASC;", (curr_p,))
            c_row = cur.fetchone()
            if not c_row:
                break
            full_chain.append(c_row[0])
            curr_p = c_row[0]

        try:
            cur_idx = full_chain.index(actual_tid)
        except ValueError:
            cur_idx = 0

        if full:
            chain_tids = full_chain
            chain_mode = "full"
        elif forward:
            chain_tids = full_chain[cur_idx:]
            chain_mode = "forward"
        elif backward:
            chain_tids = full_chain[:cur_idx + 1]
            chain_mode = "backward"

    is_multi_part = len(chain_tids) > 1

    # Fetch individual messages for the thread (or whole chain if full)
    placeholders = ",".join("?" for _ in chain_tids)
    cur.execute(f"""
    SELECT id, chat_id, date, sender, reply_to_id, text
    FROM messages
    WHERE thread_id IN ({placeholders})
    ORDER BY timestamp ASC, id ASC;
    """, chain_tids)
    msg_rows = cur.fetchall()
    thread_msgs = [
        {
            "id": mr[0],
            "chat_id": mr[1],
            "date": mr[2],
            "sender": mr[3],
            "reply_to_id": mr[4],
            "text": mr[5] or ""
        }
        for mr in msg_rows
    ]

    anchor_msg = None
    if row[3]:
        cur.execute("SELECT id, chat_id, date, sender, reply_to_id, text FROM messages WHERE id = ?", (row[3],))
        arow = cur.fetchone()
        if arow:
            anchor_msg = {
                "id": arow[0],
                "chat_id": arow[1],
                "date": arow[2],
                "sender": arow[3],
                "reply_to_id": arow[4],
                "text": arow[5] or ""
            }

    summary_short = None
    candidate_entities = None
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT summary_short, candidate_entities FROM thread_triage WHERE thread_id = ?;", (actual_tid,))
        trow = cur.fetchone()
        if trow:
            summary_short = trow[0]
            candidate_entities = trow[1]

    audit_data = None
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='inspected_threads';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT inspected_by, stage, findings_summary, thematic_tags, covered_spheres, inspected_at,
               coverage, entities_detected, unresolved_pronouns
        FROM inspected_threads
        WHERE chat_id = ? AND thread_id = ?;
        """, (row[1], actual_tid))
        arow = cur.fetchone()
        if arow:
            audit_data = {
                "inspected_by": arow[0],
                "stage": arow[1],
                "findings_summary": arow[2] or "",
                "thematic_tags": arow[3] or "",
                "covered_spheres": arow[4] or "",
                "inspected_at": arow[5],
                "coverage": arow[6] or "full",
                "entities_detected": arow[7] or "",
                "unresolved_pronouns": arow[8] or "",
            }

    conn.close()

    start_d = thread_msgs[0]["date"] if (is_multi_part and thread_msgs) else row[4]
    end_d = thread_msgs[-1]["date"] if (is_multi_part and thread_msgs) else row[5]
    msg_cnt = len(thread_msgs) if is_multi_part else row[6]

    return {
        "thread_id": actual_tid,
        "chat_id": row[1],
        "chat_name": row[2],
        "anchor_message_id": row[3],
        "anchor_message": anchor_msg,
        "summary_short": summary_short,
        "candidate_entities": candidate_entities,
        "audit": audit_data,
        "messages": thread_msgs,
        "start_date": start_d,
        "end_date": end_d,
        "message_count": msg_cnt,
        "participants": row[7],
        "initiator": row[8],
        "dialogue_text": row[9],
        "parent_thread_id": parent_tid,
        "child_thread_ids": children,
        "chain_mode": chain_mode,
        "is_full_chain": is_multi_part,
        "chain_thread_ids": chain_tids
    }


def print_thread(t: Dict[str, Any], summary_only: bool = False, force: bool = False) -> None:
    """Print ASCII transcript of a dialogue thread."""
    print("\n" + "=" * 70)
    c_label = f" [Chat: {t.get('chat_name', t.get('chat_id'))}]" if t.get("chat_name") else ""
    chain_mode = t.get("chain_mode", "single")
    if chain_mode == "forward":
        chain_desc = f" [FORWARD: {len(t['chain_thread_ids'])} parts to conversation end: {', '.join(t['chain_thread_ids'])}]"
        print(f"📜 CONVERSATION THREAD: {t['thread_id']}{c_label}{chain_desc}")
    elif chain_mode == "backward":
        chain_desc = f" [BACKWARD: {len(t['chain_thread_ids'])} parts from conversation start: {', '.join(t['chain_thread_ids'])}]"
        print(f"📜 CONVERSATION THREAD: {t['thread_id']}{c_label}{chain_desc}")
    elif chain_mode == "full":
        chain_desc = f" [FULL CHAIN: {len(t['chain_thread_ids'])} parts: {', '.join(t['chain_thread_ids'])}]"
        print(f"📜 CONVERSATION THREAD: {t['thread_id']}{c_label}{chain_desc}")
    else:
        print(f"📜 CONVERSATION THREAD: {t['thread_id']}{c_label}")
        if t.get("parent_thread_id"):
            print(f"⬆️  Parent Thread:     {t['parent_thread_id']}  (Audit previous: python3 project/scripts/query_chat.py -t {t['parent_thread_id']} | All backward: --backward)")
        if t.get("child_thread_ids"):
            children_str = ", ".join(t["child_thread_ids"])
            print(f"⬇️  Child Thread(s):   {children_str}  (Audit next part: python3 project/scripts/query_chat.py -t {t['child_thread_ids'][0]} | All forward: --forward)")
    print(f"Timeframe:         {t['start_date'][:16].replace('T', ' ')} to {t['end_date'][:16].replace('T', ' ')}")
    print(f"Messages:          {t['message_count']}")
    print(f"Participants:      {t['participants']} (Initiator: {t['initiator']})")
    if t.get("summary_short"):
        print(f"📋 Summary:          {t['summary_short']}")
    if t.get("candidate_entities") and t["candidate_entities"] not in ("[]", "None", ""):
        print(f"👥 Extracted Entities: {t['candidate_entities']}")

    if t.get("audit"):
        aud = t["audit"]
        cov = (aud.get("coverage") or "full").upper()
        print("-" * 70)
        print(f"ℹ️  THREAD AUDIT CACHE: Inspected by '{aud['inspected_by']}' (Coverage: {cov})")
        print(f"   Date: {aud['inspected_at'][:16].replace('T', ' ')} | Stage: {aud['stage']}")
        if aud.get("entities_detected"):
            print(f"   👥 Identified Entities: {aud['entities_detected']}")
        if aud.get("unresolved_pronouns"):
            print(f"   ❓ Unresolved / 'he/she' Clues: {aud['unresolved_pronouns']}")
        if aud.get("findings_summary"):
            print(f"   📋 Audit Findings: {aud['findings_summary']}")
        if aud.get("covered_spheres"):
            print(f"   🌐 Covered Spheres: {aud['covered_spheres']}")
    print("=" * 70)

    if summary_only:
        print(f"💡 [Summary-only mode: use `python3 project/scripts/query_chat.py -t {t['thread_id']}` to view full transcript]")
        print("=" * 70)
        return

    if t.get("audit") and not force:
        print("💡 CACHE HIT: Review the previous auditor's findings above.")
        print("   If this answers your inquiry, you do NOT need to re-read the raw messages.")
        print(f"   To view the full message transcript anyway, add: --force (or --force-full)")
        print("=" * 70 + "\n")
        return

    if t.get("messages"):
        if t.get("anchor_message"):
            anc = t["anchor_message"]
            fmt_anc = format_message_text(anc["text"], anc["id"])
            print(f"[Anchor #{anc['id']} | {anc['date'][:16].replace('T', ' ')}] {anc['sender']}: {fmt_anc}")
            print("-" * 50)
        for m in t["messages"]:
            prefix = f"[Reply to #{m['reply_to_id']}] " if m.get("reply_to_id") else ""
            fmt_m = format_message_text(m["text"], m["id"])
            print(f"[#{m['id']} | {m['date'][:16].replace('T', ' ')}] {m['sender']}: {prefix}{fmt_m}")
    else:
        print(t["dialogue_text"])

    # Directional continuation options for partitioned threads (only when viewing single part)
    if not t.get("is_full_chain") and (t.get("parent_thread_id") or t.get("child_thread_ids")):
        print("\n💡 THREAD CONTINUATION OPTIONS:")
        if t.get("child_thread_ids"):
            next_child = t['child_thread_ids'][0]
            print(f"   • Load NEXT FULL PART (50 msgs):  python3 project/scripts/query_chat.py -t {next_child}")
            print(f"   • Load ALL FORWARD PARTS to end:   python3 project/scripts/query_chat.py -t {t['thread_id']} --forward")
        if t.get("parent_thread_id"):
            prev_p = t['parent_thread_id']
            print(f"   • Load PREVIOUS FULL PART:         python3 project/scripts/query_chat.py -t {prev_p}")
            print(f"   • Load ALL BACKWARD PARTS to start: python3 project/scripts/query_chat.py -t {t['thread_id']} --backward")
        print("=" * 70)


def get_thread_slice(
    db_path: str,
    from_msg_id: int,
    limit: int = 5,
    window_before: int = 0,
    chat_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Fetch a slice of a conversation thread surrounding a specific message."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = "SELECT chat_id, thread_id, date, timestamp FROM messages WHERE id = ?"
    params: List[Any] = [from_msg_id]
    if chat_id:
        sql += " AND chat_id = ?"
        params.append(chat_id)

    cur.execute(sql, params)
    targets = cur.fetchall()
    if not targets:
        conn.close()
        return None

    c_id, thread_id, t_date, t_ts = targets[0]

    cur.execute("""
    SELECT t.anchor_message_id, t.initiator, t.participants, coalesce(c.chat_name, t.chat_id)
    FROM threads t
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    WHERE t.thread_id = ?;
    """, (thread_id,))
    t_row = cur.fetchone()
    anchor_id, init, parts, chat_name = t_row if t_row else (None, "Unknown", "", c_id)

    before_msgs = []
    if window_before > 0:
        cur.execute("""
        SELECT id, date, sender, reply_to_id, parent_id, link_type, text, timestamp
        FROM messages
        WHERE chat_id = ? AND thread_id = ? AND timestamp < ?
        ORDER BY timestamp DESC
        LIMIT ?;
        """, (c_id, thread_id, t_ts, window_before))
        before_msgs = cur.fetchall()
        before_msgs.reverse()

    cur.execute("""
    SELECT id, date, sender, reply_to_id, parent_id, link_type, text, timestamp
    FROM messages
    WHERE chat_id = ? AND thread_id = ? AND timestamp >= ?
    ORDER BY timestamp ASC
    LIMIT ?;
    """, (c_id, thread_id, t_ts, limit))
    forward_msgs = cur.fetchall()

    all_raw = before_msgs + forward_msgs
    conn.close()

    return {
        "thread_id": thread_id,
        "chat_id": c_id,
        "chat_name": chat_name,
        "anchor_message_id": anchor_id,
        "target_message_id": from_msg_id,
        "participants": parts,
        "messages": [
            {
                "id": m[0],
                "date": m[1],
                "sender": m[2],
                "reply_to_id": m[3],
                "parent_id": m[4],
                "link_type": m[5],
                "text": m[6],
                "is_target": (m[0] == from_msg_id)
            }
            for m in all_raw
        ]
    }


def print_thread_slice(s: Dict[str, Any]) -> None:
    """Print ASCII slice of a conversation thread."""
    print("\n" + "=" * 70)
    c_label = f" [Chat: {s.get('chat_name', s.get('chat_id'))}]" if s.get("chat_name") else ""
    print(f"🔎 THREAD SLICE (Target #{s['target_message_id']} in {s['thread_id']}){c_label}")
    print(f"Participants: {s['participants']}")
    print("=" * 70)
    for m in s["messages"]:
        marker = "==> " if m["is_target"] else "    "
        prefix = f"[Reply #{m['reply_to_id']}] " if m["reply_to_id"] else ""
        fmt_text = format_message_text(m['text'], m['id'])
        print(f"{marker}[#{m['id']} | {m['date'][:16].replace('T', ' ')}] {m['sender']}: {prefix}{fmt_text}")
    print("=" * 70)


def get_single_message(db_path: str, msg_id: int, chat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch complete metadata and text of a single message by ID."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    sql = """
    SELECT m.id, m.chat_id, coalesce(c.chat_name, m.chat_id) as chat_name,
           m.date, m.sender, m.reply_to_id, m.thread_id, m.text, length(coalesce(m.text, '')) as text_len
    FROM messages m
    LEFT JOIN chats c ON m.chat_id = c.chat_id
    WHERE m.id = ?
    """
    p: List[Any] = [msg_id]
    if chat_id:
        sql += " AND m.chat_id = ?"
        p.append(chat_id)
    cur.execute(sql, p)
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "chat_id": row[1],
        "chat_name": row[2],
        "date": row[3],
        "sender": row[4],
        "reply_to_id": row[5],
        "thread_id": row[6],
        "text": row[7] or "",
        "text_len": row[8] or 0
    }


def print_single_message(msg: Dict[str, Any], part: int = 1, part_size: int = 1500, show_all: bool = False) -> None:
    """Display single message with chunking / pagination support."""
    text = msg["text"]
    total_len = len(text)
    print("\n" + "=" * 70)
    c_label = f" [Chat: {msg['chat_name']}]" if msg.get("chat_name") else ""
    print(f"📩 MESSAGE INSPECTION: #{msg['id']}{c_label}")
    print("=" * 70)
    print(f"Date:         {msg['date'][:19].replace('T', ' ')}")
    print(f"Sender:       {msg['sender']}")
    print(f"Thread ID:    {msg['thread_id']}")
    print(f"Reply To:     #{msg['reply_to_id']}" if msg.get("reply_to_id") else "Reply To:     None")
    print(f"Total Chars:  {total_len}")
    print("=" * 70)

    if show_all or total_len <= part_size:
        if total_len > part_size:
            print(f"[📄 PEŁNA TREŚĆ WIADOMOŚCI ({total_len} znaków, tryb --all)]:\n")
        print(text)
        print("=" * 70)
        return

    total_parts = math.ceil(total_len / part_size)
    if part < 1:
        part = 1
    if part > total_parts:
        print(f"⚠️  Wybrana część ({part}) przekracza łączną liczbę części ({total_parts}). Pokazuję część {total_parts}.")
        part = total_parts

    start_idx = (part - 1) * part_size
    end_idx = min(start_idx + part_size, total_len)
    chunk = text[start_idx:end_idx]

    print(f"[📄 Część {part}/{total_parts} (znaki {start_idx + 1}-{end_idx} z {total_len})]:")
    print("-" * 70)
    print(chunk)
    print("-" * 70)

    if part < total_parts:
        print(f"💡 Aby wyświetlić kolejną część: python3 project/scripts/query_chat.py -m {msg['id']} --part {part + 1}")
        print(f"   Aby wyświetlić całość bez podziału: python3 project/scripts/query_chat.py -m {msg['id']} --all")
    else:
        print(f"✅ Koniec wiadomości (Część {part}/{total_parts}). Aby wyświetlić całość bez podziału: --all")
    print("=" * 70)
