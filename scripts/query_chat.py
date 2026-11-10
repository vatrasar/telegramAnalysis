#!/usr/bin/env python3
"""
Telegram Multi-Chat Analysis Query CLI.
Provides quantitative mining (Phase 1) and qualitative psychological retrieval (Phase 2)
over preprocessed SQLite and vector chat data with multi-chat support.

Supports:
- Multi-chat filtering via --chat <chat_id_or_name> and chat catalog via --list-chats
- Multi-query simultaneous execution (e.g. --stats --gaps --timeline in one call)
- Repeated batch queries (--semantic "q1" --semantic "q2" or -s "term1" -s "term2")
- Batch JSON execution via --batch-json <file_or_string>
- Structured JSON output mode via --json (agent-friendly token-efficient output)
"""

import os
import sys
import re
import json
import math
import sqlite3
import argparse
import datetime as dt_module
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

try:
    from vector_indexer import search_semantic, search_semantic_batch
except ImportError:
    search_semantic = None
    search_semantic_batch = None

try:
    from triage_threads import verify_unregistered_entities_decider
except ImportError:
    verify_unregistered_entities_decider = None


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
# CHAT RESOLUTION & CATALOG
# ==============================================================================

def get_chats_catalog(db_path: str) -> List[Dict[str, Any]]:
    """Retrieve catalog of all indexed chats in the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chats';")
    if cur.fetchone()[0] == 0:
        conn.close()
        return []

    cur.execute("""
    SELECT chat_id, chat_name, chat_type, source_files, total_messages, total_threads, start_date, end_date
    FROM chats
    ORDER BY total_messages DESC;
    """)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "chat_id": r[0],
            "chat_name": r[1],
            "chat_type": r[2],
            "source_files": r[3],
            "total_messages": r[4],
            "total_threads": r[5],
            "start_date": r[6][:10] if r[6] else None,
            "end_date": r[7][:10] if r[7] else None
        }
        for r in rows
    ]


def resolve_chat(db_path: str, chat_arg: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve chat_arg into (chat_id, chat_name).
    Matches by exact chat_id, exact chat_name, or case-insensitive substring.
    """
    if not chat_arg:
        return None, None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chats';")
    if cur.fetchone()[0] == 0:
        conn.close()
        return chat_arg, chat_arg

    # 1. Exact match on chat_id
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE chat_id = ?;", (chat_arg,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0], row[1]

    # 2. Case-insensitive exact match on chat_name
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE lower(chat_name) = lower(?);", (chat_arg,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0], row[1]

    # 3. Case-insensitive substring match
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE lower(chat_name) LIKE lower(?);", (f"%{chat_arg}%",))
    rows = cur.fetchall()
    conn.close()

    if len(rows) == 1:
        return rows[0][0], rows[0][1]
    elif len(rows) > 1:
        print(f"[!] Ambiguous chat identifier '{chat_arg}'. Matches multiple chats:")
        for r in rows:
            print(f"    - ID: {r[0]} | Name: '{r[1]}'")
        print("    Please specify an exact chat_id using --chat <id>.")
        sys.exit(1)

    print(f"[!] Chat '{chat_arg}' not found in database.")
    print("    Available chats:")
    catalog = get_chats_catalog(db_path)
    for c in catalog:
        print(f"    - {c['chat_id']}: '{c['chat_name']}' ({c['total_messages']} msgs)")
    sys.exit(1)


# ==============================================================================
# DATA RETRIEVAL FUNCTIONS (PURE DATA)
# ==============================================================================

def get_stats(db_path: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve Phase 1 quantitative metrics as structured data (global or chat-specific)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    where_msg = "WHERE chat_id = ?" if chat_id else ""
    where_thr = "WHERE chat_id = ?" if chat_id else ""
    where_gap = "WHERE chat_id = ?" if chat_id else ""
    params = [chat_id] if chat_id else []

    cur.execute(f"SELECT count(*), min(date), max(date) FROM messages {where_msg};", params)
    total_msgs, min_date, max_date = cur.fetchone()

    cur.execute(f"SELECT count(*) FROM threads {where_thr};", params)
    total_threads = cur.fetchone()[0]

    cur.execute(f"SELECT count(*) FROM silence_gaps {where_gap};", params)
    total_gaps = cur.fetchone()[0]

    # Thread initiator metrics
    cur.execute(f"""
    SELECT initiator, count(*)
    FROM threads
    {where_thr}
    GROUP BY initiator;
    """, params)
    thread_initiators = dict(cur.fetchall())

    # Pre-calculate active chat message and thread counts for normalized in-chat share %
    chat_msg_counts: Dict[str, int] = {}
    chat_thread_counts: Dict[str, int] = {}
    participant_chats_map: Dict[str, List[str]] = {}
    participant_chat_ids: Dict[str, Set[str]] = {}
    if not chat_id:
        cur.execute("SELECT chat_id, count(*) FROM messages GROUP BY chat_id;")
        for cid, ccount in cur.fetchall():
            chat_msg_counts[cid] = ccount

        cur.execute("SELECT chat_id, count(*) FROM threads GROUP BY chat_id;")
        for cid, tcount in cur.fetchall():
            chat_thread_counts[cid] = tcount

        cur.execute("""
        SELECT DISTINCT m.sender, c.chat_name, m.chat_id
        FROM messages m
        JOIN chats c ON m.chat_id = c.chat_id;
        """)
        for snd, cname, cid in cur.fetchall():
            participant_chats_map.setdefault(snd, []).append(cname)
            participant_chat_ids.setdefault(snd, set()).add(cid)

    # Participant metrics
    cur.execute(f"""
    SELECT sender, count(*), round(avg(word_count), 1), sum(word_count)
    FROM messages
    {where_msg}
    GROUP BY sender
    ORDER BY count(*) DESC;
    """, params)
    participants = []
    for row in cur.fetchall():
        sender, count, avg_w, sum_w = row
        pct = round((count / total_msgs * 100), 1) if total_msgs else 0.0

        chats_active = participant_chats_map.get(sender, [])
        if not chat_id and sender in participant_chat_ids:
            active_chat_total_msgs = sum(chat_msg_counts.get(cid, 0) for cid in participant_chat_ids[sender])
            in_chat_pct = round((count / active_chat_total_msgs * 100), 1) if active_chat_total_msgs else 0.0
            active_chat_total_threads = sum(chat_thread_counts.get(cid, 0) for cid in participant_chat_ids[sender])
        else:
            in_chat_pct = pct
            active_chat_total_threads = total_threads

        t_started = thread_initiators.get(sender, 0)
        t_share_pct = round((t_started / total_threads * 100), 1) if total_threads else 0.0
        in_chat_t_pct = round((t_started / active_chat_total_threads * 100), 1) if active_chat_total_threads else 0.0

        participants.append({
            "sender": sender,
            "messages": count,
            "share_percentage": pct,
            "in_chat_share_percentage": in_chat_pct,
            "threads_started": t_started,
            "threads_share_percentage": t_share_pct,
            "in_chat_threads_share_percentage": in_chat_t_pct,
            "avg_words_per_msg": avg_w or 0.0,
            "total_words": sum_w or 0,
            "chats_active": chats_active
        })

    # Catalog breakdown if overall stats
    chats_data = []
    if not chat_id:
        cur.execute("""
        SELECT c.chat_id, c.chat_name, c.total_messages, c.total_threads, c.start_date, c.end_date
        FROM chats c
        ORDER BY c.total_messages DESC;
        """)
        for r in cur.fetchall():
            chats_data.append({
                "chat_id": r[0],
                "chat_name": r[1],
                "messages": r[2],
                "threads": r[3],
                "date_range": f"{r[4][:10] if r[4] else ''} to {r[5][:10] if r[5] else ''}"
            })

    conn.close()
    return {
        "filtered_chat_id": chat_id,
        "total_chats": len(chats_data) if not chat_id else 1,
        "total_messages": total_msgs or 0,
        "total_threads": total_threads or 0,
        "long_silences_over_24h": total_gaps or 0,
        "date_range": {
            "start": str(min_date)[:10] if min_date else None,
            "end": str(max_date)[:10] if max_date else None
        },
        "chats": chats_data,
        "participants": participants
    }


def get_silence_gaps(db_path: str, min_hours: float = 24.0, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve silence gaps and initiative ratios (calculated strictly per chat and normalized)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT g.chat_id, coalesce(c.chat_name, g.chat_id) as chat_name,
           g.silence_start_date, g.silence_end_date, g.silence_duration_seconds,
           g.last_sender, g.initiator, g.after_thread_id
    FROM silence_gaps g
    LEFT JOIN chats c ON g.chat_id = c.chat_id
    WHERE g.silence_duration_hours >= ?
    """
    params: List[Any] = [min_hours]
    if chat_id:
        sql += " AND g.chat_id = ? "
        params.append(chat_id)

    sql += " ORDER BY g.silence_duration_seconds DESC; "
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Pre-fetch participants per chat to track all interlocutors (even if 0 silence breaks)
    chat_participants_map: Dict[str, Set[str]] = {}
    cur.execute("SELECT DISTINCT chat_id, sender FROM messages;")
    for cid, snd in cur.fetchall():
        chat_participants_map.setdefault(cid, set()).add(snd)

    gaps_list = []
    chats_gaps_map: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        c_id = r[0]
        c_name = r[1]
        init = r[6]

        if c_id not in chats_gaps_map:
            chats_gaps_map[c_id] = {
                "chat_id": c_id,
                "chat_name": c_name,
                "total_gaps": 0,
                "initiators": {}
            }
        chats_gaps_map[c_id]["total_gaps"] += 1
        c_inits = chats_gaps_map[c_id]["initiators"]
        c_inits[init] = c_inits.get(init, 0) + 1

        gaps_list.append({
            "chat_id": r[0],
            "chat_name": r[1],
            "start_date": r[2],
            "end_date": r[3],
            "duration_seconds": r[4],
            "duration_formatted": format_duration(r[4]),
            "last_sender": r[5],
            "initiator": r[6],
            "after_thread_id": r[7]
        })

    total_gaps = len(rows)

    # Build per-chat relational breakdown
    chat_initiatives = []
    for c_id, c_data in sorted(chats_gaps_map.items(), key=lambda x: x[1]["total_gaps"], reverse=True):
        c_total = c_data["total_gaps"]
        known_parts = chat_participants_map.get(c_id, set(c_data["initiators"].keys()))
        chat_init_list = []
        for p in known_parts:
            cnt = c_data["initiators"].get(p, 0)
            chat_init_list.append({
                "sender": p,
                "count": cnt,
                "percentage": round((cnt / c_total * 100), 1) if c_total else 0.0
            })
        chat_init_list.sort(key=lambda x: x["count"], reverse=True)
        chat_initiatives.append({
            "chat_id": c_id,
            "chat_name": c_data["chat_name"],
            "total_gaps": c_total,
            "initiatives": chat_init_list
        })

    # Normalized participant initiatives across relevant chats (Anti-Simpson's Paradox)
    participant_gaps_pool: Dict[str, int] = {}
    participant_breaks: Dict[str, int] = {}

    for c_id, c_data in chats_gaps_map.items():
        c_total = c_data["total_gaps"]
        known_parts = chat_participants_map.get(c_id, set(c_data["initiators"].keys()))
        for p in known_parts:
            participant_gaps_pool[p] = participant_gaps_pool.get(p, 0) + c_total
        for p, cnt in c_data["initiators"].items():
            participant_breaks[p] = participant_breaks.get(p, 0) + cnt

    all_senders = sorted(participant_breaks.keys(), key=lambda x: participant_breaks[x], reverse=True)
    init_stats = []
    for sender in all_senders:
        cnt = participant_breaks[sender]
        rel_gaps = participant_gaps_pool.get(sender, total_gaps)
        in_chat_pct = round((cnt / rel_gaps * 100), 1) if rel_gaps else 0.0
        raw_corpus_pct = round((cnt / total_gaps * 100), 1) if total_gaps else 0.0

        init_stats.append({
            "sender": sender,
            "count": cnt,
            "in_chat_gaps_total": rel_gaps,
            "in_chat_percentage": in_chat_pct,
            "raw_corpus_percentage": raw_corpus_pct,
            "percentage": in_chat_pct
        })

    conn.close()
    return {
        "filtered_chat_id": chat_id,
        "min_hours": min_hours,
        "total_gaps": total_gaps,
        "initiative_stats": init_stats,
        "chat_initiatives": chat_initiatives,
        "longest_gaps": gaps_list[:15]
    }


def get_timeline(db_path: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve monthly message counts per participant."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT substr(date, 1, 7) as month, sender, count(*)
    FROM messages
    """
    params = []
    if chat_id:
        sql += " WHERE chat_id = ? "
        params.append(chat_id)

    sql += " GROUP BY month, sender ORDER BY month ASC; "
    cur.execute(sql, params)
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
        "filtered_chat_id": chat_id,
        "senders": sorted_senders,
        "months": monthly_data
    }


def get_burning_days(
    db_path: str,
    std_multiplier: float = 2.0,
    min_msgs: int = 15,
    chat_id: Optional[str] = None
) -> Dict[str, Any]:
    """Identify statistically anomalous high-activity days (mu + 2*sigma)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT substr(date, 1, 10) as day, count(*), sum(word_count)
    FROM messages
    """
    params = []
    if chat_id:
        sql += " WHERE chat_id = ? "
        params.append(chat_id)

    sql += " GROUP BY day ORDER BY day ASC; "
    cur.execute(sql, params)
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
    if not candidates and n > 0:
        sorted_rows = sorted(rows, key=lambda x: x[1], reverse=True)
        candidates = sorted_rows[:min(5, n)]

    burning_days = []
    for day, msg_count, word_count in sorted(candidates, key=lambda x: x[1], reverse=True):
        cur.execute("""
        SELECT sender, count(*) FROM messages
        WHERE substr(date, 1, 10) = ?
        GROUP BY sender ORDER BY count(*) DESC LIMIT 1;
        """, (day,))
        top_s_row = cur.fetchone()
        top_sender = top_s_row[0] if top_s_row else "Unknown"

        cur.execute("""
        SELECT DISTINCT m.chat_id, coalesce(c.chat_name, m.chat_id)
        FROM messages m
        LEFT JOIN chats c ON m.chat_id = c.chat_id
        WHERE substr(m.date, 1, 10) = ?;
        """, (day,))
        active_chats = [r[1] for r in cur.fetchall()]

        cur.execute("""
        SELECT DISTINCT thread_id FROM messages
        WHERE substr(date, 1, 10) = ?;
        """, (day,))
        thread_ids = [r[0] for r in cur.fetchall()]

        burning_days.append({
            "date": day,
            "messages": msg_count,
            "words": word_count or 0,
            "top_participant": top_sender,
            "active_chats": active_chats,
            "active_threads_count": len(thread_ids),
            "thread_ids": thread_ids
        })

    conn.close()
    return {
        "filtered_chat_id": chat_id,
        "total_active_days": n,
        "mean_daily_messages": round(mean_count, 1),
        "std_daily_messages": round(std_count, 1),
        "anomaly_threshold_messages": threshold,
        "burning_days_count": len(burning_days),
        "burning_days": burning_days
    }


def get_intensive_threads(
    db_path: str,
    min_words: int = 50,
    min_messages: int = 6,
    limit: int = 25,
    chat_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve dialogue threads ranked by substantive conversational volume, filtering small-talk noise."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id) as chat_name,
           t.start_date, t.end_date, t.message_count, sum(m.word_count) as total_words,
           t.participants, t.initiator, t.duration_seconds
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    """
    params: List[Any] = []
    if chat_id:
        sql += " WHERE t.chat_id = ? "
        params.append(chat_id)

    sql += """
    GROUP BY t.thread_id
    HAVING t.message_count >= ? AND total_words >= ?
    ORDER BY total_words DESC
    LIMIT ?;
    """
    params.extend([min_messages, min_words, limit])

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "thread_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "start_date": r[3][:16].replace("T", " "),
            "end_date": r[4][:16].replace("T", " "),
            "message_count": r[5],
            "total_words": r[6] or 0,
            "participants": r[7],
            "initiator": r[8],
            "duration": format_duration(r[9] or 0)
        })
    return results


def get_triaged_threads(
    db_path: str,
    limit: int = 25,
    chat_id: Optional[str] = None,
    min_salience: float = 0.0,
    category: Optional[str] = None,
    anomalies_only: bool = False,
    emotional_peaks_only: bool = False,
    peak_type: Optional[str] = None,
    advice_seeking_only: bool = False
) -> List[Dict[str, Any]]:
    """Retrieve dialogue threads qualified by System-1 (Jev) triage for LLM profiling."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage'")
    if cur.fetchone()[0] == 0:
        conn.close()
        return []

    # Check available columns in thread_triage
    cur.execute("PRAGMA table_info(thread_triage)")
    cols = {col[1] for col in cur.fetchall()}
    has_anom = "is_atypical" in cols
    has_peak = "emotional_peak" in cols
    has_advice = "is_advice_seeking" in cols

    atyp_col = "tr.is_atypical" if has_anom else "0"
    surp_col = "tr.interlocutor_surprised" if has_anom else "0"
    note_col = "tr.anomaly_notes" if has_anom else "''"
    peak_col = "tr.emotional_peak" if has_peak else "'none'"
    adv_col = "tr.is_advice_seeking" if has_advice else "0"

    sql = f"""
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id) as chat_name,
           t.start_date, t.end_date, t.message_count, sum(m.word_count) as total_words,
           t.participants, tr.salience_score, tr.primary_category, tr.reason,
           {atyp_col}, {surp_col}, {note_col}, {peak_col}, {adv_col}
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    JOIN messages m ON t.thread_id = m.thread_id
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    WHERE tr.escalate = 1
    """

    params: List[Any] = []
    if chat_id:
        sql += " AND t.chat_id = ? "
        params.append(chat_id)
    if min_salience > 0.0:
        sql += " AND tr.salience_score >= ? "
        params.append(min_salience)
    if category:
        sql += " AND tr.primary_category = ? "
        params.append(category)
    if anomalies_only and has_anom:
        sql += " AND (tr.is_atypical = 1 OR tr.interlocutor_surprised = 1) "
    if emotional_peaks_only and has_peak:
        if peak_type:
            sql += " AND tr.emotional_peak = ? "
            params.append(peak_type)
        else:
            sql += " AND tr.emotional_peak != 'none' "
    if advice_seeking_only and has_advice:
        sql += " AND tr.is_advice_seeking = 1 "

    sql += """
    GROUP BY t.thread_id
    ORDER BY tr.salience_score DESC, total_words DESC
    LIMIT ?;
    """
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "thread_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "start_date": r[3][:16].replace("T", " "),
            "end_date": r[4][:16].replace("T", " "),
            "message_count": r[5],
            "total_words": r[6] or 0,
            "participants": r[7],
            "salience_score": r[8],
            "category": r[9],
            "reason": r[10] or "",
            "is_atypical": r[11] or 0,
            "interlocutor_surprised": r[12] or 0,
            "anomaly_notes": r[13] or "",
            "emotional_peak": r[14] or "none",
            "is_advice_seeking": r[15] or 0
        })
    return results


def get_search_messages(
    db_path: str,
    query: str,
    limit: int = 15,
    chat_id: Optional[str] = None
) -> List[Dict[str, Any]]:
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
        sql = """
        SELECT mf.message_id, mf.chat_id, coalesce(c.chat_name, mf.chat_id) as chat_name,
               mf.date, mf.sender, mf.thread_id, snippet(messages_fts, 5, '【', '】', '...', 15)
        FROM messages_fts mf
        LEFT JOIN chats c ON mf.chat_id = c.chat_id
        WHERE messages_fts MATCH ?
        """
        p: List[Any] = [fts_query]
        if chat_id:
            sql += " AND mf.chat_id = ? "
            p.append(chat_id)
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


def get_thread(db_path: str, identifier: str, chat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch full dialogue transcript of a thread by thread_id or message_id."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    target_thread_id = identifier
    cur.execute("""
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.anchor_message_id,
           t.start_date, t.end_date, t.message_count, t.participants, t.initiator, t.dialogue_text
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
                cur.execute("""
                SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id), t.anchor_message_id,
                       t.start_date, t.end_date, t.message_count, t.participants, t.initiator, t.dialogue_text
                FROM threads t
                LEFT JOIN chats c ON t.chat_id = c.chat_id
                WHERE t.thread_id = ?;
                """, (target_thread_id,))
                row = cur.fetchone()
        except ValueError:
            pass

    conn.close()
    if not row:
        return None

    return {
        "thread_id": row[0],
        "chat_id": row[1],
        "chat_name": row[2],
        "anchor_message_id": row[3],
        "start_date": row[4],
        "end_date": row[5],
        "message_count": row[6],
        "participants": row[7],
        "initiator": row[8],
        "dialogue_text": row[9]
    }


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


def get_chronological_around(
    db_path: str,
    msg_id: int,
    window: int = 5,
    chat_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieve chronological messages surrounding msg_id strictly by timestamp/id,
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


# ==============================================================================
# PRESENTATION FUNCTIONS (CLI ASCII FORMATTING)
# ==============================================================================

def print_chats_catalog(chats: List[Dict[str, Any]]):
    print("\n" + "=" * 80)
    print("📁 INDEXED CHATS CATALOG")
    print("=" * 80)
    if not chats:
        print("No chats found in database.")
        return

    print(f"{'Chat ID':<16} {'Chat Name':<24} {'Messages':<10} {'Threads':<10} {'Date Range':<22}")
    print("-" * 84)
    for c in chats:
        c_id = c["chat_id"][:14]
        c_name = c["chat_name"][:22]
        d_range = f"{c['start_date'] or ''} to {c['end_date'] or ''}"
        print(f"{c_id:<16} {c_name:<24} {c['total_messages']:<10,} {c['total_threads']:<10,} {d_range:<22}")
    print("=" * 80)


def print_stats(stats: Dict[str, Any]):
    filter_label = f" [Chat: {stats['filtered_chat_id']}]" if stats.get("filtered_chat_id") else " [All Chats Combined]"
    print("\n" + "=" * 65)
    print(f"📊 QUANTITATIVE OVERVIEW (PHASE 1){filter_label}")
    print("=" * 65)
    print(f"Total Indexed Chats:  {stats['total_chats']}")
    print(f"Total Messages:       {stats['total_messages']:,}")
    print(f"Total Threads:        {stats['total_threads']:,}")
    print(f"Long Silences (>24h): {stats['long_silences_over_24h']:,}")
    print(f"Date Range:           {stats['date_range']['start']} to {stats['date_range']['end']}")

    if stats.get("chats") and len(stats["chats"]) > 1:
        print("\n💬 CHAT BREAKDOWN:")
        print(f"{'Chat ID':<16} {'Chat Name':<22} {'Messages':<10} {'Threads':<10} {'Date Range'}")
        print("-" * 75)
        for c in stats["chats"]:
            print(f"{c['chat_id']:<16} {c['chat_name']:<22} {c['messages']:<10,} {c['threads']:<10,} {c['date_range']}")

    print("\n👥 PARTICIPANT METRICS:")
    if stats.get("total_chats", 1) > 1:
        print(f"{'Sender':<18} {'Messages':<9} {'Global %':<10} {'In-Chat %':<11} {'Threads (In-Chat %)':<21} {'Avg W/Msg':<10} {'Active Chats'}")
        print("-" * 98)
        for p in stats["participants"]:
            c_str = ", ".join(p.get("chats_active", []))[:24]
            th_str = f"{p.get('threads_started', 0)} ({p.get('in_chat_threads_share_percentage', 0.0):.1f}%)"
            glob_pct = f"{p['share_percentage']:.1f}%"
            in_pct = f"{p.get('in_chat_share_percentage', p['share_percentage']):.1f}%"
            print(f"{p['sender']:<18} {p['messages']:<9,} {glob_pct:<10} {in_pct:<11} {th_str:<21} {p['avg_words_per_msg']:<10} {c_str}")
    else:
        print(f"{'Sender':<18} {'Messages':<9} {'Share %':<10} {'Threads Started':<18} {'Avg Words/Msg':<14} {'Total Words':<12}")
        print("-" * 84)
        for p in stats["participants"]:
            th_str = f"{p.get('threads_started', 0)} ({p.get('threads_share_percentage', 0.0):.1f}%)"
            share_pct = f"{p['share_percentage']:.1f}%"
            print(f"{p['sender']:<18} {p['messages']:<9,} {share_pct:<10} {th_str:<18} {p['avg_words_per_msg']:<14} {p['total_words']:<12,}")


def print_silence_gaps(data: Dict[str, Any]):
    filter_label = f" [Chat: {data['filtered_chat_id']}]" if data.get("filtered_chat_id") else ""
    print("\n" + "=" * 85)
    print(f"⏳ CONVERSATION GAPS & RECONNECTION INITIATIVE (>= {data['min_hours']}h){filter_label}")
    print("=" * 85)

    if not data["longest_gaps"]:
        print(f"No silences found exceeding {data['min_hours']} hours.")
        return

    chat_inits = data.get("chat_initiatives", [])
    if len(chat_inits) > 1:
        print("\nInitiative Ratio (Per-Chat Relational Breakdown):")
        for ci in chat_inits:
            print(f"  📁 Chat '{ci['chat_name']}' ({ci['total_gaps']} silences >= {data['min_hours']}h):")
            for s in ci["initiatives"]:
                print(f"    - {s['sender']:<18}: {s['count']:>3} times ({s['percentage']:>5.1f}%)")

        print("\nOverall Participant Initiative (Normalized to Active Chats):")
        for s in data["initiative_stats"]:
            print(f"  - {s['sender']:<18}: {s['count']:>3} / {s['in_chat_gaps_total']:<3} times ({s['in_chat_percentage']:>5.1f}% in-chat, raw corpus share: {s['raw_corpus_percentage']}%)")
    else:
        print("\nInitiative Ratio (Who breaks the silence):")
        for s in data["initiative_stats"]:
            print(f"  - {s['sender']:<18}: {s['count']} times ({s['percentage']}%)")

    print(f"\nTop Longest Silences:")
    print(f"{'Chat':<14} {'Silence Period':<35} {'Duration':<12} {'Last Spoke':<12} {'Broke Silence':<12}")
    print("-" * 88)
    for g in data["longest_gaps"]:
        c_label = g.get("chat_name", g.get("chat_id", ""))[:12]
        start_d = g["start_date"][:16].replace("T", " ")
        end_d = g["end_date"][:16].replace("T", " ")
        dur_str = g["duration_formatted"]
        last_s = g["last_sender"][:11]
        init_s = g["initiator"][:11]
        print(f"{c_label:<14} {start_d} -> {end_d:<16} {dur_str:<12} {last_s:<12} {init_s:<12}")


def print_timeline(data: Dict[str, Any]):
    filter_label = f" [Chat: {data['filtered_chat_id']}]" if data.get("filtered_chat_id") else ""
    print("\n" + "=" * 65)
    print(f"📅 MONTHLY TIMELINE DISTRIBUTION{filter_label}")
    print("=" * 65)
    senders = data["senders"]
    header = f"{'Month':<10} " + " ".join([f"{s[:12]:<12}" for s in senders]) + " Total"
    print(header)
    print("-" * len(header))

    for m in data["months"]:
        counts_str = " ".join([f"{m.get(s, 0):<12}" for s in senders])
        print(f"{m['month']:<10} {counts_str} {m['total']}")


def print_burning_days(data: Dict[str, Any]):
    filter_label = f" [Chat: {data['filtered_chat_id']}]" if data.get("filtered_chat_id") else ""
    print("\n" + "=" * 75)
    print(f"🔥 STATISTICALLY ANOMALOUS CONVERSATION DAYS (BURNING DAYS){filter_label}")
    print("=" * 75)
    print(f"Active Days Analyzed:   {data['total_active_days']}")
    print(f"Daily Message Baseline: {data['mean_daily_messages']} msgs/day (std: {data['std_daily_messages']})")
    print(f"Outlier Cutoff (μ+2σ):  {data['anomaly_threshold_messages']} msgs/day")
    print(f"Detected Burning Days:  {data['burning_days_count']}")

    if not data["burning_days"]:
        print("No burning days detected exceeding the statistical threshold.")
        return

    print("\nTop Intensity Days:")
    print(f"{'Date':<12} {'Messages':<10} {'Words':<10} {'Top Speaker':<16} {'Active Chats / Topics'}")
    print("-" * 75)
    for b in data["burning_days"][:15]:
        chats_str = ", ".join(b.get("active_chats", []))[:20]
        print(f"{b['date']:<12} {b['messages']:<10,} {b['words']:<10,} {b['top_participant'][:15]:<16} {chats_str} ({b['active_threads_count']} threads)")


def print_intensive_threads(threads: List[Dict[str, Any]]):
    print("\n" + "=" * 80)
    print(f"💬 SUBSTANTIVE DIALOGUE THREADS (RANKED BY CONVERSATIONAL VOLUME)")
    print("=" * 80)
    if not threads:
        print("No intensive dialogue threads found meeting criteria.")
        return

    print(f"{'Thread ID':<22} {'Chat':<14} {'Date':<17} {'Msgs':<6} {'Words':<8} {'Participants'}")
    print("-" * 80)
    for t in threads:
        c_label = t.get("chat_name", t.get("chat_id", ""))[:12]
        print(f"{t['thread_id']:<22} {c_label:<14} {t['start_date']:<17} {t['message_count']:<6} {t['total_words']:<8,} {t['participants']}")


def print_triaged_threads(threads: List[Dict[str, Any]]):
    print("\n" + "=" * 95)
    print("🧠 TRIAGED HIGH-SALIENCE DIALOGUE THREADS (SYSTEM-1 JEV QUALIFIED)")
    print("=" * 95)
    if not threads:
        print("No triaged threads found meeting criteria (or run 'python3 .agents/scripts/triage_threads.py' first).")
        return

    print(f"{'Flag':<5} {'Thread ID':<22} {'Date':<17} {'Score':<6} {'Category':<22} {'Msgs':<5} {'Words':<7} {'Reason'}")
    print("-" * 95)
    for t in threads:
        flags = []
        if t.get("is_atypical") or t.get("interlocutor_surprised"):
            flags.append("⚡")
        peak = t.get("emotional_peak", "none")
        if peak == "profound_sadness":
            flags.append("😢")
        elif peak == "euphoric_joy":
            flags.append("🎉")
        elif peak == "intense_rage":
            flags.append("😡")
        if t.get("is_advice_seeking"):
            flags.append("💡")
        flag_str = "".join(flags)
        flag_display = f"{flag_str:<5}" if flag_str else "     "
        r_snippet = (t.get("reason", "") or "")[:25]
        print(f"{flag_display} {t['thread_id']:<22} {t['start_date']:<17} {t['salience_score']:<6.1f} {t['category'][:21]:<22} {t['message_count']:<5} {t['total_words']:<7,} {r_snippet}")
        if t.get("anomaly_notes"):
            print(f"     ↳ [RADAR NOTES] {t['anomaly_notes']}")


def print_search_messages(query: str, rows: List[Dict[str, Any]]):
    print("\n" + "=" * 70)
    print(f"🔍 MESSAGE SEARCH: '{query}' ({len(rows)} matches)")
    print("=" * 70)
    if not rows:
        print("No matching messages found.")
        return

    for r in rows:
        c_label = f" | Chat: {r.get('chat_name', r.get('chat_id'))}" if r.get("chat_name") else ""
        print(f"\n[#{r['message_id']} | {r['date'][:16].replace('T', ' ')}{c_label}] {r['sender']} (Thread: {r['thread_id']}):")
        print(f"   {r['text']}")


def print_search_threads_fts(query: str, rows: List[Dict[str, Any]]):
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


def print_thread(t: Dict[str, Any]):
    print("\n" + "=" * 70)
    c_label = f" [Chat: {t.get('chat_name', t.get('chat_id'))}]" if t.get("chat_name") else ""
    print(f"📜 CONVERSATION THREAD: {t['thread_id']}{c_label}")
    print(f"Timeframe:    {t['start_date'][:16].replace('T', ' ')} to {t['end_date'][:16].replace('T', ' ')}")
    print(f"Messages:     {t['message_count']}")
    print(f"Participants: {t['participants']} (Initiator: {t['initiator']})")
    print("=" * 70)
    print(t["dialogue_text"])
    if t.get("message_count", 0) <= 1:
        print("\n⚠️  BOUNDARY / SINGLE-MESSAGE SAFEGUARD:")
        print("   This thread contains only 1 message. The N-5...N+5 rule requires checking")
        print("   surrounding chronological messages before drawing any conclusions.")
        anc = t.get("anchor_message_id")
        tid_suffix = t['thread_id'].split('_')[-1]
        sugg_id = anc or (tid_suffix[1:] if tid_suffix.startswith(('s', 't')) and tid_suffix[1:].isdigit() else None)
        if sugg_id:
            print(f"   Audit command: python3 project/scripts/query_chat.py --around {sugg_id} -n 5")
    print("=" * 70)


def print_chronological_around(c: Dict[str, Any]):
    print("\n" + "=" * 70)
    c_label = f" [Chat: {c.get('chat_name', c.get('chat_id'))}]" if c.get("chat_name") else ""
    print(f"⏱️  CHRONOLOGICAL AUDIT WINDOW: Message #{c['target_id']}{c_label} (±{c['window']} msgs)")
    print("=" * 70)
    for m in c["messages"]:
        is_target = m.get("is_target", False)
        prefix = f"[Reply to #{m['reply_to_id']}] " if m.get("reply_to_id") else ""
        thread_tag = f" (Thread: {m['thread_id']})" if m.get("thread_id") else ""
        dt_str = m['date'][:16].replace('T', ' ')
        if is_target:
            print("-" * 70)
            print(f"👉 [#{m['id']} | {dt_str}{thread_tag}] {m['sender']}: {prefix}{m['text']}  [AUDITED TARGET]")
            print("-" * 70)
        else:
            print(f"   [#{m['id']} | {dt_str}{thread_tag}] {m['sender']}: {prefix}{m['text']}")
    print("=" * 70)


def print_thread_slice(s: Dict[str, Any]):
    print("\n" + "=" * 70)
    c_label = f" [Chat: {s.get('chat_name', s.get('chat_id'))}]" if s.get("chat_name") else ""
    print(f"🔎 THREAD SLICE (Target #{s['target_message_id']} in {s['thread_id']}){c_label}")
    print(f"Participants: {s['participants']}")
    print("=" * 70)
    for m in s["messages"]:
        marker = "==> " if m["is_target"] else "    "
        prefix = f"[Reply #{m['reply_to_id']}] " if m["reply_to_id"] else ""
        print(f"{marker}[#{m['id']} | {m['date'][:16].replace('T', ' ')}] {m['sender']}: {prefix}{m['text']}")
    print("=" * 70)


def print_quote_chain(c: Dict[str, Any]):
    print("\n" + "=" * 70)
    c_label = f" [Chat: {c.get('chat_name', c.get('chat_id'))}]" if c.get("chat_name") else ""
    print(f"🔗 CAUSAL QUOTE CHAIN FOR MESSAGE #{c['target_message']['id']}{c_label}")
    print("=" * 70)

    if c["ancestors"]:
        print("⬆️  UPSTREAM CONTEXT (What triggered this):")
        for a in c["ancestors"]:
            print(f"   [#{a['id']} | {a['date'][:16].replace('T', ' ')}] {a['sender']}: {a['text']}")
        print("   " + "-" * 50)

    t = c["target_message"]
    print(f"🎯 TARGET MESSAGE [#{t['id']} | {t['date'][:16].replace('T', ' ')}] {t['sender']}:")
    print(f"   {t['text']}")

    if c["replies"]:
        print("   " + "-" * 50)
        print("⬇️  DOWNSTREAM REACTIONS (Direct answers to target):")
        for r in c["replies"]:
            print(f"   [#{r['id']} | {r['date'][:16].replace('T', ' ')}] {r['sender']}: {r['text']}")
    print("=" * 70)


def print_semantic_results(concept: str, results: List[Dict[str, Any]]):
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



# ==============================================================================
# ENTITY DISAMBIGUATION & DESCRIPTOR REGISTRY
# ==============================================================================

def ensure_entities_tables(conn: sqlite3.Connection):
    """Ensure chat_entities and chat_descriptors tables exist in the database."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_entities (
        entity_id TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        name_or_alias TEXT NOT NULL,
        verified_role TEXT,
        associated_descriptors TEXT,
        is_ex_partner INTEGER DEFAULT 0,
        is_romantic INTEGER DEFAULT 0,
        confidence TEXT DEFAULT 'unverified',
        first_msg_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, entity_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_chat ON chat_entities(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON chat_entities(chat_id, name_or_alias);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_descriptors (
        chat_id TEXT NOT NULL,
        descriptor TEXT NOT NULL,
        cardinality TEXT NOT NULL,
        estimated_count INTEGER DEFAULT 1,
        mapped_entity_ids TEXT,
        evidence_msg_ids TEXT,
        needs_recheck INTEGER DEFAULT 0,
        audited_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, descriptor)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_desc_chat ON chat_descriptors(chat_id);")
    conn.commit()


def get_chat_entities(db_path: str, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve registered third-party entities scoped to chat."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    sql = """
    SELECT e.entity_id, e.chat_id, coalesce(c.chat_name, e.chat_id), e.name_or_alias,
           e.verified_role, e.associated_descriptors, e.is_ex_partner, e.is_romantic,
           e.confidence, e.first_msg_id, e.notes, e.created_at, e.updated_at
    FROM chat_entities e
    LEFT JOIN chats c ON e.chat_id = c.chat_id
    """
    params = []
    if chat_id:
        sql += " WHERE e.chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY e.name_or_alias ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "entity_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "name_or_alias": r[3],
            "verified_role": r[4] or "",
            "associated_descriptors": r[5] or "",
            "is_ex_partner": bool(r[6]),
            "is_romantic": bool(r[7]),
            "confidence": r[8] or "verified",
            "first_msg_id": r[9],
            "notes": r[10] or "",
            "created_at": r[11],
            "updated_at": r[12]
        }
        for r in rows
    ]


def print_chat_entities(entities: List[Dict[str, Any]], chat_name: Optional[str] = None):
    print("\n" + "=" * 80)
    c_label = f" [Chat: {chat_name}]" if chat_name else ""
    print(f"👥 REGISTERED THIRD-PARTY ENTITIES (CHARACTERS & SUITORS){c_label}")
    print("=" * 80)
    if not entities:
        print("No third-party entities currently registered for this chat.")
        print("Use --register-entity '<name>' --role '<role>' --desc '<descriptors>' to register.")
        print("=" * 80)
        return

    print(f"{'Name / Alias':<18} {'Role':<22} {'Ex?':<5} {'Rom?':<5} {'Descriptors / Notes':<28}")
    print("-" * 80)
    for e in entities:
        ex_str = "YES" if e["is_ex_partner"] else "no"
        rom_str = "YES" if e["is_romantic"] else "no"
        role_str = e["verified_role"][:20]
        desc_notes = e["associated_descriptors"]
        if e["notes"]:
            desc_notes = f"{desc_notes} ({e['notes']})" if desc_notes else e["notes"]
        desc_notes = desc_notes[:27]
        print(f"{e['name_or_alias']:<18} {role_str:<22} {ex_str:<5} {rom_str:<5} {desc_notes:<28}")
    print("=" * 80)


def register_entity(
    db_path: str,
    chat_id: str,
    name_or_alias: str,
    verified_role: Optional[str] = None,
    associated_descriptors: Optional[str] = None,
    is_ex_partner: bool = False,
    is_romantic: bool = False,
    confidence: str = "verified",
    first_msg_id: Optional[int] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Register or update a third-party entity in the database."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    entity_id = re.sub(r'[^a-z0-9_]+', '_', name_or_alias.strip().lower()).strip('_')
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    cur.execute("""
    INSERT INTO chat_entities
    (entity_id, chat_id, name_or_alias, verified_role, associated_descriptors,
     is_ex_partner, is_romantic, confidence, first_msg_id, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, entity_id) DO UPDATE SET
        name_or_alias = excluded.name_or_alias,
        verified_role = coalesce(excluded.verified_role, chat_entities.verified_role),
        associated_descriptors = coalesce(excluded.associated_descriptors, chat_entities.associated_descriptors),
        is_ex_partner = excluded.is_ex_partner,
        is_romantic = excluded.is_romantic,
        confidence = excluded.confidence,
        first_msg_id = coalesce(excluded.first_msg_id, chat_entities.first_msg_id),
        notes = coalesce(excluded.notes, chat_entities.notes),
        updated_at = excluded.updated_at;
    """, (
        entity_id, chat_id, name_or_alias.strip(), verified_role,
        associated_descriptors, 1 if is_ex_partner else 0, 1 if is_romantic else 0,
        confidence, first_msg_id, notes, now_iso, now_iso
    ))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "entity_id": entity_id,
        "chat_id": chat_id,
        "name_or_alias": name_or_alias.strip(),
        "verified_role": verified_role,
        "associated_descriptors": associated_descriptors,
        "is_ex_partner": is_ex_partner,
        "is_romantic": is_romantic,
        "confidence": confidence,
        "first_msg_id": first_msg_id,
        "notes": notes
    }


def get_chat_descriptors(db_path: str, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve audited role/geographic descriptors and their cardinality."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    sql = """
    SELECT d.chat_id, coalesce(c.chat_name, d.chat_id), d.descriptor, d.cardinality,
           d.estimated_count, d.mapped_entity_ids, d.evidence_msg_ids, d.needs_recheck, d.audited_at
    FROM chat_descriptors d
    LEFT JOIN chats c ON d.chat_id = c.chat_id
    """
    params = []
    if chat_id:
        sql += " WHERE d.chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY d.descriptor ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "chat_id": r[0],
            "chat_name": r[1],
            "descriptor": r[2],
            "cardinality": r[3],
            "estimated_count": r[4],
            "mapped_entity_ids": r[5] or "",
            "evidence_msg_ids": r[6] or "",
            "needs_recheck": bool(r[7]),
            "audited_at": r[8]
        }
        for r in rows
    ]


def print_chat_descriptors(descriptors: List[Dict[str, Any]], chat_name: Optional[str] = None):
    print("\n" + "=" * 85)
    c_label = f" [Chat: {chat_name}]" if chat_name else ""
    print(f"🏷️  AUDITED DESCRIPTORS & ROLE CARDINALITY (K=1 vs K>1){c_label}")
    print("=" * 85)
    if not descriptors:
        print("No descriptors currently audited for this chat.")
        print("Run --audit-descriptor '<descriptor>' to run a lazy cardinality scan.")
        print("=" * 85)
        return

    print(f"{'Descriptor':<20} {'Cardinality':<18} {'Count':<6} {'Needs Recheck?':<15} {'Mapped Entities':<20}")
    print("-" * 85)
    for d in descriptors:
        recheck_str = "⚠️ YES" if d["needs_recheck"] else "OK"
        print(f"{d['descriptor']:<20} {d['cardinality']:<18} {d['estimated_count']:<6} {recheck_str:<15} {d['mapped_entity_ids']:<20}")
    print("=" * 85)


def audit_descriptor(
    db_path: str,
    descriptor: str,
    chat_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run lazy cardinality audit on a descriptor (e.g. 'sister', 'US guy') for a given chat.
    Scans messages for mentions, checks pluralization/variations, correlates with registered entities,
    and classifies cardinality as SINGLETON_K1 vs POLYSEMOUS_K_GT_1.
    """
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    if not chat_id:
        cur.execute("SELECT chat_id FROM chats LIMIT 2;")
        c_rows = cur.fetchall()
        if len(c_rows) == 1:
            chat_id = c_rows[0][0]
        else:
            conn.close()
            raise ValueError("Multiple chats exist in database. Please specify chat via -C <chat_id>.")

    desc_clean = descriptor.strip().lower()
    tokens = [t for t in re.split(r'\W+', desc_clean) if t]

    matching_msgs = []
    try:
        fts_query = " OR ".join([f'"{tok}"' for tok in tokens if len(tok) > 2])
        if fts_query:
            cur.execute("""
            SELECT m.id, m.date, m.sender, m.text, m.thread_id
            FROM messages m
            JOIN messages_fts f ON m.id = f.rowid
            WHERE m.chat_id = ? AND messages_fts MATCH ?
            ORDER BY m.timestamp ASC;
            """, (chat_id, fts_query))
            matching_msgs = cur.fetchall()
    except Exception:
        matching_msgs = []

    if not matching_msgs:
        cur.execute("""
        SELECT m.id, m.date, m.sender, m.text, m.thread_id
        FROM messages m
        WHERE m.chat_id = ? AND lower(m.text) LIKE ?
        ORDER BY m.timestamp ASC;
        """, (chat_id, f"%{desc_clean}%"))
        matching_msgs = cur.fetchall()

    filtered_msgs = []
    plural_indicators = [
        "sisters", "brothers", "friends", "guys", "both", "all of them", "two", "three",
        "siostry", "bracia", "znajomi", "faceci", "obaj", "obydwaj", "dwaj", "dwie", "dwoje"
    ]
    plural_detected = False
    plural_evidence_ids = []

    cur.execute("SELECT entity_id, name_or_alias, associated_descriptors FROM chat_entities WHERE chat_id = ?;", (chat_id,))
    reg_entities = cur.fetchall()

    mapped_entities = set()
    for eid, ename, edesc in reg_entities:
        ename_lower = ename.lower()
        edesc_lower = (edesc or "").lower()
        if desc_clean in edesc_lower or ename_lower in desc_clean:
            mapped_entities.add(eid)

    # Identify base noun tokens and build targeted plural regex
    noun_tokens = [tok for tok in tokens if tok not in ("my", "the", "a", "an", "this", "that", "from", "in", "ten", "ta", "to", "mój", "moja", "moje")]
    plural_patterns = []
    for ntok in noun_tokens:
        # Possessive plural: "my sisters", "my brothers", "my guys", "my exes"
        plural_patterns.append(rf'\b(my|our|moja|moje|moi)\s+(?:\w+\s+)?{re.escape(ntok)}s\b')
        # Ordinal qualifiers: "my second sister", "my 4th sister", "druga siostra"
        plural_patterns.append(rf'\b(my|our|moja|moje|moi)\s+(?:second|third|fourth|fifth|other|another|\d+(?:st|nd|rd|th)?|drug(?:a|i)|trzeci(?:a)?)\s+{re.escape(ntok)}\b')
        # Direct numeral quantity: "two sisters", "three guys", "two exes", "dwie siostry"
        plural_patterns.append(rf'\b(two|three|four|five|several|multiple|both|dwie|dwaj|trzy|cztery|obaj)\s+(?:\w+\s+)?{re.escape(ntok)}s?\b')

    plural_regex = re.compile("|".join(plural_patterns), re.IGNORECASE) if plural_patterns else None

    evidence_ids = []
    for mid, mdate, msender, mtext, mth_id in matching_msgs:
        text_lower = mtext.lower()
        if any(tok in text_lower for tok in tokens) or desc_clean in text_lower:
            filtered_msgs.append((mid, mdate, msender, mtext, mth_id))
            evidence_ids.append(mid)

            if plural_regex and plural_regex.search(text_lower):
                plural_detected = True
                plural_evidence_ids.append(mid)

            for eid, ename, _ in reg_entities:
                if re.search(r'\b' + re.escape(ename.lower()) + r'\b', text_lower):
                    mapped_entities.add(eid)

    if len(mapped_entities) >= 2 or plural_detected:
        cardinality = "POLYSEMOUS_K_GT_1"
        est_count = max(2, len(mapped_entities))
    elif len(filtered_msgs) == 0:
        cardinality = "UNRESOLVED"
        est_count = 0
    else:
        cardinality = "SINGLETON_K1"
        est_count = 1

    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()
    ev_ids_str = ",".join(str(x) for x in evidence_ids[:20])
    mapped_str = ",".join(sorted(mapped_entities))

    cur.execute("""
    INSERT INTO chat_descriptors
    (chat_id, descriptor, cardinality, estimated_count, mapped_entity_ids, evidence_msg_ids, needs_recheck, audited_at)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
    ON CONFLICT(chat_id, descriptor) DO UPDATE SET
        cardinality = excluded.cardinality,
        estimated_count = excluded.estimated_count,
        mapped_entity_ids = excluded.mapped_entity_ids,
        evidence_msg_ids = excluded.evidence_msg_ids,
        needs_recheck = 0,
        audited_at = excluded.audited_at;
    """, (chat_id, desc_clean, cardinality, est_count, mapped_str, ev_ids_str, now_iso))
    conn.commit()
    conn.close()

    return {
        "chat_id": chat_id,
        "descriptor": desc_clean,
        "cardinality": cardinality,
        "estimated_count": est_count,
        "plural_detected": plural_detected,
        "plural_evidence_msg_ids": plural_evidence_ids[:5],
        "mapped_entities": list(sorted(mapped_entities)),
        "total_mentions": len(filtered_msgs),
        "evidence_msg_ids": evidence_ids[:10],
        "sample_mentions": [
            {"id": m[0], "date": m[1][:10], "sender": m[2], "text": m[3][:120]}
            for m in filtered_msgs[:5]
        ]
    }


def print_descriptor_audit(audit: Dict[str, Any]):
    print("\n" + "=" * 80)
    print(f"🔬 LAZY DESCRIPTOR CARDINALITY AUDIT: '{audit['descriptor']}'")
    print(f"   Chat ID:          {audit['chat_id']}")
    print(f"   Total Mentions:   {audit['total_mentions']}")
    print(f"   Result:           {audit['cardinality']} (Estimated Count: {audit['estimated_count']})")
    print("=" * 80)

    if audit["mapped_entities"]:
        print(f"🔗 Mapped Known Entities: {', '.join(audit['mapped_entities'])}")
    if audit["plural_detected"]:
        print(f"⚠️  Plural language detected in messages: {audit['plural_evidence_msg_ids']}")

    print("\n📌 ACTIONABLE PROFILER DIRECTIVE:")
    if audit["cardinality"] == "SINGLETON_K1":
        print("   🟢 SINGLETON (K=1): Verified as a unique individual in this chat.")
        print("      Conversational inertia may link subsequent unanchored mentions to this entity.")
    elif audit["cardinality"] == "POLYSEMOUS_K_GT_1":
        print("   🔴 POLYSEMOUS (K>1): MULTIPLE INDIVIDUALS SHARE THIS ROLE OR DESCRIPTOR.")
        print("      CRITICAL INVARIANT: The agent is STRICTLY FORBIDDEN from attributing messages")
        print("      or traits using bare pronouns ('he', 'she') without a proper name anchor in N-5...N.")
    else:
        print("   ⚪ UNRESOLVED: Insufficient evidence in this chat stream to determine cardinality.")

    if audit["sample_mentions"]:
        print("\n📝 Sample Mentions in Chat:")
        for sm in audit["sample_mentions"]:
            print(f"   [#{sm['id']} | {sm['date']}] {sm['sender']}: {sm['text']}")
    print("=" * 80)


def run_watchdog_check(
    db_path: str,
    thread_id: str,
    chat_id: Optional[str] = None,
    explicit_known_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute adversarial System-1 entity watchdog check on a thread."""
    if verify_unregistered_entities_decider is None:
        raise ImportError("verify_unregistered_entities_decider could not be imported from triage_threads.py")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT thread_id, chat_id, dialogue_text, participants FROM threads WHERE thread_id = ?;", (thread_id,))
    t_row = cur.fetchone()
    if not t_row:
        try:
            mid = int(thread_id)
            cur.execute("""
            SELECT t.thread_id, t.chat_id, t.dialogue_text, t.participants
            FROM threads t
            JOIN messages m ON t.thread_id = m.thread_id
            WHERE m.id = ?;
            """, (mid,))
            t_row = cur.fetchone()
        except ValueError:
            pass

    if not t_row:
        conn.close()
        raise ValueError(f"Thread or message '{thread_id}' not found.")

    actual_thread_id, actual_chat_id, dialogue_text, participants = t_row

    known_names = []
    if explicit_known_names:
        known_names.extend(explicit_known_names)
    else:
        ensure_entities_tables(conn)
        cur.execute("SELECT name_or_alias FROM chat_entities WHERE chat_id = ?;", (actual_chat_id,))
        for r in cur.fetchall():
            known_names.append(r[0])
        if participants:
            for p in participants.split(","):
                p_clean = p.strip()
                if p_clean and p_clean not in known_names:
                    known_names.append(p_clean)

    conn.close()

    # Locate config file
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "embeddings_config.json")
    if not os.path.exists(config_path):
        root_cfg = os.path.join(os.getcwd(), "config", "embeddings_config.json")
        if os.path.exists(root_cfg):
            config_path = root_cfg

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_key = cfg.get("openrouter_api_key", "").strip()
    model = cfg.get("triage_model", "openrouter/auto")

    has_unregistered, prob = verify_unregistered_entities_decider(
        dialogue_text=dialogue_text,
        known_names=known_names,
        model=model,
        api_key=api_key
    )

    return {
        "thread_id": actual_thread_id,
        "chat_id": actual_chat_id,
        "known_entities": known_names,
        "has_unregistered_third_party": has_unregistered,
        "probability": round(prob, 3),
        "model_used": model
    }


def print_watchdog_result(res: Dict[str, Any]):
    print("\n" + "=" * 80)
    print(f"🛡️  ADVERSARIAL SYSTEM-1 ENTITY WATCHDOG CHECK: Thread {res['thread_id']}")
    print(f"   Chat ID:          {res['chat_id']}")
    print(f"   Known Entities:   [{', '.join(res['known_entities'])}]")
    print(f"   Model Used:       {res['model_used']}")
    print("-" * 80)
    if res["has_unregistered_third_party"]:
        print(f"🚨 ALERT: UNREGISTERED THIRD-PARTY ENTITY DETECTED! (Confidence: {res['probability'] * 100:.1f}%)")
        print("   This thread appears to discuss or mention an external individual NOT present")
        print("   in your registered entities list.")
        print("   ACTION REQUIRED: Inspect thread (query_chat.py -t <id>), identify the new person,")
        print("   and register them via --register-entity.")
    else:
        print(f"✅ PASSED: No unregistered third-party entities detected. (Confidence: {(1.0 - res['probability']) * 100:.1f}%)")
        print("   All discussed individuals are accounted for in the registered entities set.")
    print("=" * 80)


# ==============================================================================
# MAIN CLI DISPATCHER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Query Telegram analytical SQLite and vector database (multi-chat support)."
    )
    parser.add_argument("--db", default="chat.db", help="Path to analytical SQLite database (default: chat.db)")
    parser.add_argument("--chat", "-C", type=str, help="Filter query to a specific chat by chat_id or chat_name")
    parser.add_argument("--list-chats", action="store_true", help="Display catalog of all indexed chats in the database")

    # Analytical flags
    parser.add_argument("--stats", action="store_true", help="Display Phase 1 quantitative metrics")
    parser.add_argument("--gaps", action="store_true", help="Display silence and reconnection initiative analysis")
    parser.add_argument("--min-hours", type=float, default=24.0, help="Minimum silence duration in hours (default: 24)")
    parser.add_argument("--timeline", action="store_true", help="Display monthly activity timeline")
    parser.add_argument("--burning-days", action="store_true", help="Display statistically anomalous high-activity days (burning days)")
    parser.add_argument("--intensive-threads", action="store_true", help="Display substantive dialogue threads ranked by volume (anti-noise)")
    parser.add_argument("--min-words", type=int, default=50, help="Minimum total words for --intensive-threads (default: 50)")
    parser.add_argument("--min-messages", type=int, default=6, help="Minimum messages for --intensive-threads (default: 6)")
    parser.add_argument("--triaged-threads", action="store_true", help="Display threads qualified by System-1 (Jev) triage for LLM profiling")
    parser.add_argument("--anomalies-only", action="store_true", help="Display only triaged threads with atypical behavior or interlocutor surprise")
    parser.add_argument("--emotional-peaks", action="store_true", help="Display only triaged threads with acute emotional peaks")
    parser.add_argument("--peak-type", type=str, help="Filter --emotional-peaks by type (profound_sadness, euphoric_joy, intense_rage)")
    parser.add_argument("--advice-seeking", action="store_true", help="Display only triaged threads with intimate confessions or advice seeking")
    parser.add_argument("--min-salience", type=float, default=0.0, help="Minimum salience score for --triaged-threads")
    parser.add_argument("--triage-category", type=str, help="Filter --triaged-threads by primary category")
    parser.add_argument("--triage-status", action="store_true", help="Display summary reduction report of System-1 triage")

    # Repeatable flags for multi-query execution
    parser.add_argument("--search", "-s", action="append", help="Search individual messages via FTS5 (can be repeated)")
    parser.add_argument("--search-threads", "-st", action="append", help="Search full dialogue threads via FTS5 (can be repeated)")
    parser.add_argument("--thread", "-t", action="append", help="Display full transcript of a thread by thread_id or message_id (can be repeated)")
    parser.add_argument("--from-msg", "-f", action="append", type=int, help="Display a slice of a thread starting from this message_id (can be repeated)")
    parser.add_argument("--window", "-w", type=int, default=0, help="Number of preceding messages to show before --from-msg (default: 0)")
    parser.add_argument("--chain", "-c", action="append", type=int, help="Display direct causal quote chain for a message_id (can be repeated)")
    parser.add_argument("--around", "-ar", "-ctx", action="append", type=int, help="Display chronological context surrounding a message across thread boundaries (can be repeated)")
    parser.add_argument("--semantic", "-sem", action="append", help="Search threads by psychological concept/meaning (can be repeated)")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Maximum number of results to display per query (default: 10)")

    # Agent productivity features
    parser.add_argument("--json", action="store_true", help="Output all results in structured JSON format")
    parser.add_argument("--batch-json", type=str, help="JSON string or file path containing multiple query directives")

    # Entity Disambiguation & Descriptor Registry flags
    parser.add_argument("--entities", action="store_true", help="Display catalog of registered third-party entities for the selected chat")
    parser.add_argument("--descriptors", action="store_true", help="Display catalog of audited role/geographic descriptors and their cardinality")
    parser.add_argument("--audit-descriptor", type=str, help="Run lazy cardinality audit on a descriptor (e.g. 'sister', 'US guy')")
    parser.add_argument("--register-entity", type=str, help="Register or update a third-party entity (provide name/alias)")
    parser.add_argument("--role", type=str, help="Verified role for --register-entity (e.g. 'ex-partner', 'platonic friend')")
    parser.add_argument("--desc", type=str, help="Associated descriptors/notes for --register-entity")
    parser.add_argument("--ex", action="store_true", help="Mark entity as ex-partner in --register-entity")
    parser.add_argument("--romantic", action="store_true", help="Mark entity as romantic prospect/partner in --register-entity")
    parser.add_argument("--non-romantic", action="store_true", help="Explicitly mark entity as non-romantic in --register-entity")
    parser.add_argument("--first-msg", type=int, help="First message ID introducing the entity")
    parser.add_argument("--confidence", type=str, default="verified", help="Confidence status for entity ('verified', 'unverified', 'hypothetical')")
    parser.add_argument("--watchdog-check", type=str, help="Run adversarial System-1 watchdog on a thread_id against registered entities")
    parser.add_argument("--known", action="append", help="Explicit list of known entities for --watchdog-check (can be repeated)")

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

    if not os.path.exists(args.db):
        print(f"[!] Database file '{args.db}' not found.")
        print("    Build it first using: python3 .agents/scripts/db_builder.py rozmowy/*.json -o chat.db")
        sys.exit(1)

    # Catalog command
    if args.list_chats or batch_config.get("list_chats", False):
        catalog = get_chats_catalog(args.db)
        if args.json:
            print(json.dumps({"chats": catalog}, indent=2, ensure_ascii=False))
        else:
            print_chats_catalog(catalog)
        return

    # Resolve chat filter
    filter_chat_arg = args.chat or batch_config.get("chat")
    resolved_chat_id, resolved_chat_name = resolve_chat(args.db, filter_chat_arg)

    # Auto-resolve chat if exactly one chat exists in DB
    if not resolved_chat_id:
        catalog = get_chats_catalog(args.db)
        if len(catalog) == 1:
            resolved_chat_id = catalog[0]["chat_id"]
            resolved_chat_name = catalog[0]["chat_name"]

    # 1. Register Entity
    if args.register_entity:
        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)
        is_ex = bool(args.ex)
        is_rom = True if args.romantic else (False if args.non_romantic else False)
        reg_res = register_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            name_or_alias=args.register_entity,
            verified_role=args.role,
            associated_descriptors=args.desc,
            is_ex_partner=is_ex,
            is_romantic=is_rom,
            confidence=args.confidence or "verified",
            first_msg_id=args.first_msg,
            notes=args.desc
        )
        if args.json:
            print(json.dumps(reg_res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[SUCCESS] Registered entity '{args.register_entity}' for chat {resolved_chat_id}.")
            entities = get_chat_entities(args.db, chat_id=resolved_chat_id)
            print_chat_entities(entities, chat_name=resolved_chat_name or resolved_chat_id)
        return

    # 2. Display Entities
    if args.entities or batch_config.get("entities", False):
        entities = get_chat_entities(args.db, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps({"entities": entities}, indent=2, ensure_ascii=False))
        else:
            print_chat_entities(entities, chat_name=resolved_chat_name)
        return

    # 3. Display Descriptors
    if args.descriptors or batch_config.get("descriptors", False):
        descriptors = get_chat_descriptors(args.db, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps({"descriptors": descriptors}, indent=2, ensure_ascii=False))
        else:
            print_chat_descriptors(descriptors, chat_name=resolved_chat_name)
        return

    # 4. Audit Descriptor (Lazy Cardinality Scan)
    if args.audit_descriptor:
        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)
        audit_res = audit_descriptor(args.db, args.audit_descriptor, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps(audit_res, indent=2, ensure_ascii=False))
        else:
            print_descriptor_audit(audit_res)
        return

    # 5. Adversarial System-1 Entity Watchdog Check
    if args.watchdog_check:
        watchdog_res = run_watchdog_check(
            db_path=args.db,
            thread_id=args.watchdog_check,
            chat_id=resolved_chat_id,
            explicit_known_names=args.known
        )
        if args.json:
            print(json.dumps(watchdog_res, indent=2, ensure_ascii=False))
        else:
            print_watchdog_result(watchdog_res)
        return

    # Merge CLI flags with batch config
    run_stats = args.stats or batch_config.get("stats", False)
    run_gaps = args.gaps or batch_config.get("gaps", False)
    run_timeline = args.timeline or batch_config.get("timeline", False)
    run_burning = args.burning_days or batch_config.get("burning_days", False)
    run_intensive = args.intensive_threads or batch_config.get("intensive_threads", False)
    run_anomalies_only = args.anomalies_only or batch_config.get("anomalies_only", False)
    run_peaks = args.emotional_peaks or batch_config.get("emotional_peaks", False)
    peak_type = args.peak_type or batch_config.get("peak_type")
    run_advice = args.advice_seeking or batch_config.get("advice_seeking", False)
    run_triaged = args.triaged_threads or run_anomalies_only or run_peaks or run_advice or batch_config.get("triaged_threads", False)
    run_triage_status = args.triage_status or batch_config.get("triage_status", False)
    min_salience = float(batch_config.get("min_salience", args.min_salience))
    triage_category = batch_config.get("triage_category", args.triage_category)
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
    around_msgs = [int(x) for x in extract_list(args.around, "around")]
    semantic_queries = [str(x) for x in extract_list(args.semantic, "semantic")]

    has_actions = any([
        run_stats, run_gaps, run_timeline, run_burning, run_intensive,
        run_triaged, run_triage_status,
        search_queries, search_thread_queries, thread_ids,
        from_msgs, chains, around_msgs, semantic_queries
    ])

    if not has_actions:
        parser.print_help()
        sys.exit(0)

    aggregated: Dict[str, Any] = {}
    if resolved_chat_id:
        aggregated["filter_chat"] = {"chat_id": resolved_chat_id, "chat_name": resolved_chat_name}

    # 1. Quantitative Stats
    if run_stats:
        stats_data = get_stats(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["stats"] = stats_data
        else:
            print_stats(stats_data)

    # 2. Silence Gaps
    if run_gaps:
        gaps_data = get_silence_gaps(args.db, min_hours=min_hours, chat_id=resolved_chat_id)
        if args.json:
            aggregated["silence_gaps"] = gaps_data
        else:
            print_silence_gaps(gaps_data)

    # 3. Monthly Timeline
    if run_timeline:
        timeline_data = get_timeline(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["timeline"] = timeline_data
        else:
            print_timeline(timeline_data)

    # 4. Burning Days
    if run_burning:
        burning_data = get_burning_days(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["burning_days"] = burning_data
        else:
            print_burning_days(burning_data)

    # 5. Intensive Substantive Threads
    if run_intensive:
        intensive_data = get_intensive_threads(
            args.db, min_words=min_words, min_messages=min_messages, limit=limit, chat_id=resolved_chat_id
        )
        if args.json:
            aggregated["intensive_threads"] = intensive_data
        else:
            print_intensive_threads(intensive_data)

    # 5b. System-1 Triaged Threads (Jev Qualified)
    if run_triage_status:
        from triage_threads import print_reduction_report
        t_conn = sqlite3.connect(args.db)
        print_reduction_report(t_conn)
        t_conn.close()

    if run_triaged:
        triaged_data = get_triaged_threads(
            args.db, limit=limit, chat_id=resolved_chat_id, min_salience=min_salience, category=triage_category,
            anomalies_only=run_anomalies_only,
            emotional_peaks_only=run_peaks,
            peak_type=peak_type,
            advice_seeking_only=run_advice
        )
        if args.json:
            aggregated["triaged_threads"] = triaged_data
        else:
            print_triaged_threads(triaged_data)

    # 6. Keyword Search (Individual Messages)
    if search_queries:
        search_results: Dict[str, Any] = {}
        for q in search_queries:
            msgs = get_search_messages(args.db, q, limit=limit, chat_id=resolved_chat_id)
            if args.json:
                search_results[q] = msgs
            else:
                print_search_messages(q, msgs)
        if args.json:
            aggregated["search_messages"] = search_results

    # 7. Keyword Search (Full Threads)
    if search_thread_queries:
        st_results: Dict[str, Any] = {}
        for q in search_thread_queries:
            threads = get_search_threads_fts(args.db, q, limit=limit, chat_id=resolved_chat_id)
            if args.json:
                st_results[q] = threads
            else:
                print_search_threads_fts(q, threads)
        if args.json:
            aggregated["search_threads"] = st_results

    # 8. Retrieve Full Threads
    if thread_ids:
        thread_results: Dict[str, Any] = {}
        for t_id in thread_ids:
            t_obj = get_thread(args.db, t_id, chat_id=resolved_chat_id)
            if t_obj:
                if args.json:
                    thread_results[t_id] = t_obj
                else:
                    print_thread(t_obj)
            else:
                if args.json:
                    thread_results[t_id] = None
                else:
                    print(f"\n[!] Thread/Message '{t_id}' not found.")
        if args.json:
            aggregated["threads"] = thread_results

    # 9. Retrieve Thread Slices
    if from_msgs:
        slice_results: Dict[str, Any] = {}
        for m_id in from_msgs:
            s_obj = get_thread_slice(args.db, m_id, limit=limit, window_before=window, chat_id=resolved_chat_id)
            if s_obj:
                if args.json:
                    slice_results[str(m_id)] = s_obj
                else:
                    print_thread_slice(s_obj)
            else:
                if args.json:
                    slice_results[str(m_id)] = None
                else:
                    print(f"\n[!] Message #{m_id} not found.")
        if args.json:
            aggregated["thread_slices"] = slice_results

    # 10. Trace Causal Quote Chains
    if chains:
        chain_results: Dict[str, Any] = {}
        for c_id in chains:
            chain_obj = get_quote_chain(args.db, c_id, chat_id=resolved_chat_id)
            if chain_obj:
                if args.json:
                    chain_results[str(c_id)] = chain_obj
                else:
                    print_quote_chain(chain_obj)
            else:
                if args.json:
                    chain_results[str(c_id)] = None
                else:
                    print(f"\n[!] Message #{c_id} not found.")
        if args.json:
            aggregated["quote_chains"] = chain_results

    # 11. Retrieve Chronological Window Across Thread Boundaries (N-5 ... N+5 Audit)
    if around_msgs:
        around_window = window if window > 0 else (limit if limit != 10 else 5)
        around_results: Dict[str, Any] = {}
        for a_id in around_msgs:
            a_obj = get_chronological_around(args.db, a_id, window=around_window, chat_id=resolved_chat_id)
            if a_obj:
                if args.json:
                    around_results[str(a_id)] = a_obj
                else:
                    print_chronological_around(a_obj)
            else:
                if args.json:
                    around_results[str(a_id)] = None
                else:
                    print(f"\n[!] Message #{a_id} not found.")
        if args.json:
            aggregated["chronological_around"] = around_results

    # 12. Batch Semantic Search
    if semantic_queries:
        sem_res = get_semantic_batch_results(args.db, semantic_queries, top_k=limit, chat_id=resolved_chat_id)
        if args.json:
            aggregated["semantic_search"] = sem_res
        else:
            for q, results in sem_res.items():
                print_semantic_results(q, results)

    # Output structured JSON if requested
    if args.json:
        print(json.dumps(aggregated, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
