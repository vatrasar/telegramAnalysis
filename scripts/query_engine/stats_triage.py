"""Burning days statistical outlier detection, intensive threads, and System-1 triage retrieval."""

import math
import sqlite3
from typing import List, Dict, Any, Optional

from .formatters import format_duration


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


def print_burning_days(data: Dict[str, Any]) -> None:
    """Print ASCII table of burning days."""
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


def print_intensive_threads(threads: List[Dict[str, Any]]) -> None:
    """Print ASCII list of substantive threads."""
    print("\n" + "=" * 80)
    print("💬 SUBSTANTIVE DIALOGUE THREADS (RANKED BY CONVERSATIONAL VOLUME)")
    print("=" * 80)
    if not threads:
        print("No intensive dialogue threads found meeting criteria.")
        return

    print(f"{'Thread ID':<22} {'Chat':<14} {'Date':<17} {'Msgs':<6} {'Words':<8} {'Participants'}")
    print("-" * 80)
    for t in threads:
        c_label = t.get("chat_name", t.get("chat_id", ""))[:12]
        print(f"{t['thread_id']:<22} {c_label:<14} {t['start_date']:<17} {t['message_count']:<6} {t['total_words']:<8,} {t['participants']}")


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


def print_triaged_threads(threads: List[Dict[str, Any]]) -> None:
    """Print ASCII list of high-salience triaged threads."""
    print("\n" + "=" * 95)
    print("🧠 TRIAGED HIGH-SALIENCE DIALOGUE THREADS (SYSTEM-1 JEV QUALIFIED)")
    print("=" * 95)
    if not threads:
        print("No triaged threads found meeting criteria (or run 'python3 project/scripts/triage_threads.py' first).")
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
