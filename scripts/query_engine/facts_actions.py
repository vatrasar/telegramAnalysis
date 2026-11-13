"""CLI action handlers for discovered facts and inspected threads."""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, Optional

from .facts_engine import (
    record_discovered_fact,
    record_facts_batch,
    get_discovered_facts,
    print_discovered_facts,
    mark_thread_inspected,
    get_inspected_threads,
    is_thread_inspected,
    print_inspected_threads,
    normalize_category_and_sphere,
)


def handle_facts_and_inspection_actions(
    args: Any,
    batch_config: Dict[str, Any],
    resolved_chat_id: Optional[str],
    resolved_chat_name: Optional[str],
) -> bool:
    """Handle fact recording/retrieval and thread inspection CLI flags. Returns True if handled."""
    # 1. Check if thread is inspected: --is-inspected <thread_id>
    if getattr(args, "is_inspected", None):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --is-inspected.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        inspected, data = is_thread_inspected(conn, resolved_chat_id, args.is_inspected)
        conn.close()
        if args.json:
            print(json.dumps({"thread_id": args.is_inspected, "inspected": inspected, "data": data}, indent=2, ensure_ascii=False))
        else:
            if inspected and data:
                print(f"\n[✓] Thread '{args.is_inspected}' HAS BEEN INSPECTED.")
                print(f"    Inspector: {data['inspected_by']} | Stage: {data['stage']} | Date: {data['inspected_at'][:16]}")
                if data['covered_spheres']:
                    print(f"    Covered Spheres: {data['covered_spheres']}")
                if data['findings_summary']:
                    print(f"    Findings: {data['findings_summary']}\n")
            else:
                print(f"\n[✗] Thread '{args.is_inspected}' HAS NOT been inspected yet.\n")
        return True

    # 2. Mark thread inspected: --mark-inspected <thread_id>
    if getattr(args, "mark_inspected", None):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --mark-inspected.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        res = mark_thread_inspected(
            conn=conn,
            chat_id=resolved_chat_id,
            thread_id=args.mark_inspected,
            inspected_by=getattr(args, "inspected_by", None) or "agent",
            stage=getattr(args, "stage", None) or "entity_discovery",
            findings=getattr(args, "findings", None) or "",
            tags=getattr(args, "thematic_tags", None) or getattr(args, "tags", None) or "",
            spheres=getattr(args, "covered_spheres", None) or getattr(args, "sphere", None) or "",
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[✓] Thread '{args.mark_inspected}' marked as INSPECTED for chat {resolved_chat_id}.")
            print(f"    Inspector: {res['inspected_by']} | Stage: {res['stage']}")
            if res['covered_spheres']:
                print(f"    Covered Spheres: {res['covered_spheres']}")
            print()
        return True

    # 3. View inspected threads catalog: --inspected-threads
    if getattr(args, "inspected_threads", False) or batch_config.get("inspected_threads", False):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --inspected-threads.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        threads = get_inspected_threads(
            conn=conn,
            chat_id=resolved_chat_id,
            sphere_id=getattr(args, "sphere", None),
            tag=getattr(args, "tag", None),
        )
        conn.close()
        if args.json:
            print(json.dumps({"inspected_threads": threads}, indent=2, ensure_ascii=False))
        else:
            print_inspected_threads(threads, resolved_chat_id)
        return True

    # 4. Record single fact: --record-fact
    if getattr(args, "record_fact", False):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --record-fact.")
            sys.exit(1)
        summary = getattr(args, "fact_summary", None) or getattr(args, "findings", None)
        quote = getattr(args, "quote", None) or getattr(args, "quotes", None)
        if not summary or not quote:
            print("[!] Error: --record-fact requires both --fact-summary (or --findings) and --quote (or --quotes).")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        res = record_discovered_fact(
            conn=conn,
            chat_id=resolved_chat_id,
            fact_summary=summary,
            verbatim_quote=quote,
            category=getattr(args, "category", None),
            sphere_id=getattr(args, "sphere", None),
            thread_id=getattr(args, "fact_thread", None) or getattr(args, "thread_id", None),
            anchor_msg_id=getattr(args, "anchor_id", None),
            target_agent=getattr(args, "target_agent", None),
            discovered_by=getattr(args, "discovered_by", None) or "agent",
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[✓] Recorded Fact #{res['fact_id']} for chat {resolved_chat_id}.")
            print(f"    Category: {res['category']} | Sphere: {res['sphere_id'] or 'None'} | Target: {res['target_agent']}")
            print(f"    Summary: {res['fact_summary']}\n")
        return True

    # 5. Record batch facts: --record-facts-batch <file_or_string>
    if getattr(args, "record_facts_batch", None):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --record-facts-batch.")
            sys.exit(1)
        raw_val = args.record_facts_batch.strip()
        facts_list = []
        if os.path.exists(raw_val):
            with open(raw_val, "r", encoding="utf-8") as f:
                facts_list = json.load(f)
        else:
            try:
                facts_list = json.loads(raw_val)
            except Exception as e:
                print(f"[!] Error parsing JSON string for --record-facts-batch: {e}")
                sys.exit(1)

        if not isinstance(facts_list, list):
            print("[!] Error: --record-facts-batch must be a JSON array of fact objects.")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        res = record_facts_batch(
            conn=conn,
            chat_id=resolved_chat_id,
            facts=facts_list,
            discovered_by=getattr(args, "discovered_by", None),
            default_thread_id=getattr(args, "fact_thread", None),
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[✓] Recorded {res['recorded_count']} facts into evidence repository for chat {resolved_chat_id}.\n")
        return True

    # 6. Retrieve facts for specific sphere: --facts-for-sphere <sphere_or_category>
    if getattr(args, "facts_for_sphere", None):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --facts-for-sphere.")
            sys.exit(1)
        canon_cat, canon_sph = normalize_category_and_sphere(args.facts_for_sphere, args.facts_for_sphere)
        conn = sqlite3.connect(args.db)
        facts = get_discovered_facts(
            conn=conn,
            chat_id=resolved_chat_id,
            category=canon_cat if not canon_sph else None,
            sphere_id=canon_sph,
        )
        conn.close()
        if args.json:
            print(json.dumps({"sphere": canon_sph, "category": canon_cat, "facts": facts}, indent=2, ensure_ascii=False))
        else:
            lbl = f"Sphere {canon_sph}" if canon_sph else f"Category {canon_cat}"
            print_discovered_facts(facts, filter_label=lbl)
        return True

    # 7. View all discovered facts: --facts
    if getattr(args, "facts", False) or batch_config.get("facts", False):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --facts.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        facts = get_discovered_facts(
            conn=conn,
            chat_id=resolved_chat_id,
            category=getattr(args, "category", None),
            sphere_id=getattr(args, "sphere", None),
            target_agent=getattr(args, "target_agent", None),
            thread_id=getattr(args, "fact_thread", None),
        )
        conn.close()
        if args.json:
            print(json.dumps({"facts": facts}, indent=2, ensure_ascii=False))
        else:
            print_discovered_facts(facts, filter_label=f"Chat {resolved_chat_id}")
        return True

    return False
