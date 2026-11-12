"""Hard-stop gatekeeper verification for Thread Forensic Audit Checklist (Track B)."""

import sqlite3
from checklist_engine.threads_db import ensure_thread_checklist_table, is_thread_checklist_waived


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
        print("    The agent is strictly prohibited from assembling the final report until all threads are audited.")
        print(f"    Inspect next pending thread with: python3 project/scripts/thread_checklist.py -C {chat_id} --next")
        return 1
