#!/usr/bin/env python3
"""
Telegram Chat Analysis Query CLI.
Provides quantitative mining (Phase 1) and qualitative psychological retrieval (Phase 2)
over preprocessed SQLite and vector chat data.

Supports:
- Multi-query simultaneous execution (e.g. --stats --gaps --timeline in one call)
- Repeated batch queries (--semantic "q1" --semantic "q2" or -s "term1" -s "term2")
- Batch JSON execution via --batch-json <file_or_string>
- Structured JSON output mode via --json (agent-friendly token-efficient output)
"""

import os
import sys
import json
import math
import sqlite3
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from vector_indexer import search_semantic, search_semantic_batch
except ImportError:
    search_semantic = None
    search_semantic_batch = None


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable string (days, hours, minutes)."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h"


# ==============================================================================
# DATA RETRIEVAL FUNCTIONS (PURE DATA)
# ==============================================================================

def get_stats(db_path: str) -> Dict[str, Any]:
    """Retrieve Phase 1 quantitative metrics as structured data."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT count(*), min(date), max(date) FROM messages")
    total_msgs, min_date, max_date = cur.fetchone()

    cur.execute("SELECT count(*) FROM threads")
    total_threads = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM silence_gaps")
    total_gaps = cur.fetchone()[0]

    cur.execute("""
    SELECT sender, count(*), round(avg(word_count), 1), sum(word_count)
    FROM messages
    GROUP BY sender
    ORDER BY count(*) DESC
    """)
    participants = []
    for row in cur.fetchall():
        sender, count, avg_w, sum_w = row
        pct = round((count / total_msgs * 100), 1) if total_msgs else 0.0
        participants.append({
            "sender": sender,
            "messages": count,
            "share_percentage": pct,
            "avg_words_per_msg": avg_w or 0.0,
            "total_words": sum_w or 0
        })

    conn.close()
    return {
        "total_messages": total_msgs or 0,
        "total_threads": total_threads or 0,
        "long_silences_over_24h": total_gaps or 0,
        "date_range": {
            "start": str(min_date)[:10] if min_date else None,
            "end": str(max_date)[:10] if max_date else None
        },
        "participants": participants
    }


def get_silence_gaps(db_path: str, min_hours: float = 24.0) -> Dict[str, Any]:
    """Retrieve silence gaps and initiative ratios as structured data."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT silence_start_date, silence_end_date, silence_duration_seconds, last_sender, initiator, after_thread_id
    FROM silence_gaps
    WHERE silence_duration_hours >= ?
    ORDER BY silence_duration_seconds DESC
    """, (min_hours,))
    rows = cur.fetchall()

    initiators: Dict[str, int] = {}
    gaps_list = []
    for r in rows:
        init = r[4]
        initiators[init] = initiators.get(init, 0) + 1
        gaps_list.append({
            "start_date": r[0],
            "end_date": r[1],
            "duration_seconds": r[2],
            "duration_formatted": format_duration(r[2]),
            "last_sender": r[3],
            "initiator": r[4],
            "after_thread_id": r[5]
        })

    total_gaps = len(rows)
    init_stats = []
    for sender, count in sorted(initiators.items(), key=lambda x: x[1], reverse=True):
        init_stats.append({
            "sender": sender,
            "count": count,
            "percentage": round((count / total_gaps * 100), 1) if total_gaps else 0.0
        })

    conn.close()
    return {
        "min_hours": min_hours,
        "total_gaps": total_gaps,
        "initiative_stats": init_stats,
        "longest_gaps": gaps_list[:15]
    }


def get_timeline(db_path: str) -> Dict[str, Any]:
    """Retrieve monthly message counts per participant."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT substr(date, 1, 7) as month, sender, count(*)
    FROM messages
    GROUP BY month, sender
    ORDER BY month ASC
    """)
    rows = cur.fetchall()

    timeline: Dict[str, Dict[str, int]] = {}
    senders = set()
    for month, sender, count in rows:
        timeline.setdefault(month, {})[sender] = count
        senders.add(sender)

    conn.close()
    sorted_senders = sorted(list(senders))
    monthly_data = []
    for month in sorted(timeline.keys()):
        counts = timeline[month]
        total = sum(counts.values())
        entry = {"month": month, "total": total}
        for s in sorted_senders:
            entry[s] = counts.get(s, 0)
        monthly_data.append(entry)

    return {
        "senders": sorted_senders,
        "months": monthly_data
    }


def get_burning_days(db_path: str, std_multiplier: float = 2.0, min_msgs: int = 15) -> Dict[str, Any]:
    """Identify statistically anomalous high-activity days (mu + 2*sigma)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT substr(date, 1, 10) as day, count(*), sum(word_count)
    FROM messages
    GROUP BY day
    ORDER BY day ASC
    """)
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return {"total_active_days": 0, "threshold_messages": 0, "burning_days": []}

    counts = [r[1] for r in rows]
    n = len(counts)
    mean_count = sum(counts) / n
    variance = sum((c - mean_count) ** 2 for c in counts) / n
    std_count = math.sqrt(variance)
    threshold = max(float(min_msgs), round(mean_count + (std_multiplier * std_count), 1))

    candidates = [r for r in rows if r[1] >= threshold]
    # Fallback to top days if standard deviation is tiny
    if not candidates and n > 0:
        sorted_rows = sorted(rows, key=lambda x: x[1], reverse=True)
        candidates = sorted_rows[:min(5, n)]

    burning_days = []
    for day, msg_count, word_count in sorted(candidates, key=lambda x: x[1], reverse=True):
        cur.execute("""
        SELECT sender, count(*) FROM messages
        WHERE substr(date, 1, 10) = ?
        GROUP BY sender ORDER BY count(*) DESC LIMIT 1
        """, (day,))
        top_s_row = cur.fetchone()
        top_sender = top_s_row[0] if top_s_row else "Unknown"

        cur.execute("""
        SELECT DISTINCT thread_id FROM messages
        WHERE substr(date, 1, 10) = ?
        """, (day,))
        thread_ids = [r[0] for r in cur.fetchall()]

        burning_days.append({
            "date": day,
            "messages": msg_count,
            "words": word_count or 0,
            "top_participant": top_sender,
            "active_threads_count": len(thread_ids),
            "thread_ids": thread_ids
        })

    conn.close()
    return {
        "total_active_days": n,
        "mean_daily_messages": round(mean_count, 1),
        "std_daily_messages": round(std_count, 1),
        "anomaly_threshold_messages": threshold,
        "burning_days_count": len(burning_days),
        "burning_days": burning_days
    }


def get_intensive_threads(db_path: str, min_words: int = 50, min_messages: int = 6, limit: int = 25) -> List[Dict[str, Any]]:
    """Retrieve dialogue threads ranked by substantive conversational volume, filtering small-talk noise."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT t.thread_id, t.start_date, t.end_date, t.message_count, sum(m.word_count) as total_words,
           t.participants, t.initiator, t.duration_seconds
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id
    GROUP BY t.thread_id
    HAVING t.message_count >= ? AND total_words >= ?
    ORDER BY total_words DESC
    LIMIT ?
    """, (min_messages, min_words, limit))
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "thread_id": r[0],
            "start_date": r[1][:16].replace("T", " "),
            "end_date": r[2][:16].replace("T", " "),
            "message_count": r[3],
            "total_words": r[4] or 0,
            "participants": r[5],
            "initiator": r[6],
            "duration": format_duration(r[7] or 0)
        })
    return results


def get_search_messages(db_path: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Search individual messages using FTS5."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
    if not clean_q:
        conn.close()
        return []

    terms = clean_q.split()
    fts_query = " AND ".join(f'"{t}"' for t in terms)

    try:
        cur.execute("""
        SELECT message_id, date, sender, thread_id, snippet(messages_fts, 4, '【', '】', '...', 15)
        FROM messages_fts
        WHERE messages_fts MATCH ?
        ORDER BY rank
        LIMIT ?;
        """, (fts_query, limit))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        cur.execute("""
        SELECT id, date, sender, thread_id, text
        FROM messages
        WHERE text LIKE ?
        ORDER BY date DESC
        LIMIT ?;
        """, (f"%{clean_q}%", limit))
        rows = cur.fetchall()

    conn.close()
    return [
        {
            "message_id": r[0],
            "date": r[1],
            "sender": r[2],
            "thread_id": r[3],
            "text": r[4]
        }
        for r in rows
    ]


def get_search_threads_fts(db_path: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search complete threads using FTS5."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
    terms = clean_q.split()
    fts_query = " AND ".join(f'"{t}"' for t in terms)

    try:
        cur.execute("""
        SELECT thread_id, start_date, participants, dialogue_text
        FROM threads_fts
        WHERE threads_fts MATCH ?
        ORDER BY rank
        LIMIT ?;
        """, (fts_query, limit))
        rows = cur.fetchall()
    except Exception:
        cur.execute("""
        SELECT thread_id, start_date, participants, dialogue_text
        FROM threads
        WHERE dialogue_text LIKE ?
        ORDER BY start_date DESC
        LIMIT ?;
        """, (f"%{clean_q}%", limit))
        rows = cur.fetchall()

    conn.close()
    return [
        {
            "thread_id": r[0],
            "start_date": r[1],
            "participants": r[2],
            "dialogue_text": r[3]
        }
        for r in rows
    ]


def get_thread(db_path: str, identifier: str) -> Optional[Dict[str, Any]]:
    """Fetch full dialogue transcript of a thread by thread_id or message_id."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    target_thread_id = identifier
    cur.execute("""
    SELECT thread_id, anchor_message_id, start_date, end_date, message_count, participants, initiator, dialogue_text
    FROM threads WHERE thread_id = ?
    """, (target_thread_id,))
    row = cur.fetchone()

    if not row:
        try:
            msg_id = int(identifier)
            cur.execute("SELECT thread_id FROM messages WHERE id = ?", (msg_id,))
            m_row = cur.fetchone()
            if m_row:
                target_thread_id = m_row[0]
                cur.execute("""
                SELECT thread_id, anchor_message_id, start_date, end_date, message_count, participants, initiator, dialogue_text
                FROM threads WHERE thread_id = ?
                """, (target_thread_id,))
                row = cur.fetchone()
        except ValueError:
            pass

    conn.close()
    if not row:
        return None

    return {
        "thread_id": row[0],
        "anchor_message_id": row[1],
        "start_date": row[2],
        "end_date": row[3],
        "message_count": row[4],
        "participants": row[5],
        "initiator": row[6],
        "dialogue_text": row[7]
    }


def get_thread_slice(db_path: str, from_msg_id: int, limit: int = 5, window_before: int = 0) -> Optional[Dict[str, Any]]:
    """Fetch a slice of a conversation thread surrounding a specific message."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT thread_id, date, timestamp FROM messages WHERE id = ?", (from_msg_id,))
    target = cur.fetchone()
    if not target:
        conn.close()
        return None

    thread_id, t_date, t_ts = target

    cur.execute("SELECT anchor_message_id, initiator, participants FROM threads WHERE thread_id = ?", (thread_id,))
    t_row = cur.fetchone()
    anchor_id, init, parts = t_row if t_row else (None, "Unknown", "")

    before_msgs = []
    if window_before > 0:
        cur.execute("""
        SELECT id, date, sender, reply_to_id, parent_id, link_type, text, timestamp
        FROM messages
        WHERE thread_id = ? AND timestamp < ?
        ORDER BY timestamp DESC
        LIMIT ?
        """, (thread_id, t_ts, window_before))
        before_msgs = cur.fetchall()
        before_msgs.reverse()

    cur.execute("""
    SELECT id, date, sender, reply_to_id, parent_id, link_type, text, timestamp
    FROM messages
    WHERE thread_id = ? AND timestamp >= ?
    ORDER BY timestamp ASC
    LIMIT ?
    """, (thread_id, t_ts, limit))
    forward_msgs = cur.fetchall()

    all_raw = before_msgs + forward_msgs
    conn.close()

    return {
        "thread_id": thread_id,
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


def get_quote_chain(db_path: str, msg_id: int) -> Optional[Dict[str, Any]]:
    """Trace and extract the exact causal quote chain for a message."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, date, sender, reply_to_id, parent_id, link_type, text FROM messages WHERE id = ?", (msg_id,))
    target = cur.fetchone()
    if not target:
        conn.close()
        return None

    # Upstream ancestors
    ancestors = []
    curr_parent = target[4] or target[3]
    visited = {msg_id}

    while curr_parent and curr_parent not in visited:
        visited.add(curr_parent)
        cur.execute("SELECT id, date, sender, reply_to_id, parent_id, link_type, text FROM messages WHERE id = ?", (curr_parent,))
        p_row = cur.fetchone()
        if not p_row:
            break
        ancestors.append(p_row)
        curr_parent = p_row[4] or p_row[3]

    ancestors.reverse()

    # Downstream direct replies
    cur.execute("""
    SELECT id, date, sender, reply_to_id, parent_id, link_type, text 
    FROM messages 
    WHERE parent_id = ? OR reply_to_id = ?
    ORDER BY date ASC
    LIMIT 10
    """, (msg_id, msg_id))
    children = cur.fetchall()
    conn.close()

    return {
        "target_message": {
            "id": target[0],
            "date": target[1],
            "sender": target[2],
            "reply_to_id": target[3],
            "parent_id": target[4],
            "link_type": target[5],
            "text": target[6]
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


def get_semantic_batch_results(db_path: str, concepts: List[str], top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """Execute batch semantic search over multiple psychological concepts."""
    if search_semantic_batch is not None:
        return search_semantic_batch(db_path, concepts, top_k=top_k)
    elif search_semantic is not None:
        return {c: search_semantic(db_path, c, top_k=top_k) for c in concepts}
    else:
        print("[!] vector_indexer module not available for semantic queries.")
        return {c: [] for c in concepts}


# ==============================================================================
# PRESENTATION FUNCTIONS (CLI ASCII FORMATTING)
# ==============================================================================

def print_stats(stats: Dict[str, Any]):
    print("\n" + "=" * 60)
    print("📊 QUANTITATIVE OVERVIEW (PHASE 1)")
    print("=" * 60)
    print(f"Total Messages:       {stats['total_messages']:,}")
    print(f"Total Threads:        {stats['total_threads']:,}")
    print(f"Long Silences (>24h): {stats['long_silences_over_24h']:,}")
    print(f"Date Range:           {stats['date_range']['start']} to {stats['date_range']['end']}")

    print("\n👥 PARTICIPANT METRICS:")
    print(f"{'Sender':<20} {'Messages':<10} {'Share %':<10} {'Avg Words/Msg':<15} {'Total Words':<12}")
    print("-" * 67)
    for p in stats["participants"]:
        print(f"{p['sender']:<20} {p['messages']:<10,} {p['share_percentage']:<9.1f}% {p['avg_words_per_msg']:<15} {p['total_words']:<12,}")


def print_silence_gaps(data: Dict[str, Any]):
    print("\n" + "=" * 75)
    print(f"⏳ CONVERSATION GAPS & RECONNECTION INITIATIVE (>= {data['min_hours']}h)")
    print("=" * 75)

    if not data["longest_gaps"]:
        print(f"No silences found exceeding {data['min_hours']} hours.")
        return

    print("\nInitiative Ratio (Who breaks the silence):")
    for s in data["initiative_stats"]:
        print(f"  - {s['sender']:<18}: {s['count']} times ({s['percentage']}%)")

    print(f"\nTop Longest Silences:")
    print(f"{'Silence Period':<35} {'Duration':<12} {'Last Spoke':<14} {'Broke Silence':<14}")
    print("-" * 75)
    for g in data["longest_gaps"]:
        start_d = g["start_date"][:16].replace("T", " ")
        end_d = g["end_date"][:16].replace("T", " ")
        dur_str = g["duration_formatted"]
        last_s = g["last_sender"][:13]
        init_s = g["initiator"][:13]
        print(f"{start_d} -> {end_d:<16} {dur_str:<12} {last_s:<14} {init_s:<14}")


def print_timeline(data: Dict[str, Any]):
    print("\n" + "=" * 60)
    print("📅 MONTHLY TIMELINE DISTRIBUTION")
    print("=" * 60)
    senders = data["senders"]
    header = f"{'Month':<10} " + " ".join([f"{s[:12]:<12}" for s in senders]) + " Total"
    print(header)
    print("-" * len(header))

    for m in data["months"]:
        counts_str = " ".join([f"{m.get(s, 0):<12}" for s in senders])
        print(f"{m['month']:<10} {counts_str} {m['total']}")


def print_search_messages(query: str, rows: List[Dict[str, Any]]):
    print(f"\n🔍 Search Results for: '{query}' (Found {len(rows)} matches)")
    print("=" * 70)
    for r in rows:
        d_clean = r["date"][:16].replace("T", " ")
        print(f"[#{r['message_id']} | {d_clean} | Thread: {r['thread_id']}] {r['sender']}:")
        print(f"  {r['text']}\n")


def print_search_threads(query: str, rows: List[Dict[str, Any]]):
    print(f"\n💬 Complete Threads Matching: '{query}' (Found {len(rows)})")
    print("=" * 70)
    for r in rows:
        d_clean = r["start_date"][:16].replace("T", " ")
        print(f"--- Thread: {r['thread_id']} | Started: {d_clean} | Participants: {r['participants']} ---")
        print(r["dialogue_text"])
        print("-" * 70)


def print_thread(t: Optional[Dict[str, Any]], identifier: str):
    if not t:
        print(f"[!] Thread or Message '{identifier}' not found in database.")
        return

    print("\n" + "=" * 70)
    print(f"Thread:       {t['thread_id']}")
    print(f"Anchor Msg:   #{t['anchor_message_id'] if t['anchor_message_id'] else 'None'}")
    start_d = t["start_date"][:16].replace("T", " ")
    end_d = t["end_date"][:16].replace("T", " ")
    print(f"Time Range:   {start_d} to {end_d}")
    print(f"Initiator:    {t['initiator']} | Total Messages: {t['message_count']}")
    print(f"Participants: {t['participants']}")
    print("=" * 70)
    print(t["dialogue_text"])
    print("=" * 70 + "\n")


def print_thread_slice(s: Optional[Dict[str, Any]], from_msg_id: int):
    if not s:
        print(f"[!] Message #{from_msg_id} not found in database.")
        return

    print("\n" + "=" * 70)
    print(f"Thread:       {s['thread_id']}")
    print(f"Anchor Msg:   #{s['anchor_message_id'] if s['anchor_message_id'] else 'None'}")
    print(f"Slice View:   Starting at #{from_msg_id} (Showing {len(s['messages'])} messages)")
    print(f"Participants: {s['participants']}")
    print("=" * 70)

    for m in s["messages"]:
        is_target = "⭐ [START] " if m["is_target"] else "  "
        prefix = ""
        if m["link_type"] == "explicit_reply":
            prefix = f"[Reply to #{m['parent_id']}] "
        elif m["link_type"] == "burst_continuation":
            prefix = "[+] "
        m_date = m["date"][:16].replace("T", " ")
        print(f"{is_target}[#{m['id']} | {m_date}] {m['sender']}: {prefix}{m['text']}")

    print("=" * 70 + "\n")


def print_quote_chain(c: Optional[Dict[str, Any]], msg_id: int):
    if not c:
        print(f"[!] Message #{msg_id} not found in database.")
        return

    print("\n" + "=" * 75)
    print(f"🔗 CAUSAL QUOTE CHAIN FOR MESSAGE #{msg_id}")
    print("=" * 75)

    indent = 0
    if c["ancestors"]:
        print("Ancestors (What led up to this message):")
        for anc in c["ancestors"]:
            prefix = "  " * indent + "↳ " if indent > 0 else "• "
            anc_date = anc["date"][:16].replace("T", " ")
            print(f"{prefix}[#{anc['id']} | {anc_date}] {anc['sender']}: {anc['text']}")
            indent += 1

    tgt = c["target_message"]
    target_prefix = "  " * indent + "⭐ [TARGET] " if indent > 0 else "⭐ [TARGET] "
    t_date = tgt["date"][:16].replace("T", " ")
    print(f"\n{target_prefix}[#{tgt['id']} | {t_date}] {tgt['sender']}: {tgt['text']}\n")

    if c["replies"]:
        print("Direct Replies & Follow-ups to this message:")
        for ch in c["replies"]:
            ch_date = ch["date"][:16].replace("T", " ")
            l_info = "Reply" if ch["reply_to_id"] == msg_id else "Burst continuation"
            print(f"  ↳ [#{ch['id']} | {ch_date} | {l_info}] {ch['sender']}: {ch['text']}")

    print("=" * 75 + "\n")


def print_burning_days(data: Dict[str, Any]):
    print("\n" + "=" * 70)
    print("🔥 BURNING DAYS (STATISTICAL CONVERSATION ANOMALIES)")
    print("=" * 70)
    print(f"Total Active Days: {data['total_active_days']} | Mean: {data['mean_daily_messages']} msgs/day | StdDev: {data['std_daily_messages']}")
    print(f"Anomaly Threshold (μ + 2σ): {data['anomaly_threshold_messages']} messages | Found: {data['burning_days_count']} days")
    print("-" * 70)
    print(f"{'Date':<12} {'Messages':<10} {'Words':<10} {'Top Participant':<18} {'Active Threads'}")
    print("-" * 70)
    for b in data["burning_days"]:
        t_ids = ", ".join(b["thread_ids"][:4])
        if len(b["thread_ids"]) > 4:
            t_ids += f" (+{len(b['thread_ids']) - 4} more)"
        print(f"{b['date']:<12} {b['messages']:<10} {b['words']:<10} {b['top_participant'][:16]:<18} {t_ids}")


def print_intensive_threads(rows: List[Dict[str, Any]]):
    print("\n" + "=" * 75)
    print("💬 SUBSTANTIVE DIALOGUE THREADS (RANKED BY VOLUME)")
    print("=" * 75)
    print(f"{'Thread ID':<15} {'Start Date':<17} {'Msgs':<6} {'Words':<8} {'Duration':<10} {'Initiator'}")
    print("-" * 75)
    for r in rows:
        print(f"{r['thread_id']:<15} {r['start_date']:<17} {r['message_count']:<6} {r['total_words']:<8} {r['duration']:<10} {r['initiator']}")


def print_semantic_results(concept: str, results: List[Dict[str, Any]]):
    print(f"\n🧠 Semantic Psychological Search for: '{concept}'")
    print("=" * 70)
    for i, res in enumerate(results, 1):
        print(f"\n[{i}] Thread: {res['thread_id']} | Date: {res['start_date'][:10]} | Relevance Score: {res['score']}")
        print(f"Participants: {res['participants']}")
        print(res["dialogue_text"])
        print("-" * 70)


# ==============================================================================
# MAIN CONTROLLER & BATCH DISPATCHER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Query CLI for Telegram analytical chat database (supports multi-query and batch modes)."
    )
    parser.add_argument("--db", default="chat_index.db", help="Path to SQLite database")
    parser.add_argument("--stats", action="store_true", help="Display Phase 1 quantitative metrics")
    parser.add_argument("--gaps", action="store_true", help="Display silence and reconnection initiative analysis")
    parser.add_argument("--min-hours", type=float, default=24.0, help="Minimum silence duration in hours (default: 24)")
    parser.add_argument("--timeline", action="store_true", help="Display monthly activity timeline")
    parser.add_argument("--burning-days", action="store_true", help="Display statistically anomalous high-activity days (burning days)")
    parser.add_argument("--intensive-threads", action="store_true", help="Display substantive dialogue threads ranked by volume (anti-noise)")
    parser.add_argument("--min-words", type=int, default=50, help="Minimum total words for --intensive-threads (default: 50)")
    parser.add_argument("--min-messages", type=int, default=6, help="Minimum messages for --intensive-threads (default: 6)")

    # Repeatable flags for multi-query execution
    parser.add_argument("--search", "-s", action="append", help="Search individual messages via FTS5 (can be repeated)")
    parser.add_argument("--search-threads", "-st", action="append", help="Search full dialogue threads via FTS5 (can be repeated)")
    parser.add_argument("--thread", "-t", action="append", help="Display full transcript of a thread by thread_id or message_id (can be repeated)")
    parser.add_argument("--from-msg", "-f", action="append", type=int, help="Display a slice of a thread starting from this message_id (can be repeated)")
    parser.add_argument("--window", "-w", type=int, default=0, help="Number of preceding messages to show before --from-msg (default: 0)")
    parser.add_argument("--chain", "-c", action="append", type=int, help="Display direct causal quote chain for a message_id (can be repeated)")
    parser.add_argument("--semantic", "-sem", action="append", help="Search threads by psychological concept/meaning (can be repeated)")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Maximum number of results to display per query (default: 10)")

    # Agent productivity features
    parser.add_argument("--json", action="store_true", help="Output all results in structured JSON format")
    parser.add_argument("--batch-json", type=str, help="JSON string or file path containing multiple query directives")

    args = parser.parse_args()

    # Support batch directives from JSON file or JSON string
    batch_config: Dict[str, Any] = {}
    if args.batch_json:
        if os.path.exists(args.batch_json):
            with open(args.batch_json, "r", encoding="utf-8") as f:
                batch_config = json.load(f)
        else:
            try:
                batch_config = json.loads(args.batch_json)
            except Exception as e:
                print(f"[!] Error parsing --batch-json: {e}")
                sys.exit(1)

    # Merge CLI flags with batch config
    run_stats = args.stats or batch_config.get("stats", False)
    run_gaps = args.gaps or batch_config.get("gaps", False)
    run_timeline = args.timeline or batch_config.get("timeline", False)
    run_burning = args.burning_days or batch_config.get("burning_days", False)
    run_intensive = args.intensive_threads or batch_config.get("intensive_threads", False)
    min_hours = batch_config.get("min_hours", args.min_hours)
    min_words = batch_config.get("min_words", args.min_words)
    min_messages = batch_config.get("min_messages", args.min_messages)
    limit = batch_config.get("limit", args.limit)
    window = batch_config.get("window", args.window)

    def extract_list(cli_arg: Optional[List[Any]], config_key: str) -> List[Any]:
        items = list(cli_arg or [])
        from_cfg = batch_config.get(config_key)
        if isinstance(from_cfg, list):
            items.extend(from_cfg)
        elif isinstance(from_cfg, (str, int)):
            items.append(from_cfg)
        return items

    search_queries = extract_list(args.search, "search")
    search_thread_queries = extract_list(args.search_threads, "search_threads")
    thread_ids = [str(x) for x in extract_list(args.thread, "thread")]
    from_msgs = [int(x) for x in extract_list(args.from_msg, "from_msg")]
    chains = [int(x) for x in extract_list(args.chain, "chain")]
    semantic_queries = [str(x) for x in extract_list(args.semantic, "semantic")]

    has_actions = any([
        run_stats, run_gaps, run_timeline, run_burning, run_intensive,
        search_queries, search_thread_queries, thread_ids,
        from_msgs, chains, semantic_queries
    ])

    if not has_actions:
        parser.print_help()
        sys.exit(0)

    if not os.path.exists(args.db):
        print(f"[!] Database file '{args.db}' not found.")
        print("    Build it first using: python3 project/scripts/db_builder.py <path_to_export.json> -o chat_index.db")
        sys.exit(1)

    # Dictionary to aggregate all results for structured JSON mode
    aggregated: Dict[str, Any] = {}

    # 1. Quantitative Stats
    if run_stats:
        stats_data = get_stats(args.db)
        if args.json:
            aggregated["stats"] = stats_data
        else:
            print_stats(stats_data)

    # 2. Silence Gaps
    if run_gaps:
        gaps_data = get_silence_gaps(args.db, min_hours)
        if args.json:
            aggregated["silence_gaps"] = gaps_data
        else:
            print_silence_gaps(gaps_data)

    # 3. Monthly Timeline
    if run_timeline:
        timeline_data = get_timeline(args.db)
        if args.json:
            aggregated["timeline"] = timeline_data
        else:
            print_timeline(timeline_data)

    # 3.5. Burning Days (Statistical Conversation Outliers)
    if run_burning:
        burning_data = get_burning_days(args.db)
        if args.json:
            aggregated["burning_days"] = burning_data
        else:
            print_burning_days(burning_data)

    # 3.6. Substantive Dialogue Threads (Ranked by Volume)
    if run_intensive:
        intensive_data = get_intensive_threads(args.db, min_words=min_words, min_messages=min_messages, limit=limit)
        if args.json:
            aggregated["intensive_threads"] = intensive_data
        else:
            print_intensive_threads(intensive_data)

    # 4. Message Keyword Searches
    if search_queries:
        search_res = {}
        for q in search_queries:
            res = get_search_messages(args.db, q, limit)
            search_res[q] = res
            if not args.json:
                print_search_messages(q, res)
        if args.json:
            aggregated["search_messages"] = search_res

    # 5. Thread Keyword Searches
    if search_thread_queries:
        st_res = {}
        for q in search_thread_queries:
            res = get_search_threads_fts(args.db, q, limit)
            st_res[q] = res
            if not args.json:
                print_search_threads(q, res)
        if args.json:
            aggregated["search_threads"] = st_res

    # 6. Full Thread Transcripts
    if thread_ids:
        t_res = {}
        for tid in thread_ids:
            res = get_thread(args.db, tid)
            t_res[tid] = res
            if not args.json:
                print_thread(res, tid)
        if args.json:
            aggregated["threads"] = t_res

    # 7. Thread Slices
    if from_msgs:
        slice_res = {}
        for fmsg in from_msgs:
            res = get_thread_slice(args.db, fmsg, limit=limit, window_before=window)
            slice_res[str(fmsg)] = res
            if not args.json:
                print_thread_slice(res, fmsg)
        if args.json:
            aggregated["thread_slices"] = slice_res

    # 8. Causal Quote Chains
    if chains:
        chain_res = {}
        for cid in chains:
            res = get_quote_chain(args.db, cid)
            chain_res[str(cid)] = res
            if not args.json:
                print_quote_chain(res, cid)
        if args.json:
            aggregated["quote_chains"] = chain_res

    # 9. Semantic Psychological Search (Executed in single batch)
    if semantic_queries:
        sem_res = get_semantic_batch_results(args.db, semantic_queries, top_k=limit)
        if args.json:
            aggregated["semantic_search"] = sem_res
        else:
            for q, results in sem_res.items():
                print_semantic_results(q, results)

    # Output JSON if requested
    if args.json:
        print(json.dumps(aggregated, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
