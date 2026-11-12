"""Dedicated handlers for early-exit CLI actions (entities, watchdogs, checklists)."""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, Optional

from .entities import (
    get_chat_entities,
    print_chat_entities,
    register_entity,
    get_chat_descriptors,
    print_chat_descriptors,
    audit_descriptor,
    print_descriptor_audit,
)
from .candidate_inspect import (
    get_candidate_entities_data,
    print_candidate_entities_summary,
)
from .conflation_audit import (
    run_conflation_audit,
    print_conflation_audit,
)
from .watchdog_api import (
    run_watchdog_check,
    print_watchdog_result,
    run_anomaly_check,
    print_anomaly_check_result,
    skip_watchdog_thread,
    print_watchdog_status,
    check_watchdog_gate,
)
from .watchdog_scan import run_sequential_watchdog_scan


def handle_entity_actions(args: Any, batch_config: Dict[str, Any], resolved_chat_id: Optional[str], resolved_chat_name: Optional[str]) -> bool:
    """Handle entity and descriptor registration/audit CLI flags. Returns True if handled."""
    if args.register_entity:
        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)
        is_ex = bool(args.ex)
        is_rom = True if args.romantic else (False if args.non_romantic else False)
        reg_res = register_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            name_or_alias=args.register_entity,
            verified_role=args.role,
            associated_descriptors=args.desc,
            is_ex_partner=is_ex,
            is_romantic=is_rom,
            confidence=args.confidence or "verified",
            first_msg_id=args.first_msg,
            notes=args.desc
        )
        if args.json:
            print(json.dumps(reg_res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[SUCCESS] Registered entity '{args.register_entity}' for chat {resolved_chat_id}.")
            entities = get_chat_entities(args.db, chat_id=resolved_chat_id)
            print_chat_entities(entities, chat_name=resolved_chat_name or resolved_chat_id)
        return True

    if args.entities or batch_config.get("entities", False):
        entities = get_chat_entities(args.db, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps({"entities": entities}, indent=2, ensure_ascii=False))
        else:
            print_chat_entities(entities, chat_name=resolved_chat_name)
        return True

    if args.descriptors or batch_config.get("descriptors", False):
        descriptors = get_chat_descriptors(args.db, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps({"descriptors": descriptors}, indent=2, ensure_ascii=False))
        else:
            print_chat_descriptors(descriptors, chat_name=resolved_chat_name)
        return True

    if args.audit_descriptor:
        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)
        audit_res = audit_descriptor(args.db, args.audit_descriptor, chat_id=resolved_chat_id)
        if args.json:
            print(json.dumps(audit_res, indent=2, ensure_ascii=False))
        else:
            print_descriptor_audit(audit_res)
        return True

    if args.candidates or batch_config.get("candidates", False):
        if not resolved_chat_id:
            print("[!] Error: Please specify target chat via -C <chat_id> for --candidates.")
            sys.exit(1)
        cdata = get_candidate_entities_data(args.db, resolved_chat_id)
        if args.json:
            print(json.dumps(cdata, indent=2, ensure_ascii=False))
        else:
            print_candidate_entities_summary(cdata, chat_name=resolved_chat_name)
        return True

    if args.conflation_audit or batch_config.get("conflation_audit", False):
        if not resolved_chat_id:
            print("[!] Error: Please specify target chat via -C <chat_id> for --conflation-audit.")
            sys.exit(1)
        caudit = run_conflation_audit(args.db, resolved_chat_id)
        if args.json:
            print(json.dumps(caudit, indent=2, ensure_ascii=False))
        else:
            print_conflation_audit(caudit)
        return True

    return False


def handle_watchdog_actions(args: Any, resolved_chat_id: Optional[str]) -> bool:
    """Handle watchdog adversarial checks and scan CLI flags. Returns True if handled."""
    if args.watchdog_check:
        watchdog_res = run_watchdog_check(
            db_path=args.db,
            thread_id=args.watchdog_check,
            chat_id=resolved_chat_id,
            explicit_known_names=args.known
        )
        if args.json:
            print(json.dumps(watchdog_res, indent=2, ensure_ascii=False))
        else:
            print_watchdog_result(watchdog_res)
        return True

    if args.anomaly_check:
        identified_list = args.identified or []
        anomaly_res = run_anomaly_check(
            db_path=args.db,
            thread_id=args.anomaly_check,
            chat_id=resolved_chat_id,
            identified=identified_list
        )
        if args.json:
            print(json.dumps(anomaly_res, indent=2, ensure_ascii=False))
        else:
            print_anomaly_check_result(anomaly_res)
        return True

    if args.watchdog_status:
        if not resolved_chat_id:
            print("[!] Error: Please specify target chat via -C <chat_id> for --watchdog-status.")
            sys.exit(1)
        print_watchdog_status(args.db, resolved_chat_id)
        return True

    if args.check_watchdog_gate:
        cid = resolved_chat_id or "global"
        gate_code = check_watchdog_gate(args.db, cid)
        sys.exit(gate_code)

    if args.skip_thread:
        skip_watchdog_thread(args.db, args.skip_thread, resolved_chat_id)
        return True

    if args.watchdog_scan:
        if not resolved_chat_id:
            print("[!] Error: Please specify target chat via -C <chat_id> for --watchdog-scan.")
            sys.exit(1)
        scan_res = run_sequential_watchdog_scan(
            db_path=args.db,
            chat_id=resolved_chat_id,
            limit=args.limit,
            reset=args.reset_watchdog_scan,
            sweep=bool(getattr(args, "sweep", False))
        )
        if args.json:
            print(json.dumps(scan_res, indent=2, ensure_ascii=False))
        return True

    return False


def handle_checklist_actions(args: Any, batch_config: Dict[str, Any], resolved_chat_id: Optional[str]) -> bool:
    """Handle life spheres and thread audit checklists CLI flags. Returns True if handled."""
    if args.waive_checklist:
        try:
            from checklist import waive_checklist
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from checklist import waive_checklist

        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        waived_count = waive_checklist(conn, resolved_chat_id, reason=args.reason)
        conn.close()
        if args.json:
            print(json.dumps({"action": "waive", "chat_id": resolved_chat_id, "waived_items": waived_count, "reason": args.reason}))
        else:
            print(f"[✓] Life spheres checklist WAIVED/DISABLED for chat '{resolved_chat_id}'.")
            print(f"    Reason: {args.reason}")
            print(f"    {waived_count} pending items marked as not_applicable. Full checklist audit is not required.")
        return True

    if args.checklist or batch_config.get("checklist", False):
        try:
            from checklist import get_checklist_stats, print_status_summary
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from checklist import get_checklist_stats, print_status_summary

        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        stats = get_checklist_stats(conn, resolved_chat_id)
        conn.close()
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print_status_summary(stats)
        return True

    if args.waive_threads_checklist:
        try:
            from thread_checklist import waive_thread_checklist
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from thread_checklist import waive_thread_checklist

        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        waived_count = waive_thread_checklist(conn, resolved_chat_id, reason=args.reason)
        conn.close()
        if args.json:
            print(json.dumps({"action": "waive_thread_checklist", "chat_id": resolved_chat_id, "waived_threads": waived_count, "reason": args.reason}))
        else:
            print(f"[✓] Thread audit checklist WAIVED/DISABLED for chat '{resolved_chat_id}'.")
            print(f"    Reason: {args.reason}")
            print(f"    {waived_count} pending threads marked as not_applicable. Full thread audit is not required.")
        return True

    if args.threads_checklist or batch_config.get("threads_checklist", False):
        try:
            from thread_checklist import get_thread_checklist_stats, print_thread_status
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from thread_checklist import get_thread_checklist_stats, print_thread_status

        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        stats = get_thread_checklist_stats(conn, resolved_chat_id)
        conn.close()
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print_thread_status(stats)
        return True

    if args.next_thread:
        try:
            from thread_checklist import print_next_thread
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from thread_checklist import print_next_thread

        if not resolved_chat_id:
            print("[!] Error: Multiple chats found in database. Please specify chat using -C <chat_id>.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        print_next_thread(conn, resolved_chat_id)
        conn.close()
        return True

    return False
