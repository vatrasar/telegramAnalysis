#!/usr/bin/env python3
"""
Life Spheres Forensic Checklist & Verification Manager CLI Entrypoint.
Tracks, audits, and enforces complete evidentiary coverage of foundational life spheres
(Social Matrix, Work & Ambitions, Worldview & Tech, Family Roots, Romantic Attachment, Leisure & Animals)
in the analytical SQLite database (chat.db).
"""

import os
import sys
import json
import sqlite3
import argparse

# Ensure local script packages are resolvable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_default_db_path, connect_db
from checklist_engine.spheres_def import (
    CHECKLIST_DEFINITIONS,
    MANDATORY_SEMANTIC_ITEMS,
    VALID_STATUSES,
    RESOLVED_STATUSES,
)
from checklist_engine.spheres_db import (
    ensure_checklist_table,
    is_checklist_waived,
    waive_checklist,
    enable_checklist,
    resolve_chat_id,
    init_checklist,
    get_checklist_stats,
    update_checklist_item,
    list_checklist_items,
)
from checklist_engine.spheres_gate import check_gate
from checklist_engine.spheres_view import print_status_summary, print_items_list

DEFAULT_DB_PATH = get_default_db_path()

__all__ = [
    "DEFAULT_DB_PATH",
    "CHECKLIST_DEFINITIONS",
    "MANDATORY_SEMANTIC_ITEMS",
    "VALID_STATUSES",
    "RESOLVED_STATUSES",
    "ensure_checklist_table",
    "is_checklist_waived",
    "waive_checklist",
    "enable_checklist",
    "resolve_chat_id",
    "init_checklist",
    "get_checklist_stats",
    "update_checklist_item",
    "list_checklist_items",
    "check_gate",
    "print_status_summary",
]


def main():
    parser = argparse.ArgumentParser(
        description="Life Spheres Forensic Checklist & Verification Manager."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite analytical database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--chat", "-C",
        type=str,
        default=None,
        help="Chat ID or chat name (auto-detected if only 1 chat exists in database)"
    )

    action_group = parser.add_mutually_exclusive_group(required=False)
    action_group.add_argument(
        "--init",
        action="store_true",
        help="Initialize checklist items in the database for the selected chat"
    )
    action_group.add_argument(
        "--status", "--summary",
        action="store_true",
        help="Display completion progress and breakdown across all 6 life spheres"
    )
    action_group.add_argument(
        "--list",
        action="store_true",
        help="List checklist items with their current statuses"
    )
    action_group.add_argument(
        "--update",
        type=str,
        metavar="ITEM_ID",
        help="Update status and notes for a specific checklist item_id"
    )
    action_group.add_argument(
        "--batch-update",
        nargs="+",
        metavar="ITEM_ID",
        help="Update multiple item_ids to the same status in one command"
    )
    action_group.add_argument(
        "--check",
        action="store_true",
        help="Pipeline Gate Verification: exits with 0 if all items are resolved or waived; exits with 1 if any pending items remain"
    )
    action_group.add_argument(
        "--waive", "--bypass", "--disable",
        action="store_true",
        help="Waive/disable the checklist for ad-hoc queries or tasks not requiring full life spheres profiling"
    )
    action_group.add_argument(
        "--enable",
        action="store_true",
        help="Re-enable the checklist for full profiling (clears waiver and resets waived items to pending)"
    )
    action_group.add_argument(
        "--facts-for-sphere",
        type=str,
        metavar="SPHERE_OR_NAME",
        help="Display pre-extracted facts and evidence tagged for a specific life sphere (A-F or name)"
    )

    parser.add_argument(
        "--reason",
        type=str,
        default="Ad-hoc task / partial inquiry (full profiling not required)",
        help="Reason for waiving the checklist with --waive"
    )
    parser.add_argument(
        "--set-status",
        type=str,
        choices=list(VALID_STATUSES),
        help="Status to set for --update or --batch-update (pending, completed, no_data, not_applicable)"
    )
    parser.add_argument(
        "--notes", "--evidence",
        type=str,
        help="Evidence findings summary or probe attempt details for --update / --batch-update"
    )
    parser.add_argument(
        "--queries",
        type=str,
        help="Search query terms used during probing for --update / --batch-update"
    )
    parser.add_argument(
        "--semantic-queries", "-sem-q",
        type=str,
        help="Semantic vector search queries executed during probing"
    )
    parser.add_argument(
        "--skip-semantic-check",
        action="store_true",
        help="Bypass semantic vector search verification during --check (testing only)"
    )
    parser.add_argument(
        "--filter-status",
        type=str,
        help="Filter items by status for --list"
    )
    parser.add_argument(
        "--sphere",
        type=str,
        help="Filter items by sphere ID (A, B, C, D, E, F) or name for --list"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Display detailed descriptions, notes, and query terms when using --list"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Force reinitialization of all checklist items to pending when using --init"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--ignore-prerequisites",
        action="store_true",
        help="Bypass prerequisite check (e.g. Entity Watchdog)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[!] Error: Database not found at '{args.db}'. Ingest Telegram exports first.")
        sys.exit(1)

    conn = connect_db(args.db)

    try:
        chat_id = resolve_chat_id(conn, args.chat)
    except ValueError as e:
        print(f"[!] Error: {e}")
        conn.close()
        sys.exit(1)

    if args.init:
        if not args.ignore_prerequisites:
            from query_chat import check_watchdog_gate
            watchdog_code = check_watchdog_gate(conn, chat_id)
            if watchdog_code != 0:
                print("\n[!] PREREQUISITE ERROR: You cannot initialize or audit the Life Spheres checklist before resolving all third-party entities!", file=sys.stderr)
                print(f"    Run the sequential watchdog scan first: python3 project/scripts/query_chat.py -C {chat_id} --watchdog-scan", file=sys.stderr)
                conn.close()
                sys.exit(1)

        inserted, total = init_checklist(conn, chat_id, reset=args.reset)
        if args.json:
            print(json.dumps({"action": "init", "chat_id": chat_id, "inserted": inserted, "total": total}))
        else:
            action_desc = "Reinitialized" if args.reset else "Initialized"
            print(f"[✓] {action_desc} Life Spheres Checklist for chat '{chat_id}' ({inserted} inserted / {total} total dimensions).")
        conn.close()
        sys.exit(0)

    if args.waive:
        waived_count = waive_checklist(conn, chat_id, reason=args.reason)
        if args.json:
            print(json.dumps({"action": "waive", "chat_id": chat_id, "waived_count": waived_count, "reason": args.reason}))
        else:
            print(f"[✓] Life Spheres Checklist WAIVED for chat '{chat_id}' ({waived_count} pending items set to 'not_applicable').")
            print(f"    Reason: {args.reason}")
        conn.close()
        sys.exit(0)

    if args.enable:
        re_enabled = enable_checklist(conn, chat_id)
        if args.json:
            print(json.dumps({"action": "enable", "chat_id": chat_id, "re_enabled_count": re_enabled}))
        else:
            print(f"[✓] Life Spheres Checklist RE-ENABLED for chat '{chat_id}' ({re_enabled} items reset to 'pending').")
        conn.close()
        sys.exit(0)

    if args.update or args.batch_update:
        targets = [args.update] if args.update else args.batch_update
        if not args.set_status:
            print("[!] Error: --set-status is required when updating checklist items.")
            conn.close()
            sys.exit(1)

        updated_items = []
        for tid in targets:
            ok = update_checklist_item(
                conn, chat_id, tid, args.set_status,
                notes=args.notes, queries=args.queries, semantic_queries=args.semantic_queries
            )
            if ok:
                updated_items.append(tid)

        if args.json:
            print(json.dumps({"action": "update", "chat_id": chat_id, "status": args.set_status, "updated": updated_items}))
        else:
            print(f"[✓] Updated {len(updated_items)} checklist item(s) to '{args.set_status}'.")
        conn.close()
        sys.exit(0)

    if args.check:
        enforce_sem = not args.skip_semantic_check
        code, violations = check_gate(conn, chat_id, enforce_semantic=enforce_sem)
        if args.json:
            print(json.dumps({"gate_pass": (code == 0), "violations": violations}, indent=2))
        else:
            if code == 0:
                print(f"[✓] PASSED: Life Spheres Checklist Gate is SATISFIED for chat '{chat_id}'.")
            else:
                print(f"[✗] FAILED: Life Spheres Checklist Gate BLOCKED for chat '{chat_id}' ({len(violations)} violations).", file=sys.stderr)
                for v in violations:
                    print(f"    - [{v['item_id']}] {v['issue']}", file=sys.stderr)
        conn.close()
        sys.exit(code)

    if args.facts_for_sphere:
        from query_engine.facts_engine import get_discovered_facts, print_discovered_facts, normalize_category_and_sphere
        canon_cat, canon_sph = normalize_category_and_sphere(args.facts_for_sphere, args.facts_for_sphere)
        facts = get_discovered_facts(conn, chat_id, category=canon_cat if not canon_sph else None, sphere_id=canon_sph)
        if args.json:
            print(json.dumps({"sphere": canon_sph, "category": canon_cat, "facts": facts}, indent=2, ensure_ascii=False))
        else:
            lbl = f"Sphere {canon_sph}" if canon_sph else f"Category {canon_cat}"
            print_discovered_facts(facts, filter_label=lbl)
        conn.close()
        sys.exit(0)

    if args.list:
        items = list_checklist_items(conn, chat_id, status_filter=args.filter_status, sphere_filter=args.sphere)
        if args.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
        else:
            print_items_list(items, detailed=args.detailed)
        conn.close()
        sys.exit(0)

    # Default action: status summary
    stats = get_checklist_stats(conn, chat_id)
    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print_status_summary(stats)
    conn.close()


if __name__ == "__main__":
    main()
