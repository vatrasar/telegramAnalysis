"""Blocking gate check for Life Spheres Checklist."""

import sqlite3
from typing import List, Dict, Any, Tuple

from checklist_engine.spheres_def import MANDATORY_SEMANTIC_ITEMS
from checklist_engine.spheres_db import get_checklist_stats


def check_gate(conn: sqlite3.Connection, chat_id: str, enforce_semantic: bool = True) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Check pipeline blocking gate.
    Returns (exit_code, violations).
    Exit code 0: complete/waived and all semantic invariants satisfied.
    Exit code 1: pending items remain or semantic invariants violated.
    """
    stats = get_checklist_stats(conn, chat_id)
    if stats.get("is_waived"):
        return 0, []
    if stats.get("total", 0) == 0:
        return 1, [{"item_id": "ALL", "sphere_id": "-", "sub_item": "Checklist uninitialized", "status": "pending", "issue": "Checklist is not initialized. Run --init first."}]
    if not stats.get("is_complete", False):
        return 1, [{"item_id": "PENDING", "sphere_id": "-", "sub_item": f"{stats['pending']} items pending", "status": "pending", "issue": f"{stats['pending']} items remain pending audit."}]

    if not enforce_semantic:
        return 0, []

    cur = conn.cursor()
    cur.execute("""
    SELECT item_id, sphere_id, sphere_name, sub_item, status, evidence_summary, query_terms_used, semantic_queries_used
    FROM life_spheres_checklist
    WHERE chat_id = ? AND status IN ('completed', 'no_data');
    """, (chat_id,))
    rows = cur.fetchall()

    violations = []
    for r in rows:
        i_id, s_id, s_name, sub_item, status, notes, q_used, sem_used = r
        sem_clean = (sem_used or "").strip()

        # Invariant 1: Unverified Negative Claims (no_data without vector probing)
        if status == "no_data" and not sem_clean:
            violations.append({
                "item_id": i_id,
                "sphere_id": s_id,
                "sub_item": sub_item,
                "status": status,
                "issue": "Concluded 'no_data' without mandatory semantic vector probing. Lexical keyword absence does NOT prove empirical absence in dialogue."
            })
        # Invariant 2: Abstract / Attitudinal / Psychological dimensions completed without vector probing
        elif status == "completed" and i_id in MANDATORY_SEMANTIC_ITEMS and not sem_clean:
            violations.append({
                "item_id": i_id,
                "sphere_id": s_id,
                "sub_item": sub_item,
                "status": status,
                "issue": f"Core psychological/attitudinal item ({s_name}) marked 'completed' without recorded semantic vector search. Chat participants do not speak in clinical/diagnostic keywords."
            })

    if violations:
        return 1, violations
    return 0, []
