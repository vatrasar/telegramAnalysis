"""Windowed context retrieval, causal quote chains, and chronological boundary audits."""

import re
import json
import sqlite3
from typing import List, Dict, Any, Optional

from .formatters import format_message_text


def get_thread_snippets(
    db_path: str,
    thread_id: str,
    mentions: Optional[List[str]] = None,
    window: int = 4,
    chat_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Fetch windowed context snippets (±window messages) around candidate entity mentions in a thread."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.anchor_message_id,
           t.start_date, t.end_date, t.message_count, t.participants
    FROM threads t
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    WHERE t.thread_id = ?;
    """, (thread_id,))
    t_row = cur.fetchone()
    if not t_row:
        conn.close()
        return None

    tid, c_id, chat_name, anchor_id, sdate, edate, mcount, participants = t_row

    candidates: List[Dict[str, Any]] = []
    if mentions:
        for m in mentions:
            if m.strip():
                candidates.append({"mention": m.strip(), "role": "explicit_query"})
    else:
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT candidate_entities FROM thread_triage WHERE thread_id = ?;", (thread_id,))
            cand_row = cur.fetchone()
            if cand_row and cand_row[0]:
                raw_cands = cand_row[0].strip()
                try:
                    parsed = json.loads(raw_cands)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and "mention" in item:
                                candidates.append(item)
                            elif isinstance(item, str):
                                candidates.append({"mention": item, "role": "unspecified"})
                    elif isinstance(parsed, dict) and "people" in parsed:
                        candidates = parsed.get("people", [])
                except Exception:
                    for token in raw_cands.split(","):
                        if token.strip():
                            candidates.append({"mention": token.strip(), "role": "unspecified"})

    cur.execute("""
    SELECT id, date, sender, text, timestamp
    FROM messages
    WHERE thread_id = ?
    ORDER BY timestamp ASC, id ASC;
    """, (thread_id,))
    msg_rows = cur.fetchall()
    conn.close()

    if not msg_rows:
        return {
            "thread_id": thread_id,
            "chat_id": c_id,
            "chat_name": chat_name,
            "message_count": 0,
            "candidates": candidates,
            "snippets": []
        }

    snippets: List[Dict[str, Any]] = []

    if not candidates:
        sample_indices = sorted(list(set(range(min(5, len(msg_rows)))) | set(range(max(0, len(msg_rows) - 5), len(msg_rows)))))
        sample_msgs = [{
            "id": msg_rows[i][0], "date": msg_rows[i][1], "sender": msg_rows[i][2], "text": msg_rows[i][3]
        } for i in sample_indices]
        return {
            "thread_id": thread_id,
            "chat_id": c_id,
            "chat_name": chat_name,
            "start_date": sdate,
            "end_date": edate,
            "message_count": len(msg_rows),
            "candidates": [],
            "note": "No candidate entities found in thread_triage; displaying thread boundary sample.",
            "snippets": [{
                "candidate": {"mention": "(thread sample)", "role": "sample"},
                "matched_msg_ids": [m["id"] for m in sample_msgs],
                "messages": sample_msgs
            }]
        }

    for cand in candidates:
        mention = cand.get("mention", "").strip()
        if not mention:
            continue
        escaped_m = re.escape(mention)
        pattern = re.compile(r'(?:\b|_)' + escaped_m + r'(?:\b|_)', re.IGNORECASE)
        matching_indices = []
        for idx, m in enumerate(msg_rows):
            text = m[3] or ""
            if pattern.search(text) or mention.lower() in text.lower():
                matching_indices.append(idx)

        if not matching_indices:
            snippets.append({
                "candidate": cand,
                "matched_msg_ids": [],
                "messages": [],
                "status": "not_found_in_thread_messages"
            })
            continue

        intervals = []
        for idx in matching_indices:
            start_i = max(0, idx - window)
            end_i = min(len(msg_rows), idx + window + 1)
            intervals.append((start_i, end_i))

        merged: List[List[int]] = []
        for s, e in sorted(intervals, key=lambda x: x[0]):
            if not merged:
                merged.append([s, e])
            else:
                prev = merged[-1]
                if s <= prev[1]:
                    prev[1] = max(prev[1], e)
                else:
                    merged.append([s, e])

        cand_messages = []
        seen_msg_ids = set()
        for s, e in merged:
            for i in range(s, e):
                m = msg_rows[i]
                if m[0] not in seen_msg_ids:
                    seen_msg_ids.add(m[0])
                    cand_messages.append({
                        "id": m[0],
                        "date": m[1],
                        "sender": m[2],
                        "text": m[3],
                        "is_direct_match": (i in matching_indices)
                    })

        snippets.append({
            "candidate": cand,
            "matched_msg_ids": [msg_rows[i][0] for i in matching_indices],
            "messages": cand_messages,
            "status": "matched"
        })

    return {
        "thread_id": thread_id,
        "chat_id": c_id,
        "chat_name": chat_name,
        "start_date": sdate,
        "end_date": edate,
        "message_count": len(msg_rows),
        "candidates": candidates,
        "snippets": snippets
    }


def print_thread_snippets(data: Dict[str, Any]) -> None:
    """Print ASCII snippets around candidate entity mentions."""
    print("\n" + "=" * 80)
    c_label = f" [Chat: {data.get('chat_name', data.get('chat_id'))}]" if data.get("chat_name") else ""
    print(f"🎯 FOCUSED CANDIDATE SNIPPETS: Thread {data['thread_id']}{c_label}")
    print(f"   Period: {data.get('start_date', '')} -> {data.get('end_date', '')} | Total Msgs in Thread: {data.get('message_count', 0)}")
    cands_summary = [f"{c.get('mention')} ({c.get('role', 'unknown')})" for c in data.get("candidates", [])]
    print(f"   Candidate Entities: [{', '.join(cands_summary) if cands_summary else 'None'}]")
    print("=" * 80)

    snippets = data.get("snippets", [])
    if not snippets:
        print("   (No snippets found)")
        print("=" * 80 + "\n")
        return

    for snip in snippets:
        cand = snip.get("candidate", {})
        status = snip.get("status", "")
        print(f"\n🔍 Candidate Mention: \"{cand.get('mention')}\" (Role Hint: {cand.get('role', 'none')})")
        if status == "not_found_in_thread_messages":
            print(f"   [!] Mention \"{cand.get('mention')}\" was not directly found in raw message text (likely in summary or parent).")
            continue

        matched_ids = snip.get("matched_msg_ids", [])
        print(f"   Anchor Messages with Matches: {matched_ids}")
        print("   --- Windowed Conversational Context (±window turns) ---")
        for m in snip.get("messages", []):
            marker = "👉 [*HIT*]" if m.get("is_direct_match") else "   "
            fmt_text = format_message_text(m['text'], m['id'])
            print(f"{marker} [#{m['id']} | {m['date'][:16].replace('T', ' ')}] {m['sender']}: {fmt_text}")
    print("=" * 80 + "\n")


def get_quote_chain(db_path: str, msg_id: int, chat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Trace and extract the exact causal quote chain for a message within its chat stream."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT m.id, m.chat_id, coalesce(c.chat_name, m.chat_id), m.date, m.sender,
           m.reply_to_id, m.parent_id, m.link_type, m.text
    FROM messages m
    LEFT JOIN chats c ON m.chat_id = c.chat_id
    WHERE m.id = ?
    """
    p: List[Any] = [msg_id]
    if chat_id:
        sql += " AND m.chat_id = ? "
        p.append(chat_id)

    cur.execute(sql, p)
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return None

    target = rows[0]
    c_id = target[1]
    chat_name = target[2]

    # Upstream ancestors in the same chat
    ancestors = []
    curr_parent = target[6] or target[5]
    visited = {msg_id}

    while curr_parent and curr_parent not in visited:
        visited.add(curr_parent)
        cur.execute("""
        SELECT id, date, sender, reply_to_id, parent_id, link_type, text
        FROM messages WHERE chat_id = ? AND id = ?;
        """, (c_id, curr_parent))
        p_row = cur.fetchone()
        if not p_row:
            break
        ancestors.append(p_row)
        curr_parent = p_row[4] or p_row[3]

    ancestors.reverse()

    # Downstream direct replies in the same chat
    cur.execute("""
    SELECT id, date, sender, reply_to_id, parent_id, link_type, text 
    FROM messages 
    WHERE chat_id = ? AND (parent_id = ? OR reply_to_id = ?)
    ORDER BY date ASC
    LIMIT 10;
    """, (c_id, msg_id, msg_id))
    children = cur.fetchall()
    conn.close()

    return {
        "chat_id": c_id,
        "chat_name": chat_name,
        "target_message": {
            "id": target[0],
            "date": target[3],
            "sender": target[4],
            "reply_to_id": target[5],
            "parent_id": target[6],
            "link_type": target[7],
            "text": target[8]
        },
        "ancestors": [
            {
                "id": a[0], "date": a[1], "sender": a[2],
                "reply_to_id": a[3], "parent_id": a[4], "link_type": a[5], "text": a[6]
            }
            for a in ancestors
        ],
        "replies": [
            {
                "id": c[0], "date": c[1], "sender": c[2],
                "reply_to_id": c[3], "parent_id": c[4], "link_type": c[5], "text": c[6]
            }
            for c in children
        ]
    }


def print_quote_chain(c: Dict[str, Any]) -> None:
    """Print ASCII causal quote chain."""
    print("\n" + "=" * 70)
    c_label = f" [Chat: {c.get('chat_name', c.get('chat_id'))}]" if c.get("chat_name") else ""
    print(f"🔗 CAUSAL QUOTE CHAIN FOR MESSAGE #{c['target_message']['id']}{c_label}")
    print("=" * 70)

    if c["ancestors"]:
        print("⬆️  UPSTREAM CONTEXT (What triggered this):")
        for a in c["ancestors"]:
            fmt_a = format_message_text(a['text'], a['id'])
            print(f"   [#{a['id']} | {a['date'][:16].replace('T', ' ')}] {a['sender']}: {fmt_a}")
        print("   " + "-" * 50)

    t = c["target_message"]
    fmt_t = format_message_text(t['text'], t['id'])
    print(f"🎯 TARGET MESSAGE [#{t['id']} | {t['date'][:16].replace('T', ' ')}] {t['sender']}:")
    print(f"   {fmt_t}")

    if c["replies"]:
        print("   " + "-" * 50)
        print("⬇️  DOWNSTREAM REACTIONS (Direct answers to target):")
        for r in c["replies"]:
            fmt_r = format_message_text(r['text'], r['id'])
            print(f"   [#{r['id']} | {r['date'][:16].replace('T', ' ')}] {r['sender']}: {fmt_r}")
    print("=" * 70)


def get_chronological_around(
    db_path: str,
    msg_id: int,
    window: int = 5,
    chat_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve chronological messages surrounding msg_id strictly by timestamp/id,

    crossing thread boundaries to enforce the N-5 ... N+5 audit protocol.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT m.id, m.chat_id, coalesce(c.chat_name, m.chat_id), m.date, m.timestamp,
           m.sender, m.reply_to_id, m.thread_id, m.text
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
    if not row:
        conn.close()
        return None

    t_id, c_id, chat_name, t_date, t_ts, t_sender, t_reply, t_thread, t_text = row

    # Fetch preceding messages in the same chat
    cur.execute("""
    SELECT id, date, timestamp, sender, reply_to_id, thread_id, text
    FROM messages
    WHERE chat_id = ? AND (timestamp < ? OR (timestamp = ? AND id < ?))
    ORDER BY timestamp DESC, id DESC
    LIMIT ?;
    """, (c_id, t_ts, t_ts, t_id, window))
    before_rows = cur.fetchall()
    before_rows.reverse()

    # Fetch subsequent messages in the same chat
    cur.execute("""
    SELECT id, date, timestamp, sender, reply_to_id, thread_id, text
    FROM messages
    WHERE chat_id = ? AND (timestamp > ? OR (timestamp = ? AND id > ?))
    ORDER BY timestamp ASC, id ASC
    LIMIT ?;
    """, (c_id, t_ts, t_ts, t_id, window))
    after_rows = cur.fetchall()
    conn.close()

    def format_m(r, is_target=False):
        return {
            "id": r[0],
            "date": r[1],
            "timestamp": r[2],
            "sender": r[3],
            "reply_to_id": r[4],
            "thread_id": r[5],
            "text": r[6],
            "is_target": is_target
        }

    return {
        "chat_id": c_id,
        "chat_name": chat_name,
        "target_id": msg_id,
        "window": window,
        "preceding_count": len(before_rows),
        "subsequent_count": len(after_rows),
        "messages": (
            [format_m(r) for r in before_rows] +
            [format_m((t_id, t_date, t_ts, t_sender, t_reply, t_thread, t_text), is_target=True)] +
            [format_m(r) for r in after_rows]
        )
    }


def print_chronological_around(c: Dict[str, Any]) -> None:
    """Print ASCII view of chronological audit window."""
    print("\n" + "=" * 70)
    c_label = f" [Chat: {c.get('chat_name', c.get('chat_id'))}]" if c.get("chat_name") else ""
    print(f"⏱️  CHRONOLOGICAL AUDIT WINDOW: Message #{c['target_id']}{c_label} (±{c['window']} msgs)")
    print("=" * 70)
    for m in c["messages"]:
        is_target = m.get("is_target", False)
        prefix = f"[Reply to #{m['reply_to_id']}] " if m.get("reply_to_id") else ""
        thread_tag = f" (Thread: {m['thread_id']})" if m.get("thread_id") else ""
        dt_str = m['date'][:16].replace('T', ' ')
        fmt_text = format_message_text(m['text'], m['id'])
        if is_target:
            print("-" * 70)
            print(f"👉 [#{m['id']} | {dt_str}{thread_tag}] {m['sender']}: {prefix}{fmt_text}  [AUDITED TARGET]")
            print("-" * 70)
        else:
            print(f"   [#{m['id']} | {dt_str}{thread_tag}] {m['sender']}: {prefix}{fmt_text}")
    print("=" * 70)
