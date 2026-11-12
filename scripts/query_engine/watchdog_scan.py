"""Sequential System-1 entity watchdog scanner over third-party threads."""

import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from common.config import load_config
from .entities import ensure_entities_tables

try:
    from triage_threads import verify_unregistered_entities_decider
except ImportError:
    verify_unregistered_entities_decider = None


def run_sequential_watchdog_scan(
    db_path: str,
    chat_id: str,
    limit: Optional[int] = None,
    reset: bool = False
) -> Dict[str, Any]:
    """Run sequential System-1 entity watchdog scan on third-party threads.

    Iterates thread-by-thread:
    1. Checks if thread contains any entity NOT in currently registered list S.
    2. If NO -> thread is marked 'cleared' and scan automatically advances.
    3. If YES -> stops immediately at this thread, prints dialogue excerpt and profiler directives.
    4. Profiler identifies/registers new entity, then re-runs --watchdog-check on same thread.
    5. If all entities in thread are registered, System-1 returns NO and scan resumes.
    """
    if verify_unregistered_entities_decider is None:
        raise ImportError("verify_unregistered_entities_decider could not be imported from triage_threads.py")

    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    if reset:
        cur.execute("DELETE FROM thread_entity_audit WHERE chat_id = ?;", (chat_id,))
        conn.commit()
        print(f"[✓] Reset watchdog scan audit progress for chat '{chat_id}'.")

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0

    if has_triage:
        # Get threads with mentions_third_party = 1 or new untriaged threads
        cur.execute("""
        SELECT t.thread_id, t.start_date, t.dialogue_text, t.participants,
               COALESCE(a.status, 'pending') as audit_status
        FROM threads t
        LEFT JOIN thread_triage tt ON t.thread_id = tt.thread_id
        LEFT JOIN thread_entity_audit a ON t.thread_id = a.thread_id
        WHERE t.chat_id = ? AND (tt.mentions_third_party = 1 OR tt.thread_id IS NULL)
        ORDER BY t.start_date ASC;
        """, (chat_id,))
    else:
        # Triage not run: scan all substantive dialogue threads directly
        cur.execute("""
        SELECT t.thread_id, t.start_date, t.dialogue_text, t.participants,
               COALESCE(a.status, 'pending') as audit_status
        FROM threads t
        LEFT JOIN thread_entity_audit a ON t.thread_id = a.thread_id
        WHERE t.chat_id = ? AND length(trim(t.dialogue_text)) > 0
        ORDER BY t.start_date ASC;
        """, (chat_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        print(f"[*] No pending threads found to scan for chat '{chat_id}'.")
        return {"status": "empty"}

    cfg = load_config()
    api_key = (cfg.get("api_key") or cfg.get("openrouter_api_key", "")).strip()
    model = cfg.get("triage_model", "perplexity/pplx-decider-v1.2")

    total_threads = len(rows)
    cleared_count = sum(1 for r in rows if r[4] in ('cleared', 'skipped'))
    print("\n" + "=" * 80)
    print(f"🔍 SEQUENTIAL ENTITY WATCHDOG SCANNER [Chat: {chat_id}]")
    print(f"   Total Third-Party Threads: {total_threads}")
    print(f"   Already Cleared / Skipped: {cleared_count}")
    print(f"   Model (System-1 Decider):  {model}")
    print("=" * 80)

    processed_in_this_run = 0

    for idx, (tid, sdate, diag_text, participants, audit_status) in enumerate(rows, 1):
        if audit_status in ('cleared', 'skipped'):
            continue

        if limit is not None and processed_in_this_run >= limit:
            print(f"\n[*] Scan limit ({limit}) reached for this execution.")
            break

        # Load currently registered entities fresh from DB with roles and descriptors
        cur.execute("SELECT name_or_alias, verified_role, associated_descriptors FROM chat_entities WHERE chat_id = ?;", (chat_id,))
        known_names = []
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

        print(f"[{idx}/{total_threads}] Checking thread {tid} ({sdate}) against {len(known_names)} known entities...", end="", flush=True)

        try:
            has_unregistered, prob = verify_unregistered_entities_decider(
                dialogue_text=diag_text,
                known_names=known_names,
                model=model,
                api_key=api_key
            )
        except Exception as e:
            print(f" [ERROR: {e}]")
            break

        processed_in_this_run += 1

        now_str = datetime.now(timezone.utc).isoformat()
        if not has_unregistered:
            cur.execute("""
            INSERT OR REPLACE INTO thread_entity_audit (thread_id, chat_id, status, last_known_count, probability, audited_at)
            VALUES (?, ?, 'cleared', ?, ?, ?);
            """, (tid, chat_id, len(known_names), prob, now_str))
            conn.commit()
            print(f" [✓ CLEARED] (p={prob:.2f})")
        else:
            cur.execute("""
            INSERT OR REPLACE INTO thread_entity_audit (thread_id, chat_id, status, last_known_count, probability, audited_at)
            VALUES (?, ?, 'unregistered_detected', ?, ?, ?);
            """, (tid, chat_id, len(known_names), prob, now_str))
            conn.commit()
            print(f" [🚨 NEW ENTITY DETECTED] (p={prob:.2f})\n")

            print("-" * 80)
            print(f"🚨 UNREGISTERED THIRD-PARTY DETECTED IN THREAD: {tid}")
            print(f"   Date:              {sdate}")
            print(f"   Known Entities S:  [{', '.join(known_names)}]")
            print(f"   Confidence / Prob: {prob:.2f}")
            print("-" * 80)
            print("📜 DIALOGUE TRANSCRIPT EXCERPT:")
            lines = diag_text.strip().split("\n")
            preview_lines = lines[:20] if len(lines) > 20 else lines
            for l in preview_lines:
                print(f"   {l}")
            if len(lines) > 20:
                print(f"   ... [{len(lines)-20} more messages in thread]")
            print("-" * 80)
            print("👉 PROFILER / AGENT ACTION REQUIRED:")
            print(f"   1. Identify the new entity name/role in thread {tid}.")
            print(f"   2. Register the new entity:")
            print(f"      python3 project/scripts/query_chat.py -C {chat_id} --register-entity \"<Name>\" --role \"<Role>\"")
            print(f"   3. Re-verify this thread to ensure no secondary entities were missed:")
            print(f"      python3 project/scripts/query_chat.py -C {chat_id} --watchdog-check {tid}")
            print(f"   4. If cleared, resume scan with:")
            print(f"      python3 project/scripts/query_chat.py -C {chat_id} --watchdog-scan")
            print(f"   5. If this is a false alarm or bystander to skip, run:")
            print(f"      python3 project/scripts/query_chat.py -C {chat_id} --skip-thread {tid}")
            print("=" * 80 + "\n")
            conn.close()
            return {
                "status": "stopped_at_new_entity",
                "thread_id": tid,
                "date": sdate,
                "known_entities": known_names,
                "probability": prob
            }

    conn.close()
    print("\n[✓] Sequential Watchdog Scan iteration complete.")
    return {"status": "completed", "processed": processed_in_this_run}
