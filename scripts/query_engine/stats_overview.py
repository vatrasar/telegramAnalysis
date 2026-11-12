"""Quantitative overview metrics, silence gap analysis, and monthly timeline."""

import sqlite3
from typing import List, Dict, Any, Optional, Set

from .formatters import format_duration
from .silence_gaps import get_silence_gaps, print_silence_gaps


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


def print_stats(stats: Dict[str, Any]) -> None:
    """Print ASCII table of Phase 1 quantitative metrics."""
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


def print_timeline(data: Dict[str, Any]) -> None:
    """Print ASCII monthly timeline distribution."""
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
