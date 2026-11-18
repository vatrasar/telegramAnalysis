#!/usr/bin/env python3
"""
Thread Forensic Audit Checklist & Gatekeeper CLI Entrypoint (Track B).
Manages, audits, and enforces turn-by-turn psychological analysis of all
substantive, high-salience, and emotionally intense conversation threads in SQLite.
"""

import os
import sys
import json
import sqlite3
import argparse

# Ensure local script packages are resolvable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_default_db_path, connect_db
from checklist_engine.threads_db import (
    VALID_STATUSES,
    RESOLVED_STATUSES,
    ensure_thread_checklist_table,
    is_thread_checklist_waived,
    waive_thread_checklist,
    enable_thread_checklist,
    init_thread_checklist,
    get_thread_checklist_stats,
    update_thread_item,
    resolve_chat_id,
)
from checklist_engine.threads_evidence import (
    export_delta_manifest,
    resolve_redundant_threads,
    export_audited_evidence,
    route_thread_evidence,
    get_evidence_for_target,
)
from checklist_engine.evidence_triage import (
    auto_triage_evidence,
    batch_route_evidence,
)
from checklist_engine.custom_sections import (
    ensure_custom_sections_table,
    propose_custom_section,
    get_custom_sections,
    print_custom_sections,
)
from checklist_engine.threads_gate import check_gate
from checklist_engine.threads_view import (
    print_thread_status,
    print_next_thread,
    print_delta_manifest,
    print_audited_evidence,
    print_evidence_catalog,
    print_evidence_for_target,
)

DEFAULT_DB_PATH = get_default_db_path()

__all__ = [
    "DEFAULT_DB_PATH",
    "VALID_STATUSES",
    "RESOLVED_STATUSES",
    "ensure_thread_checklist_table",
    "is_thread_checklist_waived",
    "waive_thread_checklist",
    "enable_thread_checklist",
    "init_thread_checklist",
    "get_thread_checklist_stats",
    "update_thread_item",
    "resolve_chat_id",
    "export_delta_manifest",
    "resolve_redundant_threads",
    "export_audited_evidence",
    "check_gate",
    "print_thread_status",
    "print_next_thread",
    "print_delta_manifest",
    "print_audited_evidence",
    "print_evidence_catalog",
]


def main():
    parser = argparse.ArgumentParser(description="Thread Forensic Audit Checklist & Gatekeeper")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--chat", "-C", type=str, help="Target chat_id or chat_name")
    parser.add_argument("--init", action="store_true", help="Initialize thread audit checklist from triage and intensive threads")
    parser.add_argument("--reset", action="store_true", help="Wipe and rebuild checklist (used with --init)")
    parser.add_argument("--limit-intensive", type=int, default=0, help="Number of intensive discussions to include if triage is present (default: 0)")
    parser.add_argument("--status", action="store_true", help="Display progress and radar breakdown")
    parser.add_argument("--next", action="store_true", help="Fetch and inspect next pending thread")
    parser.add_argument("--update", type=str, metavar="THREAD_ID", help="Thread ID to update")
    parser.add_argument("--set-status", type=str, choices=list(VALID_STATUSES), help="Set thread status")
    parser.add_argument("--findings", type=str, help="Psychological findings / dynamics for the thread")
    parser.add_argument("--quotes", type=str, help="Anchored verbatim quotes [#ID | YYYY-MM-DD]")
    parser.add_argument("--tags", type=str, help="Thematic tags (e.g. #defense #attachment)")
    parser.add_argument("--notes", type=str, help="Additional notes")
    parser.add_argument("--export-delta-manifest", action="store_true", help="Export manifest of pending threads with summaries for Delta Triage Subagent")
    parser.add_argument("--export-evidence", action="store_true", help="Export complete bank of audited forensic evidence and quotes for final report synthesis")
    parser.add_argument("--evidence-catalog", action="store_true", help="Display thematic category/tag catalog of audited evidence to guide modular chapter drafting")
    parser.add_argument("--route-evidence", type=str, metavar="THREAD_ID", help="Route audited evidence to a target drafter agent and report chapter")
    parser.add_argument("--auto-triage-evidence", action="store_true", help="Automatically triage and route all audited evidence to chapters using System 1")
    parser.add_argument("--batch-route", type=str, metavar="FILE_OR_JSON", help="Batch route evidence items from a JSON file or JSON string")
    parser.add_argument("--concurrency", "-c", type=int, default=4, help="Concurrency for System-1 triage (default: 4)")
    parser.add_argument("--threshold", "-t", type=float, default=2.5, help="Salience threshold for System-1 evidence triage (default: 2.5)")
    parser.add_argument("--model", "-m", type=str, help="Override model for System-1 evidence triage")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already routed evidence items")
    parser.add_argument("--dry-run", action="store_true", help="Preview System-1 triage without modifying database")
    parser.add_argument("--target-agent", type=str, help="Target drafter agent (e.g. chapter-drafter, subsection-drafter)")
    parser.add_argument("--target-chapter", type=str, help="Target report chapter or sphere category (e.g. family, career, playbook)")
    parser.add_argument("--significance", type=str, help="Significance or rationale note for routed evidence")
    parser.add_argument("--evidence-for-target", type=str, metavar="TARGET", help="Display audited evidence routed specifically to an agent role or chapter")
    parser.add_argument("--propose-custom-section", action="store_true", help="Propose a novel custom chapter or subsection based on curated evidence")
    parser.add_argument("--section-title", type=str, help="Title of proposed custom section")
    parser.add_argument("--section-filename", type=str, help="Target markdown filename (e.g. 03_custom_gambling.md)")
    parser.add_argument("--section-rationale", type=str, help="Analytical justification and significance of proposed section")
    parser.add_argument("--section-type", type=str, choices=["chapter", "subsection"], default="chapter", help="Type of proposed section (default: chapter)")
    parser.add_argument("--section-threads", type=str, default="", help="Associated thread IDs for custom section")
    parser.add_argument("--section-quotes", type=str, default="", help="Key anchor quotes supporting custom section")
    parser.add_argument("--list-custom-sections", action="store_true", help="List all proposed custom report sections")
    parser.add_argument("--tag", type=str, help="Filter --export-evidence by thematic tag (e.g. #family, #ex, #career, #defense)")
    parser.add_argument("--category", type=str, help="Filter --export-evidence by primary category")
    parser.add_argument("--part", type=int, default=1, help="Part/slice number to display for long evidence lists (default: 1)")
    parser.add_argument("--part-size", type=int, default=8, help="Number of evidence items per part (default: 8)")
    parser.add_argument("--all", action="store_true", help="Display all evidence items at once without pagination")
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

    conn = connect_db(args.db)
    chat_id = resolve_chat_id(conn, args.chat)

    if not chat_id:
        print("[!] Error: Could not determine chat_id. Please specify -C <chat_id>.")
        conn.close()
        sys.exit(1)

    if args.init:
        if not args.ignore_prerequisites:
            from query_chat import check_watchdog_gate
            watchdog_code = check_watchdog_gate(conn, chat_id)
            if watchdog_code != 0:
                print("\n[!] PREREQUISITE ERROR: You cannot initialize or audit the thread forensic checklist before resolving all third-party entities!", file=sys.stderr)
                print(f"    Run the sequential watchdog scan first: python3 project/scripts/query_chat.py -C {chat_id} --watchdog-scan", file=sys.stderr)
                conn.close()
                sys.exit(1)

        res = init_thread_checklist(conn, chat_id, reset=args.reset, limit_intensive=args.limit_intensive)
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

    if args.evidence_catalog:
        print_evidence_catalog(conn, chat_id)
        conn.close()
        sys.exit(0)

    if args.route_evidence:
        res = route_thread_evidence(
            conn, chat_id, args.route_evidence,
            target_agent=args.target_agent,
            target_chapter=args.target_chapter,
            significance=args.significance,
            tags=args.tags
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[✓] Routed evidence for thread '{args.route_evidence}':")
            if args.target_agent:
                print(f"    Target Agent:   {args.target_agent}")
            if args.target_chapter:
                print(f"    Target Chapter: {args.target_chapter}")
            if args.significance:
                print(f"    Significance:   {args.significance}")
        sys.exit(0)

    if args.auto_triage_evidence:
        res = auto_triage_evidence(
            conn, chat_id,
            db_path=args.db,
            model=args.model,
            concurrency=args.concurrency,
            salience_threshold=args.threshold,
            force=args.force,
            dry_run=args.dry_run
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[✓] System-1 Evidence Triage completed for chat '{chat_id}':")
            print(f"    Evaluated:  {res['total_evaluated']} items (Model: {res.get('model', 'default')})")
            print(f"    Routed:     {res['routed_count']} items to chapters")
            print(f"    Discarded:  {res['discarded_count']} items (noise / low-salience)")
            if res.get("chapter_breakdown"):
                print("    Chapter breakdown:")
                for ch, cnt in sorted(res["chapter_breakdown"].items()):
                    print(f"      • {ch}: {cnt} items")
            print(f"    Latency:    {res['elapsed_seconds']}s | Cost: ${res['total_cost_usd']:.5f}")
            if res.get("dry_run"):
                print("    [!] Dry-run mode: database was not modified.")
            else:
                print("    [✓] Database updated and committed.")
        sys.exit(0)

    if args.batch_route:
        res = batch_route_evidence(conn, chat_id, args.batch_route)
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[✓] Batch routed {res['total_routed']} evidence items for chat '{chat_id}':")
            for ch, cnt in sorted(res.get("chapter_breakdown", {}).items()):
                print(f"    • {ch}: {cnt} items")
        sys.exit(0)

    if args.evidence_for_target:
        items = get_evidence_for_target(conn, chat_id, args.evidence_for_target)
        conn.close()
        if args.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
        else:
            print_evidence_for_target(items, args.evidence_for_target)
        sys.exit(0)

    if args.propose_custom_section:
        if not args.section_title or not args.section_rationale or not args.section_filename:
            print("[!] Error: --propose-custom-section requires --section-title, --section-rationale, and --section-filename.")
            conn.close()
            sys.exit(1)
        res = propose_custom_section(
            conn, chat_id,
            title=args.section_title,
            rationale=args.section_rationale,
            target_filename=args.section_filename,
            section_type=args.section_type,
            suggested_target_agent=args.target_agent or "chapter-drafter",
            associated_threads=args.section_threads,
            key_quotes=args.section_quotes
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[✓] Proposed custom report section #{res['section_id']}: \"{res['section_title']}\"")
            print(f"    Target File:  reports/<subject>_sections/{res['target_filename']}")
            print(f"    Drafter:      {res['suggested_target_agent']}")
            print(f"    Rationale:    {res['rationale']}")
        sys.exit(0)

    if args.list_custom_sections:
        print_custom_sections(conn, chat_id)
        conn.close()
        sys.exit(0)

    if args.export_evidence:
        evidence = export_audited_evidence(conn, chat_id, tag=args.tag, category=args.category)
        conn.close()
        if args.json:
            print(json.dumps(evidence, indent=2, ensure_ascii=False))
        else:
            print_audited_evidence(
                evidence, chat_id,
                tag=args.tag, category=args.category,
                part=args.part, part_size=args.part_size, show_all=args.all
            )
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

    if args.next:
        print_next_thread(conn, chat_id)
        conn.close()
        sys.exit(0)

    if args.check:
        code = check_gate(conn, chat_id)
        conn.close()
        sys.exit(code)

    stats = get_thread_checklist_stats(conn, chat_id)
    conn.close()
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print_thread_status(stats)


if __name__ == "__main__":
    main()
