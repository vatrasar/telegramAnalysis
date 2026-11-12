"""Silence gap and reconnection initiative analysis across duration intervals and cumulative milestones."""

import sqlite3
from typing import List, Dict, Any, Optional, Set

from .formatters import format_duration


DURATION_BRACKETS_DEF = [
    ("1-3 days (24h-72h)", 24.0, 72.0),
    ("3-7 days (3d-7d)", 72.0, 168.0),
    ("1-2 weeks (7d-14d)", 168.0, 336.0),
    ("2-4 weeks (14d-30d)", 336.0, 720.0),
    ("1-3 months (30d-90d)", 720.0, 2160.0),
    ("3+ months (>90d)", 2160.0, float("inf")),
]

CUMULATIVE_MILESTONES_DEF = [
    (">= 24 hours (1d)", 24.0),
    (">= 72 hours (3d)", 72.0),
    (">= 7 days (1w)", 168.0),
    (">= 14 days (2w)", 336.0),
    (">= 30 days (1m)", 720.0),
    (">= 90 days (3m)", 2160.0),
]


def _calc_initiative_summary(gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate counts and percentages of initiators for a given slice of gaps."""
    total = len(gaps)
    if total == 0:
        return []

    counts: Dict[str, int] = {}
    self_reconnects: Dict[str, int] = {}
    for g in gaps:
        init = g["initiator"]
        counts[init] = counts.get(init, 0) + 1
        if g.get("last_sender") == init:
            self_reconnects[init] = self_reconnects.get(init, 0) + 1

    result = []
    for sender, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        pct = round((cnt / total * 100), 1)
        self_cnt = self_reconnects.get(sender, 0)
        result.append({
            "sender": sender,
            "count": cnt,
            "percentage": pct,
            "self_reconnect_count": self_cnt,
            "self_reconnect_percentage": round((self_cnt / cnt * 100), 1) if cnt else 0.0,
        })
    return result


def _build_duration_brackets(gaps: List[Dict[str, Any]], min_hours: float) -> List[Dict[str, Any]]:
    """Group gaps into predefined duration intervals/brackets."""
    brackets = []
    max_duration_hours = max((g["duration_hours"] for g in gaps), default=0.0)

    for label, low, high in DURATION_BRACKETS_DEF:
        # Skip brackets that are strictly below min_hours
        if high <= min_hours:
            continue
        # Skip brackets that are strictly above the maximum duration in data if empty
        if low > max_duration_hours and low > min_hours:
            continue

        b_gaps = [g for g in gaps if low <= g["duration_hours"] < high]
        brackets.append({
            "bracket": label,
            "min_hours": low,
            "max_hours": high if high != float("inf") else None,
            "total_gaps": len(b_gaps),
            "initiatives": _calc_initiative_summary(b_gaps),
        })
    return brackets


def _build_cumulative_milestones(gaps: List[Dict[str, Any]], min_hours: float) -> List[Dict[str, Any]]:
    """Group gaps into cumulative thresholds (>= 1d, >= 3d, >= 7d, >= 14d, >= 30d, >= 90d)."""
    milestones = []
    for label, threshold in CUMULATIVE_MILESTONES_DEF:
        if threshold < min_hours:
            continue
        m_gaps = [g for g in gaps if g["duration_hours"] >= threshold]
        if not m_gaps and threshold > min_hours:
            continue
        milestones.append({
            "milestone": label,
            "threshold_hours": threshold,
            "threshold_days": round(threshold / 24.0, 1),
            "total_gaps": len(m_gaps),
            "initiatives": _calc_initiative_summary(m_gaps),
        })
    return milestones


def get_silence_gaps(db_path: str, min_hours: float = 24.0, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve silence gaps and tiered initiative ratios (overall, brackets, milestones, per-chat)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sql = """
    SELECT g.chat_id, coalesce(c.chat_name, g.chat_id) as chat_name,
           g.silence_start_date, g.silence_end_date, g.silence_duration_seconds,
           g.last_sender, g.initiator, g.after_thread_id, g.silence_duration_hours
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

    # Pre-fetch participants per chat to track all interlocutors
    chat_participants_map: Dict[str, Set[str]] = {}
    cur.execute("SELECT DISTINCT chat_id, sender FROM messages;")
    for cid, snd in cur.fetchall():
        chat_participants_map.setdefault(cid, set()).add(snd)

    gaps_list: List[Dict[str, Any]] = []
    chats_gaps_map: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        c_id = r[0]
        c_name = r[1]
        init = r[6]
        dur_hrs = r[8] if r[8] is not None else round(r[4] / 3600.0, 1)

        if c_id not in chats_gaps_map:
            chats_gaps_map[c_id] = {
                "chat_id": c_id,
                "chat_name": c_name,
                "total_gaps": 0,
                "initiators": {},
                "gaps": []
            }
        chats_gaps_map[c_id]["total_gaps"] += 1
        c_inits = chats_gaps_map[c_id]["initiators"]
        c_inits[init] = c_inits.get(init, 0) + 1

        gap_entry = {
            "chat_id": r[0],
            "chat_name": r[1],
            "start_date": r[2],
            "end_date": r[3],
            "duration_seconds": r[4],
            "duration_hours": dur_hrs,
            "duration_formatted": format_duration(r[4]),
            "last_sender": r[5],
            "initiator": r[6],
            "after_thread_id": r[7]
        }
        gaps_list.append(gap_entry)
        chats_gaps_map[c_id]["gaps"].append(gap_entry)

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
            "initiatives": chat_init_list,
            "duration_brackets": _build_duration_brackets(c_data["gaps"], min_hours),
            "cumulative_milestones": _build_cumulative_milestones(c_data["gaps"], min_hours),
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

    duration_brackets = _build_duration_brackets(gaps_list, min_hours)
    cumulative_milestones = _build_cumulative_milestones(gaps_list, min_hours)

    return {
        "filtered_chat_id": chat_id,
        "min_hours": min_hours,
        "min_days": round(min_hours / 24.0, 2),
        "total_gaps": total_gaps,
        "initiative_stats": init_stats,
        "duration_brackets": duration_brackets,
        "cumulative_milestones": cumulative_milestones,
        "chat_initiatives": chat_initiatives,
        "longest_gaps": gaps_list[:15]
    }


def _format_initiatives_line(initiatives: List[Dict[str, Any]]) -> str:
    """Format list of initiatives into a compact single-line string."""
    if not initiatives:
        return "None"
    return " | ".join(f"{item['sender']}: {item['count']} ({item['percentage']}%)" for item in initiatives)


def print_silence_gaps(data: Dict[str, Any]) -> None:
    """Print ASCII view of silence gaps, duration brackets, cumulative milestones, and top silences."""
    filter_label = f" [Chat: {data['filtered_chat_id']}]" if data.get("filtered_chat_id") else ""
    hours_label = f"{data['min_hours']}h" if data.get("min_hours") else "24h"
    days_label = f" ({data['min_days']}d)" if data.get("min_days") and data["min_days"] > 1.0 else ""

    print("\n" + "=" * 88)
    print(f"⏳ CONVERSATION GAPS & RECONNECTION INITIATIVE (>={hours_label}{days_label}){filter_label}")
    print("=" * 88)

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
        print(f"\nOverall Initiative Ratio (>={data['min_hours']}h, Total Silences: {data['total_gaps']}):")
        for s in data["initiative_stats"]:
            print(f"  - {s['sender']:<18}: {s['count']:>3} times ({s['percentage']:>5.1f}%)")

    # Duration intervals / brackets table
    brackets = data.get("duration_brackets", [])
    if brackets:
        print("\nInitiative Breakdown by Silence Duration Interval:")
        print(f"{'Interval / Bracket':<24} {'Total':<6} {'Initiative Breakdown (Who Broke Silence)'}")
        print("-" * 88)
        for b in brackets:
            b_label = b["bracket"]
            b_total = b["total_gaps"]
            init_str = _format_initiatives_line(b["initiatives"]) if b_total > 0 else "0 (no silences)"
            print(f"{b_label:<24} {b_total:<6} {init_str}")

    # Cumulative milestones table
    milestones = data.get("cumulative_milestones", [])
    if milestones and len(milestones) > 1:
        print("\nCumulative Initiative Milestones (Tracking Long Pauses):")
        print(f"{'Threshold':<24} {'Total':<6} {'Initiative Breakdown'}")
        print("-" * 88)
        for m in milestones:
            m_label = m["milestone"]
            m_total = m["total_gaps"]
            init_str = _format_initiatives_line(m["initiatives"])
            print(f"{m_label:<24} {m_total:<6} {init_str}")

    print(f"\nTop Longest Silences:")
    print(f"{'Chat':<12} {'Silence Period':<35} {'Duration':<11} {'Last Spoke':<11} {'Broke Silence':<13} {'Thread'}")
    print("-" * 88)
    for g in data["longest_gaps"]:
        c_label = g.get("chat_name", g.get("chat_id", ""))[:10]
        start_d = g["start_date"][:16].replace("T", " ")
        end_d = g["end_date"][:16].replace("T", " ")
        dur_str = g["duration_formatted"]
        last_s = g["last_sender"][:10]
        init_s = g["initiator"][:10]
        th_id = g.get("after_thread_id") or ""
        print(f"{c_label:<12} {start_d} -> {end_d:<16} {dur_str:<11} {last_s:<11} {init_s:<13} {th_id}")
