"""CLI presentation and action routing for entity staging and disambiguation."""

import sys
import json
from typing import Any, Optional

from .staging_entities import (
    stage_entity,
    stage_entities_batch,
    get_pending_staging_entities,
    approve_staging_entity,
    merge_staging_entity,
    reject_staging_entity,
    record_distinct_pair,
)


def handle_staging_cli_actions(
    args: Any,
    resolved_chat_id: Optional[str],
    resolved_chat_name: Optional[str]
) -> bool:
    """Handle CLI flags for candidate entity staging and supervisor review."""
    if not resolved_chat_id:
        return False

    if getattr(args, "stage_entity", None):
        res = stage_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            name=args.stage_entity,
            role=getattr(args, "role", None),
            desc=getattr(args, "desc", None),
            thread_id=getattr(args, "staging_thread", None),
            proposed_by=getattr(args, "inspected_by", None) or "entity-investigator"
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[✓] Staged candidate entity [#{res.get('staging_id')}] '{args.stage_entity}' for supervisor review.")
        return True

    if getattr(args, "stage_entities_batch", None):
        res = stage_entities_batch(
            db_path=args.db,
            chat_id=resolved_chat_id,
            raw_payload=args.stage_entities_batch,
            thread_id=getattr(args, "staging_thread", None),
            proposed_by=getattr(args, "inspected_by", None) or "entity-investigator"
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[✓] Staged {res.get('staged_count', 0)} candidate entities for supervisor review.")
        return True

    if getattr(args, "pending_entities", False):
        pending = get_pending_staging_entities(args.db, resolved_chat_id)
        if args.json:
            print(json.dumps({"pending_entities": pending, "count": len(pending)}, indent=2, ensure_ascii=False))
        else:
            print(f"\n" + "=" * 80)
            print(f"📋 PENDING CANDIDATE ENTITIES FOR SUPERVISOR REVIEW [Chat: {resolved_chat_name or resolved_chat_id}]")
            print(f"   Total Pending: {len(pending)}")
            print("=" * 80)
            if not pending:
                print("   (No pending candidate entities in staging. All proposals reviewed.)")
            for p in pending:
                t_str = f" [Thread: {p['source_thread_id']}]" if p['source_thread_id'] else ""
                print(f"  [#{p['staging_id']}] {p['proposed_name']} | Role: {p['proposed_role'] or 'N/A'}{t_str}")
                if p['context_notes']:
                    print(f"      Notes: {p['context_notes']}")
                if p['anchors']:
                    print(f"      Anchors: {p['anchors']}")
            print("=" * 80 + "\n")
        return True

    if getattr(args, "approve_entity", None) is not None:
        res = approve_staging_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            staging_id=args.approve_entity,
            canonical_name=getattr(args, "canonical_name", None),
            role=getattr(args, "role", None),
            desc=getattr(args, "desc", None),
            is_ex=getattr(args, "ex", False),
            is_romantic=getattr(args, "romantic", False)
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if "error" in res:
                print(f"[!] Error: {res['error']}")
            else:
                print(f"[✓] {res.get('resolution')}")
        return True

    if getattr(args, "merge_entity", None) is not None:
        if not getattr(args, "into_entity", None):
            print("[!] Error: --merge-entity requires --into-entity '<Target_Name>'")
            sys.exit(1)
        res = merge_staging_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            staging_id=args.merge_entity,
            into_entity=args.into_entity,
            reason=getattr(args, "reason", None)
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if "error" in res:
                print(f"[!] Error: {res['error']}")
            else:
                print(f"[✓] {res.get('resolution')}")
        return True

    if getattr(args, "reject_entity", None) is not None:
        if not getattr(args, "reason", None):
            print("[!] Error: --reject-entity requires an explicit --reason '<reason>'")
            sys.exit(1)
        res = reject_staging_entity(
            db_path=args.db,
            chat_id=resolved_chat_id,
            staging_id=args.reject_entity,
            reason=args.reason
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if "error" in res:
                print(f"[!] Error: {res['error']}")
            else:
                print(f"[✓] {res.get('resolution')}")
        return True

    if getattr(args, "record_distinct_pair", None):
        pair = args.record_distinct_pair
        reason = getattr(args, "reason", "")
        if not reason:
            print("[!] Error: --record-distinct-pair requires an explicit --reason '<notes & evidence anchors>'")
            sys.exit(1)
        res = record_distinct_pair(
            db_path=args.db,
            chat_id=resolved_chat_id,
            entity_a=pair[0],
            entity_b=pair[1],
            reason=reason
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if "error" in res:
                print(f"[!] Error: {res['error']}")
            else:
                print(f"[✓] Recorded distinct pair '{res['entity_1']}' and '{res['entity_2']}'. Negative boundaries added.")
        return True

    return False
