#!/usr/bin/env python3
"""
Thread Forensic Audit Checklist & Gatekeeper.
Manages, audits, and enforces turn-by-turn psychological analysis of all
substantive, high-salience, and emotionally intense conversation threads in SQLite.

Enforces Track B of the analysis architecture:
- Track A (Radar 4 / Entity Discovery): Sequential System-1 Watchdog Cursor (--watchdog-scan)
- Track B (Radars 1-3 + Intensive Threads): turn-by-turn psychological audit tracked in SQLite
  (thread_audit_checklist) with a hard-stop blocking gate before report assembly.
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

# Script location and path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_ROOT = os.path.dirname(PROJECT_DIR)
DEFAULT_DB_PATH = os.path.join(WORKSPACE_ROOT, "chat.db")

VALID_STATUSES = {"pending", "completed", "skipped", "not_applicable"}
RESOLVED_STATUSES = {"completed", "skipped", "not_applicable"}


def ensure_thread_checklist_table(conn: sqlite3.Connection):
    """Create thread_audit_checklist and metadata tables and indexes if they do not exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_audit_checklist (
        chat_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        radar_sources TEXT NOT NULL,
        salience_score REAL,
        primary_category TEXT,
        start_date TEXT,
        message_count INTEGER,
        total_words INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        findings_summary TEXT,
        key_quotes TEXT,
        thematic_tags TEXT,
        notes TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, thread_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thread_checklist_status ON thread_audit_checklist(chat_id, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thread_checklist_radar ON thread_audit_checklist(chat_id, radar_sources);")
    conn.commit()


def is_thread_checklist_waived(conn: sqlite3.Connection, chat_id: str) -> Tuple[bool, Optional[str]]:
    """Check if thread audit checklist is currently flagged as waived/exempt in metadata."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"thread_checklist_mode_{chat_id}",))
        row = cur.fetchone()
        if row and row[0] == "waived":
            cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"thread_checklist_waiver_reason_{chat_id}",))
            r_row = cur.fetchone()
            reason = r_row[0] if r_row else "Ad-hoc task / partial inquiry"
            return True, reason
    except Exception:
        pass
    return False, None


def waive_thread_checklist(conn: sqlite3.Connection, chat_id: str, reason: str = "Ad-hoc task / partial inquiry") -> int:
    """Waive thread checklist by marking all pending threads as not_applicable and setting metadata flag."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("""
    UPDATE thread_audit_checklist
    SET status = 'not_applicable',
        notes = coalesce(notes || ' | ', '') || 'Waived: ' || ?,
        updated_at = ?
    WHERE chat_id = ? AND status = 'pending';
    """, (reason, now_iso, chat_id))
    waived_count = cur.rowcount
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, 'waived');", (f"thread_checklist_mode_{chat_id}",))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", (f"thread_checklist_waiver_reason_{chat_id}", reason))
    conn.commit()
    return waived_count


def enable_thread_checklist(conn: sqlite3.Connection, chat_id: str) -> int:
    """Re-enable thread checklist after waiver by changing not_applicable items back to pending."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("""
    UPDATE thread_audit_checklist
    SET status = 'pending',
        updated_at = ?
    WHERE chat_id = ? AND status = 'not_applicable';
    """, (now_iso, chat_id))
    re_enabled = cur.rowcount
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, 'active');", (f"thread_checklist_mode_{chat_id}",))
    cur.execute("DELETE FROM metadata WHERE key = ?;", (f"thread_checklist_waiver_reason_{chat_id}",))
    conn.commit()
    return re_enabled


def init_thread_checklist(
    conn: sqlite3.Connection,
    chat_id: str,
    reset: bool = False,
    min_salience_other: float = 2.0,
    min_words_intensive: int = 60,
    min_messages_intensive: int = 8,
    limit_intensive: int = 50
) -> Dict[str, Any]:
    """
    Initialize thread audit checklist for a given chat.
    Pulls:
    - Radar 1 (Anomalies & Shocks)
    - Radar 2 (Acute Emotional Peaks: grief, euphoria, rage)
    - Radar 3 (Intimate Confessions & Advice Seeking)
    - Other High-Salience Triaged Threads (salience >= min_salience_other)
    - Top Intensive Discussions (word_count >= 60, msgs >= 8)
    
    EXCLUDES: Pure Radar 4 (third-party names only) without anomalies, peaks, advice, or high intensity.
    """
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    if reset:
        cur.execute("DELETE FROM thread_audit_checklist WHERE chat_id = ?;", (chat_id,))
        cur.execute("DELETE FROM metadata WHERE key IN (?, ?);", 
                    (f"thread_checklist_mode_{chat_id}", f"thread_checklist_waiver_reason_{chat_id}"))
        conn.commit()

    # Check if thread_triage table exists
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0

    thread_candidates: Dict[str, Dict[str, Any]] = {}

    if has_triage:
        cur.execute("PRAGMA table_info(thread_triage);")
        tcols = {col[1] for col in cur.fetchall()}
        has_atypical = "is_atypical" in tcols
        has_peak = "emotional_peak" in tcols
        has_advice = "is_advice_seeking" in tcols

        atyp_sel = "tr.is_atypical" if has_atypical else "0"
        surp_sel = "tr.interlocutor_surprised" if has_atypical else "0"
        peak_sel = "tr.emotional_peak" if has_peak else "'none'"
        adv_sel = "tr.is_advice_seeking" if has_advice else "0"

        sql_triage = f"""
        SELECT tr.thread_id, tr.salience_score, tr.primary_category,
               {atyp_sel}, {surp_sel}, {peak_sel}, {adv_sel},
               t.start_date, t.message_count, coalesce(sum(m.word_count), 0) as total_words
        FROM thread_triage tr
        JOIN threads t ON tr.thread_id = t.thread_id
        LEFT JOIN messages m ON t.thread_id = m.thread_id
        WHERE tr.chat_id = ?
        GROUP BY tr.thread_id;
        """
        cur.execute(sql_triage, (chat_id,))
        for r in cur.fetchall():
            tid = r[0]
            score = float(r[1] or 0.0)
            cat = r[2] or "general"
            is_atyp = bool(r[3])
            is_surp = bool(r[4])
            peak = r[5] or "none"
            is_adv = bool(r[6])
            start_date = r[7][:16].replace("T", " ") if r[7] else ""
            msg_count = r[8] or 0
            word_count = r[9] or 0

            radars: List[str] = []
            if is_atyp or is_surp:
                radars.append("radar_1_anomalies")
            if peak in ("profound_sadness", "euphoric_joy", "intense_rage"):
                radars.append(f"radar_2_peak:{peak}")
            if is_adv:
                radars.append("radar_3_advice_seeking")

            # Check if it qualifies under other high-salience (score >= 2.0 or sensitive category)
            if not radars and score >= min_salience_other:
                radars.append("other_salient")

            if radars:
                thread_candidates[tid] = {
                    "thread_id": tid,
                    "chat_id": chat_id,
                    "radar_sources": ",".join(radars),
                    "salience_score": score,
                    "primary_category": cat,
                    "start_date": start_date,
                    "message_count": msg_count,
                    "total_words": word_count
                }

    # Add Intensive Discussions
    sql_intensive = """
    SELECT t.thread_id, t.start_date, t.message_count, sum(m.word_count) as total_words
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id
    WHERE t.chat_id = ?
    GROUP BY t.thread_id
    HAVING t.message_count >= ? AND total_words >= ?
    ORDER BY total_words DESC
    LIMIT ?;
    """
    cur.execute(sql_intensive, (chat_id, min_messages_intensive, min_words_intensive, limit_intensive))
    for r in cur.fetchall():
        tid = r[0]
        start_date = r[1][:16].replace("T", " ") if r[1] else ""
        msg_count = r[2] or 0
        word_count = r[3] or 0

        if tid in thread_candidates:
            existing_radars = thread_candidates[tid]["radar_sources"].split(",")
            if "intensive_discussion" not in existing_radars:
                existing_radars.append("intensive_discussion")
                thread_candidates[tid]["radar_sources"] = ",".join(existing_radars)
        else:
            thread_candidates[tid] = {
                "thread_id": tid,
                "chat_id": chat_id,
                "radar_sources": "intensive_discussion",
                "salience_score": 1.5,
                "primary_category": "intensive_discussion",
                "start_date": start_date,
                "message_count": msg_count,
                "total_words": word_count
            }

    # Insert into thread_audit_checklist if not existing
    now_iso = datetime.now(timezone.utc).isoformat()
    inserted_count = 0
    updated_sources = 0

    for tid, data in thread_candidates.items():
        cur.execute("SELECT radar_sources, status FROM thread_audit_checklist WHERE chat_id = ? AND thread_id = ?;", (chat_id, tid))
        row = cur.fetchone()
        if not row:
            cur.execute("""
            INSERT INTO thread_audit_checklist (
                chat_id, thread_id, radar_sources, salience_score, primary_category,
                start_date, message_count, total_words, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?);
            """, (
                chat_id, tid, data["radar_sources"], data["salience_score"], data["primary_category"],
                data["start_date"], data["message_count"], data["total_words"], now_iso
            ))
            inserted_count += 1
        else:
            # Merge radar sources if new ones appeared
            existing_srcs = set(row[0].split(","))
            new_srcs = set(data["radar_sources"].split(","))
            combined = existing_srcs.union(new_srcs)
            if combined != existing_srcs:
                cur.execute("""
                UPDATE thread_audit_checklist
                SET radar_sources = ?, updated_at = ?
                WHERE chat_id = ? AND thread_id = ?;
                """, (",".join(sorted(combined)), now_iso, chat_id, tid))
                updated_sources += 1

    conn.commit()

    cur.execute("SELECT count(*) FROM thread_audit_checklist WHERE chat_id = ?;", (chat_id,))
    total_in_db = cur.fetchone()[0]

    return {
        "chat_id": chat_id,
        "total_threads_enrolled": total_in_db,
        "newly_inserted": inserted_count,
        "updated_sources": updated_sources
    }


def get_thread_checklist_stats(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Retrieve detailed stats and breakdown of the thread audit checklist."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    is_waived, waiver_reason = is_thread_checklist_waived(conn, chat_id)

    cur.execute("""
    SELECT count(*),
           sum(case when status = 'completed' then 1 else 0 end),
           sum(case when status = 'pending' then 1 else 0 end),
           sum(case when status = 'skipped' then 1 else 0 end),
           sum(case when status = 'not_applicable' then 1 else 0 end)
    FROM thread_audit_checklist
    WHERE chat_id = ?;
    """, (chat_id,))
    row = cur.fetchone()
    total = row[0] or 0
    completed = row[1] or 0
    pending = row[2] or 0
    skipped = row[3] or 0
    not_applicable = row[4] or 0

    resolved = completed + skipped + not_applicable
    progress_pct = (resolved / total * 100.0) if total > 0 else 0.0

    # Radar breakdown
    cur.execute("""
    SELECT radar_sources, status, count(*)
    FROM thread_audit_checklist
    WHERE chat_id = ?
    GROUP BY radar_sources, status;
    """, (chat_id,))
    radar_counts: Dict[str, Dict[str, int]] = {}
    for r in cur.fetchall():
        r_sources = r[0]
        r_status = r[1]
        r_count = r[2]
        for src in r_sources.split(","):
            prefix = src.split(":")[0]
            if prefix not in radar_counts:
                radar_counts[prefix] = {"total": 0, "completed": 0, "pending": 0, "skipped": 0}
            radar_counts[prefix]["total"] += r_count
            if r_status in radar_counts[prefix]:
                radar_counts[prefix][r_status] += r_count

    # Next pending thread
    cur.execute("""
    SELECT thread_id, radar_sources, salience_score, primary_category, start_date, message_count, total_words
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'pending'
    ORDER BY salience_score DESC, total_words DESC
    LIMIT 3;
    """, (chat_id,))
    next_pending = []
    for r in cur.fetchall():
        next_pending.append({
            "thread_id": r[0],
            "radar_sources": r[1],
            "salience_score": r[2],
            "primary_category": r[3],
            "start_date": r[4],
            "message_count": r[5],
            "total_words": r[6]
        })

    return {
        "chat_id": chat_id,
        "is_waived": is_waived,
        "waiver_reason": waiver_reason,
        "total": total,
        "completed": completed,
        "pending": pending,
        "skipped": skipped,
        "not_applicable": not_applicable,
        "resolved": resolved,
        "progress_pct": progress_pct,
        "radars": radar_counts,
        "next_pending": next_pending
    }


def print_thread_status(stats: Dict[str, Any]):
    """Print visually polished dashboard of thread checklist status."""
    chat_id = stats["chat_id"]
    total = stats["total"]
    completed = stats["completed"]
    pending = stats["pending"]
    skipped = stats["skipped"]
    na = stats["not_applicable"]
    pct = stats["progress_pct"]

    print("\n" + "=" * 80)
    print(f"🎯 THREAD FORENSIC AUDIT CHECKLIST (TRACK B - SUBSTANTIVE & INTENSIVE THREADS)")
    print(f"   Chat Scope: `{chat_id}`")
    print("=" * 80)

    if stats["is_waived"]:
        print(f"⚠️  STATUS: WAIVED / DISABLED (Safety Exemption Active)")
        print(f"   Reason: {stats['waiver_reason']}")
        print(f"   Audit gate is non-blocking. Re-enable with: python3 project/scripts/thread_checklist.py -C {chat_id} --enable")
        print("=" * 80)
        return

    # Progress bar
    bar_width = 36
    filled = int(round(bar_width * (pct / 100.0)))
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"Progress: [{bar}] {pct:5.1f}% ({stats['resolved']}/{total} resolved)")
    print(f"  • ✅ Completed Audits:   {completed:3d} threads")
    print(f"  • ⏳ Pending Audit:       {pending:3d} threads")
    print(f"  • ⏭️ Skipped / Bypassed:  {skipped:3d} threads")
    if na > 0:
        print(f"  • ⚪ Not Applicable:      {na:3d} threads")

    print("-" * 80)
    print("📡 BREAKDOWN BY DIAGNOSTIC RADAR / CATEGORY:")
    radar_labels = {
        "radar_1_anomalies": "⚡ Radar 1: Behavioral Anomalies & Interlocutor Shock",
        "radar_2_peak": "🎭 Radar 2: Acute Emotional Peaks (Grief, Euphoria, Rage)",
        "radar_3_advice_seeking": "💡 Radar 3: Confessions & Intimate Advice Dilemmas",
        "other_salient": "🌟 Other High-Salience Triaged Threads (Score >= 2.0)",
        "intensive_discussion": "📚 Top Substantive & Intensive Discussions"
    }
    for r_key, r_info in sorted(stats["radars"].items()):
        label = radar_labels.get(r_key, f"📡 {r_key}")
        r_tot = r_info["total"]
        r_comp = r_info.get("completed", 0)
        r_pend = r_info.get("pending", 0)
        status_icon = "✅" if r_pend == 0 and r_tot > 0 else "⏳"
        print(f"  {status_icon} {label:<58} | Done: {r_comp:2d}/{r_tot:2d} | Pend: {r_pend:2d}")

    if stats["next_pending"]:
        print("-" * 80)
        print("🔍 NEXT PRIORITY THREADS WAITING FOR AUDIT:")
        for idx, item in enumerate(stats["next_pending"], 1):
            tid = item["thread_id"]
            score = item["salience_score"]
            cat = item["primary_category"]
            src = item["radar_sources"]
            date = item["start_date"]
            msgs = item["message_count"]
            words = item["total_words"]
            print(f"  {idx}. [{date}] {tid:<26} (Score: {score:.1f} | {msgs} msgs, {words} words | {cat})")
            print(f"     Radars: {src}")
            print(f"     Inspect: python3 project/scripts/query_chat.py -t {tid}")

    print("=" * 80 + "\n")


def print_next_thread(conn: sqlite3.Connection, chat_id: str):
    """Fetch and print the next pending thread with metadata and instructions."""
    cur = conn.cursor()
    cur.execute("""
    SELECT t.thread_id, t.chat_id, t.start_date, t.end_date, t.message_count,
           t.participants, t.initiator, t.dialogue_text,
           tac.radar_sources, tac.salience_score, tac.primary_category,
           tac.status
    FROM thread_audit_checklist tac
    JOIN threads t ON tac.thread_id = t.thread_id
    WHERE tac.chat_id = ? AND tac.status = 'pending'
    ORDER BY tac.salience_score DESC, tac.total_words DESC
    LIMIT 1;
    """, (chat_id,))
    row = cur.fetchone()
    if not row:
        print(f"\n[✓] All substantive threads for chat '{chat_id}' are resolved! (0 pending threads).\n")
        return

    tid = row[0]
    c_id = row[1]
    start_d = row[2][:16].replace("T", " ") if row[2] else ""
    end_d = row[3][:16].replace("T", " ") if row[3] else ""
    msgs = row[4]
    parts = row[5]
    init = row[6]
    dialogue = row[7] or ""
    radars = row[8]
    score = row[9]
    cat = row[10]

    # Sample preview of dialogue (first ~1000 chars)
    preview = dialogue[:1200]
    if len(dialogue) > 1200:
        preview += "\n... [Preview truncated. Run query_chat.py -t to view complete transcript] ..."

    print("\n" + "=" * 80)
    print(f"🎯 NEXT THREAD TO AUDIT: {tid}")
    print("=" * 80)
    print(f"  • Date Range:    {start_d} -> {end_d}")
    print(f"  • Participants:  {parts} (Initiator: {init})")
    print(f"  • Volume:        {msgs} messages | Salience Score: {score:.2f} | Category: {cat}")
    print(f"  • Radar Flags:   {radars}")
    print("-" * 80)
    print("📜 DIALOGUE TRANSCRIPT PREVIEW:")
    print("-" * 80)
    print(preview)
    print("-" * 80)
    print("🛠️ INVESTIGATION WORKFLOW & ACTIONS:")
    print(f"  1. Full Transcript:   python3 project/scripts/query_chat.py -t {tid}")
    print(f"  2. Context Window:    python3 project/scripts/query_chat.py --around <first_msg_id> -n 5")
    print(f"  3. Record Findings:   python3 project/scripts/thread_checklist.py -C {chat_id} --update {tid} \\")
    print(f"                        --set-status completed \\")
    print(f"                        --findings \"<Detailed psychological takeaways, defenses, attachment markers>\" \\")
    print(f"                        --quotes \"[#ID | {start_d[:10]}] \\\"verbatim quote\\\"\" \\")
    print(f"                        --tags \"#topic1 #defense #attachment\"")
    print("=" * 80 + "\n")


def update_thread_item(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    status: str,
    findings: Optional[str] = None,
    quotes: Optional[str] = None,
    tags: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """Update an individual thread audit record."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute("SELECT thread_id FROM thread_audit_checklist WHERE chat_id = ? AND thread_id = ?;", (chat_id, thread_id))
    if not cur.fetchone():
        print(f"[!] Warning: Thread '{thread_id}' not found in audit checklist for chat '{chat_id}'. Enrolling now.")
        cur.execute("""
        INSERT INTO thread_audit_checklist (
            chat_id, thread_id, radar_sources, salience_score, primary_category,
            start_date, message_count, total_words, status, updated_at
        ) VALUES (?, ?, 'manual_enrollment', 2.0, 'general', '', 0, 0, 'pending', ?);
        """, (chat_id, thread_id, now_iso))

    updates = ["status = ?", "updated_at = ?"]
    params: List[Any] = [status, now_iso]

    if findings is not None:
        updates.append("findings_summary = ?")
        params.append(findings)
    if quotes is not None:
        updates.append("key_quotes = ?")
        params.append(quotes)
    if tags is not None:
        updates.append("thematic_tags = ?")
        params.append(tags)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    params.extend([chat_id, thread_id])
    sql = f"UPDATE thread_audit_checklist SET {', '.join(updates)} WHERE chat_id = ? AND thread_id = ?;"
    cur.execute(sql, params)
    conn.commit()
    return cur.rowcount > 0


def batch_update_threads(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_ids: List[str],
    status: str,
    notes: Optional[str] = None
) -> int:
    """Batch update multiple thread audit records."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0

    for tid in thread_ids:
        cur.execute("""
        UPDATE thread_audit_checklist
        SET status = ?,
            notes = coalesce(notes || ' | ', '') || coalesce(?, ''),
            updated_at = ?
        WHERE chat_id = ? AND thread_id = ?;
        """, (status, notes, now_iso, chat_id, tid))
        updated += cur.rowcount

    conn.commit()
    return updated


def check_gate(conn: sqlite3.Connection, chat_id: str) -> int:
    """
    Hard-stop blocking gate validation.
    Returns 0 if all threads are resolved or checklist is waived.
    Returns 1 if pending threads remain.
    """
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    is_waived, reason = is_thread_checklist_waived(conn, chat_id)
    if is_waived:
        print(f"[✓] PASSED (EXEMPT): Thread audit checklist is waived for chat '{chat_id}'.")
        print(f"    Reason: {reason}")
        return 0

    cur.execute("""
    SELECT count(*),
           sum(case when status = 'pending' then 1 else 0 end)
    FROM thread_audit_checklist
    WHERE chat_id = ?;
    """, (chat_id,))
    row = cur.fetchone()
    total = row[0] or 0
    pending = row[1] or 0

    if total == 0:
        print(f"[!] Warning: No threads enrolled in thread_audit_checklist for chat '{chat_id}'.")
        print(f"    Run: python3 project/scripts/thread_checklist.py -C {chat_id} --init")
        return 1

    if pending == 0:
        print(f"[✓] PASSED: 100% of substantive threads ({total}/{total}) are resolved for chat '{chat_id}'.")
        return 0
    else:
        print(f"[✗] FAILED: Blocking gate active! {pending} of {total} substantive threads are still 'pending'.")
        print(f"    The agent is strictly prohibited from assembling the final report until all threads are audited.")
        print(f"    Inspect next pending thread with: python3 project/scripts/thread_checklist.py -C {chat_id} --next")
        return 1


def resolve_chat_id(conn: sqlite3.Connection, chat_input: Optional[str]) -> Optional[str]:
    """Helper to resolve chat_id from id or name."""
    cur = conn.cursor()
    cur.execute("SELECT chat_id, chat_name FROM chats;")
    rows = cur.fetchall()
    if not rows:
        return None
    if not chat_input:
        if len(rows) == 1:
            return rows[0][0]
        return None
    for cid, cname in rows:
        if cid == chat_input or (cname and cname.lower() == chat_input.lower()):
            return cid
    return None


def export_delta_manifest(
    conn: sqlite3.Connection,
    chat_id: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Export concise manifest of pending threads with triage summaries and candidate entities for Delta Triage Subagent."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0

    if has_triage:
        cur.execute("PRAGMA table_info(thread_triage);")
        tcols = {col[1] for col in cur.fetchall()}
        sum_col = "coalesce(tt.summary_short, 'No summary generated yet')" if "summary_short" in tcols else "'No summary generated yet'"
        ent_col = "coalesce(tt.candidate_entities, '[]')" if "candidate_entities" in tcols else "'[]'"

        sql = f"""
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               {sum_col}, {ent_col},
               substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        LEFT JOIN thread_triage tt ON tac.thread_id = tt.thread_id
        WHERE tac.chat_id = ? AND tac.status = 'pending'
        ORDER BY tac.salience_score DESC, tac.message_count DESC
        """
    else:
        sql = """
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               'No summary generated yet', '[]',
               substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        WHERE tac.chat_id = ? AND tac.status = 'pending'
        ORDER BY tac.salience_score DESC, tac.message_count DESC
        """

    if limit:
        sql += f" LIMIT {int(limit)}"

    cur.execute(sql, (chat_id,))
    rows = cur.fetchall()

    manifest = []
    for r in rows:
        manifest.append({
            "thread_id": r[0],
            "radar_sources": r[1],
            "salience_score": r[2],
            "category": r[3],
            "date": r[4],
            "messages": r[5],
            "words": r[6],
            "summary": r[7],
            "candidate_entities": r[8],
            "sample_snippet": r[9].strip().replace("\n", " ") if r[9] else ""
        })
    return manifest


def print_delta_manifest(manifest: List[Dict[str, Any]], chat_id: str):
    """Print high-density delta manifest for prompt construction."""
    print("=" * 80)
    print(f"📋 DELTA TRIAGE MANIFEST: {len(manifest)} PENDING THREADS FOR CHAT '{chat_id}'")
    print("=" * 80)
    print("Instructions for Delta Subagent: Compare each thread summary against established baseline.")
    print("Filter into: (1) NOVELTY/ANOMALY (needs deep dive) vs (2) CORROBORATING/REDUNDANT.")
    print("-" * 80)

    for i, m in enumerate(manifest, 1):
        print(f"[{i:03d}] Thread {m['thread_id']} | Date: {m['date']} | Msgs: {m['messages']} | Score: {m['salience_score']:.1f} | Radars: {m['radar_sources']}")
        print(f"      Summary:  {m['summary']}")
        if m['candidate_entities'] and m['candidate_entities'] != "[]":
            print(f"      Entities: {m['candidate_entities']}")
        print(f"      Snippet:  \"{m['sample_snippet'][:120]}...\"\n")


def resolve_redundant_threads(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_ids: List[str],
    reason: str
) -> int:
    """Safely resolve redundant/corroborating threads with full audit trail and theoretical saturation notes."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0

    clean_reason = reason.strip() or "Theoretical saturation: Corroborates established baseline"
    for tid in thread_ids:
        cur.execute("""
        UPDATE thread_audit_checklist
        SET status = 'completed',
            findings_summary = 'Theoretical Saturation: Redundant discussion corroborating established baseline',
            notes = coalesce(notes || ' | ', '') || 'Corroborating: ' || ?,
            updated_at = ?
        WHERE chat_id = ? AND thread_id = ?;
        """, (clean_reason, now_iso, chat_id, tid))
        updated += cur.rowcount

    conn.commit()
    return updated


def main():
    parser = argparse.ArgumentParser(description="Thread Forensic Audit Checklist & Gatekeeper")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--chat", "-C", type=str, help="Target chat_id or chat_name")
    parser.add_argument("--init", action="store_true", help="Initialize thread audit checklist from triage and intensive threads")
    parser.add_argument("--reset", action="store_true", help="Wipe and rebuild checklist (used with --init)")
    parser.add_argument("--status", action="store_true", help="Display progress and radar breakdown")
    parser.add_argument("--next", action="store_true", help="Fetch and inspect next pending thread")
    parser.add_argument("--update", type=str, metavar="THREAD_ID", help="Thread ID to update")
    parser.add_argument("--set-status", type=str, choices=list(VALID_STATUSES), help="Set thread status")
    parser.add_argument("--findings", type=str, help="Psychological findings / dynamics for the thread")
    parser.add_argument("--quotes", type=str, help="Anchored verbatim quotes [#ID | YYYY-MM-DD]")
    parser.add_argument("--tags", type=str, help="Thematic tags (e.g. #defense #attachment)")
    parser.add_argument("--notes", type=str, help="Additional notes")
    parser.add_argument("--batch-update", nargs="+", metavar="THREAD_ID", help="Batch update multiple thread IDs")
    parser.add_argument("--export-delta-manifest", action="store_true", help="Export manifest of pending threads with summaries for Delta Triage Subagent")
    parser.add_argument("--resolve-redundant", nargs="+", metavar="THREAD_ID", help="Mark redundant/corroborating threads as completed with saturation note")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of items for export-delta-manifest")
    parser.add_argument("--check", action="store_true", help="Run hard-stop gatekeeper check (exit 0 if resolved, exit 1 if pending)")
    parser.add_argument("--waive", action="store_true", help="Waive/disable thread audit for ad-hoc / partial tasks")
    parser.add_argument("--reason", type=str, default="Ad-hoc task / partial inquiry", help="Reason for waiver")
    parser.add_argument("--enable", action="store_true", help="Re-enable thread checklist after waiver")
    parser.add_argument("--ignore-prerequisites", action="store_true", help="Bypass prerequisite check (e.g. Entity Watchdog)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[!] Error: Database not found at '{args.db}'")
        sys.exit(1)

    conn = sqlite3.connect(args.db)
    chat_id = resolve_chat_id(conn, args.chat)

    if not chat_id:
        print("[!] Error: Could not determine chat_id. Please specify -C <chat_id>.")
        conn.close()
        sys.exit(1)

    if args.init:
        if not args.ignore_prerequisites:
            try:
                from query_chat import check_watchdog_gate
            except ImportError:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from query_chat import check_watchdog_gate

            watchdog_code = check_watchdog_gate(conn, chat_id)
            if watchdog_code != 0:
                print("\n[!] PREREQUISITE ERROR: You cannot initialize or audit the thread forensic checklist before resolving all third-party entities!", file=sys.stderr)
                print(f"    Entity identification is the essential foundation for interpreting interpersonal threads without Single-Entity Blindness.", file=sys.stderr)
                print(f"    Run the sequential watchdog scan first: python3 project/scripts/query_chat.py -C {chat_id} --watchdog-scan", file=sys.stderr)
                print(f"    (Pass --ignore-prerequisites only for testing or partial tasks).\n", file=sys.stderr)
                conn.close()
                sys.exit(1)

        res = init_thread_checklist(conn, chat_id, reset=args.reset)
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[✓] Initialized thread audit checklist for chat '{chat_id}'.")
            print(f"    Total enrolled threads: {res['total_threads_enrolled']} ({res['newly_inserted']} new, {res['updated_sources']} updated).")
        sys.exit(0)

    if args.waive:
        count = waive_thread_checklist(conn, chat_id, reason=args.reason)
        conn.close()
        if args.json:
            print(json.dumps({"action": "waive", "chat_id": chat_id, "waived": count, "reason": args.reason}))
        else:
            print(f"[✓] Thread audit checklist WAIVED for chat '{chat_id}' ({count} threads marked not_applicable).")
        sys.exit(0)

    if args.enable:
        count = enable_thread_checklist(conn, chat_id)
        conn.close()
        if args.json:
            print(json.dumps({"action": "enable", "chat_id": chat_id, "re_enabled": count}))
        else:
            print(f"[✓] Thread audit checklist RE-ENABLED for chat '{chat_id}' ({count} threads reverted to pending).")
        sys.exit(0)

    if args.export_delta_manifest:
        manifest = export_delta_manifest(conn, chat_id, limit=args.limit)
        conn.close()
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            print_delta_manifest(manifest, chat_id)
        sys.exit(0)

    if args.resolve_redundant:
        r_count = resolve_redundant_threads(conn, chat_id, args.resolve_redundant, args.reason)
        conn.close()
        if args.json:
            print(json.dumps({"action": "resolve_redundant", "count": r_count, "reason": args.reason}))
        else:
            print(f"[✓] Safely resolved {r_count} redundant threads with reason: '{args.reason}'.")
        sys.exit(0)

    if args.update:
        if not args.set_status:
            print("[!] Error: --set-status is required when updating a thread.")
            conn.close()
            sys.exit(1)
        ok = update_thread_item(
            conn, chat_id, args.update, args.set_status,
            findings=args.findings, quotes=args.quotes, tags=args.tags, notes=args.notes
        )
        conn.close()
        if args.json:
            print(json.dumps({"thread_id": args.update, "updated": ok, "status": args.set_status}))
        else:
            print(f"[✓] Updated thread '{args.update}' -> status: '{args.set_status}'.")
        sys.exit(0)

    if args.batch_update:
        if not args.set_status:
            print("[!] Error: --set-status is required when batch updating.")
            conn.close()
            sys.exit(1)
        count = batch_update_threads(conn, chat_id, args.batch_update, args.set_status, notes=args.notes)
        conn.close()
        if args.json:
            print(json.dumps({"batch_count": count, "status": args.set_status}))
        else:
            print(f"[✓] Batch updated {count} threads -> status: '{args.set_status}'.")
        sys.exit(0)

    if args.next:
        print_next_thread(conn, chat_id)
        conn.close()
        sys.exit(0)

    if args.check:
        code = check_gate(conn, chat_id)
        conn.close()
        sys.exit(code)

    # Default to status
    stats = get_thread_checklist_stats(conn, chat_id)
    conn.close()
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print_thread_status(stats)


if __name__ == "__main__":
    main()
