"""Adversarial System-1 entity watchdog and anomaly post-check APIs."""

import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from common.config import load_config
from .entities import ensure_entities_tables

try:
    from triage_threads import verify_unregistered_entities_decider, verify_secondary_anomaly_decider
except ImportError:
    verify_unregistered_entities_decider = None
    verify_secondary_anomaly_decider = None


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
        cur.execute("SELECT name_or_alias, verified_role, associated_descriptors FROM chat_entities WHERE chat_id = ?;", (actual_chat_id,))
        for r in cur.fetchall():
            name, role, descs = r[0], r[1], r[2]
            label = name
            details = []
            if role:
                details.append(f"role: {role}")
            if descs:
                details.append(f"aliases/descriptors: {descs}")
            if details:
                label = f"{name} ({', '.join(details)})"
            known_names.append(label)
        if participants:
            for p in participants.split(","):
                p_clean = p.strip()
                if p_clean and p_clean not in known_names:
                    known_names.append(p_clean)

    conn.close()

    cfg = load_config()
    api_key = (cfg.get("api_key") or cfg.get("openrouter_api_key", "")).strip()
    model = cfg.get("triage_model", "openrouter/auto")

    has_unregistered, prob = verify_unregistered_entities_decider(
        dialogue_text=dialogue_text,
        known_names=known_names,
        model=model,
        api_key=api_key
    )

    # Persist audit status to thread_entity_audit table
    try:
        w_conn = sqlite3.connect(db_path)
        ensure_entities_tables(w_conn)
        w_cur = w_conn.cursor()
        w_status = "unregistered_detected" if has_unregistered else "cleared"
        w_cur.execute("""
        INSERT OR REPLACE INTO thread_entity_audit (thread_id, chat_id, status, last_known_count, probability, audited_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """, (actual_thread_id, actual_chat_id, w_status, len(known_names), round(prob, 3), datetime.now(timezone.utc).isoformat()))
        w_conn.commit()
        w_conn.close()
    except Exception:
        pass

    return {
        "thread_id": actual_thread_id,
        "chat_id": actual_chat_id,
        "known_entities": known_names,
        "has_unregistered_third_party": has_unregistered,
        "probability": round(prob, 3),
        "model_used": model
    }


def print_watchdog_result(res: Dict[str, Any]) -> None:
    """Print ASCII report of adversarial System-1 watchdog check."""
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


def run_anomaly_check(
    db_path: str,
    thread_id: str,
    chat_id: Optional[str] = None,
    identified: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute adversarial System-1 check to detect whether secondary/unaddressed anomalies remain in thread."""
    if verify_secondary_anomaly_decider is None:
        raise ImportError("verify_secondary_anomaly_decider could not be imported from triage_threads.py")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT thread_id, chat_id, dialogue_text FROM threads WHERE thread_id = ?;", (thread_id,))
    t_row = cur.fetchone()
    if not t_row:
        try:
            mid = int(thread_id)
            cur.execute("""
            SELECT t.thread_id, t.chat_id, t.dialogue_text
            FROM messages m
            JOIN threads t ON m.thread_id = t.thread_id
            WHERE m.id = ?;
            """, (mid,))
            t_row = cur.fetchone()
        except ValueError:
            pass

    if not t_row:
        conn.close()
        raise ValueError(f"Thread or message '{thread_id}' not found in database.")

    real_tid, c_id, dialogue_text = t_row
    conn.close()

    cfg = load_config()
    api_key = (cfg.get("api_key") or cfg.get("openrouter_api_key", "")).strip()
    model = cfg.get("triage_model", "openrouter/auto")

    has_secondary, prob = verify_secondary_anomaly_decider(
        dialogue_text=dialogue_text,
        identified_anomalies=identified or [],
        model=model,
        api_key=api_key
    )

    return {
        "thread_id": real_tid,
        "chat_id": c_id,
        "already_identified": identified or [],
        "has_secondary_anomaly": has_secondary,
        "probability": round(prob, 3),
        "model_used": model
    }


def print_anomaly_check_result(res: Dict[str, Any]) -> None:
    """Print ASCII report of anomaly post-check."""
    print("\n" + "=" * 80)
    print(f"🛡️  ADVERSARIAL SYSTEM-1 ANOMALY CHECK: Thread {res['thread_id']}")
    print(f"   Chat ID:              {res['chat_id']}")
    print(f"   Accounted Anomalies:  [{'; '.join(res['already_identified']) if res['already_identified'] else 'None'}]")
    print(f"   Model Used:           {res['model_used']}")
    print("-" * 80)
    if res["has_secondary_anomaly"]:
        print(f"🚨 SECONDARY ANOMALY SUSPECTED (Probability: {res['probability'] * 100:.1f}%)")
        print("   System 1 suspects another distinct unaddressed behavioral/emotional anomaly or crisis remains in this thread.")
    else:
        print(f"✅ PASSED: No secondary anomalies detected. (Confidence: {(1.0 - res['probability']) * 100:.1f}%)")
        print("   All salient crises and anomalies in this thread appear accounted for.")
    print("=" * 80 + "\n")


def skip_watchdog_thread(
    db_path: str,
    thread_id: str,
    chat_id: Optional[str] = None,
    reason: str = "agent_cleared_false_alarm"
) -> None:
    """Mark a thread as skipped/false-positive in entity scan to resume scanning."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()
    if not chat_id:
        cur.execute("SELECT chat_id FROM threads WHERE thread_id = ?;", (thread_id,))
        r = cur.fetchone()
        if r:
            chat_id = r[0]
        else:
            conn.close()
            raise ValueError(f"Thread '{thread_id}' not found.")

    cur.execute("""
    INSERT OR REPLACE INTO thread_entity_audit (thread_id, chat_id, status, notes, audited_at)
    VALUES (?, ?, 'skipped', ?, ?);
    """, (thread_id, chat_id, reason, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    print(f"\n[✓] Thread '{thread_id}' marked as SKIPPED (Reason: {reason}).")
    print(f"    You can now resume scanning with: python3 project/scripts/query_chat.py -C {chat_id} --watchdog-scan\n")


def print_watchdog_status(db_path: str, chat_id: str) -> None:
    """Print overall summary status of entity watchdog audit for the chat."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] == 0:
        print(f"[*] 'thread_triage' table not found in '{db_path}'. Run triage first via: python3 project/scripts/triage_threads.py")
        conn.close()
        return

    cur.execute("""
    SELECT COUNT(*) FROM threads t
    JOIN thread_triage tt ON t.thread_id = tt.thread_id
    WHERE t.chat_id = ? AND tt.mentions_third_party = 1;
    """, (chat_id,))
    total_third_party = cur.fetchone()[0]

    cur.execute("""
    SELECT status, COUNT(*) FROM thread_entity_audit
    WHERE chat_id = ?
    GROUP BY status;
    """, (chat_id,))
    counts = dict(cur.fetchall())
    cleared = counts.get("cleared", 0)
    skipped = counts.get("skipped", 0)
    detected = counts.get("unregistered_detected", 0)
    resolved = cleared + skipped
    pending = max(0, total_third_party - resolved)

    cur.execute("SELECT name_or_alias, verified_role FROM chat_entities WHERE chat_id = ? ORDER BY created_at ASC;", (chat_id,))
    entities = cur.fetchall()
    conn.close()

    print("\n" + "=" * 80)
    print(f"📊 SEQUENTIAL ENTITY WATCHDOG STATUS [Chat: {chat_id}]")
    print("=" * 80)
    print(f"Total Third-Party Threads: {total_third_party}")
    print(f"  ✓ Cleared (Only Known Entities):    {cleared}")
    print(f"  ⏭️  Skipped (False Alarm / Bystander): {skipped}")
    print(f"  🚨 Blocked at New Entity:           {detected}")
    print(f"  ⏳ Pending Audit:                    {pending}")
    pct = (resolved / total_third_party * 100) if total_third_party > 0 else 100.0
    print(f"Audit Progress: [{resolved}/{total_third_party}] ({pct:.1f}%)")
    print("-" * 80)
    print(f"Registered Entities in Chat ({len(entities)}):")
    if entities:
        for name, role in entities:
            print(f"  • {name}: {role or 'No role specified'}")
    else:
        print("  (None registered yet)")
    print("=" * 80 + "\n")


def check_watchdog_gate(conn_or_db: Any, chat_id: str) -> int:
    """Hard-stop blocking gate validation for Entity Watchdog Scan.

    Returns 0 if all third-party threads are resolved (cleared or skipped) and no unregistered entities remain detected.
    Returns 1 if pending or unregistered threads remain.
    """
    if isinstance(conn_or_db, str):
        conn = sqlite3.connect(conn_or_db)
        should_close = True
    else:
        conn = conn_or_db
        should_close = False

    ensure_entities_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0
    if not has_triage:
        print(f"[!] Warning: 'thread_triage' table does not exist. Thread triage must be run before watchdog audit.")
        if should_close:
            conn.close()
        return 1

    target_chats = [chat_id]
    if chat_id == "global" or not chat_id:
        cur.execute("SELECT DISTINCT chat_id FROM chats;")
        target_chats = [r[0] for r in cur.fetchall()]
        if not target_chats:
            cur.execute("SELECT DISTINCT chat_id FROM threads;")
            target_chats = [r[0] for r in cur.fetchall()]

    if not target_chats:
        print("[✓] PASSED (EXEMPT): No chats found in database to verify for Entity Watchdog.")
        if should_close:
            conn.close()
        return 0

    overall_failed = False

    for cid in target_chats:
        cur.execute("""
        SELECT COUNT(*) FROM threads t
        JOIN thread_triage tt ON t.thread_id = tt.thread_id
        WHERE t.chat_id = ? AND tt.mentions_third_party = 1;
        """, (cid,))
        total_third_party = cur.fetchone()[0]

        if total_third_party == 0:
            print(f"[✓] PASSED (EXEMPT): No third-party threads (mentions_third_party = 1) for chat '{cid}'.")
            continue

        cur.execute("""
        SELECT status, COUNT(*) FROM thread_entity_audit
        WHERE chat_id = ?
        GROUP BY status;
        """, (cid,))
        counts = dict(cur.fetchall())
        cleared = counts.get("cleared", 0)
        skipped = counts.get("skipped", 0)
        detected = counts.get("unregistered_detected", 0)
        resolved = cleared + skipped
        pending = max(0, total_third_party - resolved)

        if detected > 0:
            print(f"[✗] FAILED: Entity Watchdog gate active for chat '{cid}'! {detected} thread(s) have unregistered entities detected.")
            print(f"    Register identified entities and resolve threads using: python3 project/scripts/query_chat.py -C {cid} --watchdog-scan")
            overall_failed = True
        elif pending > 0:
            print(f"[✗] FAILED: Entity Watchdog gate active for chat '{cid}'! {pending} of {total_third_party} third-party threads are still pending audit.")
            print(f"    Current progress: [{resolved}/{total_third_party}]. Run: python3 project/scripts/query_chat.py -C {cid} --watchdog-scan")
            overall_failed = True
        else:
            print(f"[✓] PASSED: 100% of third-party threads ({resolved}/{total_third_party}) are verified for chat '{cid}'.")

    if should_close:
        conn.close()

    return 1 if overall_failed else 0
