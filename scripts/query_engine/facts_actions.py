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
    export_chapter_evidence_package,
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
                print(f"\n[✓] Thread '{args.is_inspected}' HAS BEEN AUDITED (Coverage: {data.get('coverage', 'full').upper()}).")
                print(f"    Inspector: {data['inspected_by']} | Stage: {data['stage']} | Date: {data['inspected_at'][:16]}")
                if data.get('entities_detected'):
                    print(f"    Entities Detected: {data['entities_detected']}")
                if data.get('unresolved_pronouns'):
                    print(f"    Unresolved / 'he/she' Clues: {data['unresolved_pronouns']}")
                if data.get('covered_spheres'):
                    print(f"    Covered Spheres: {data['covered_spheres']}")
                if data.get('findings_summary'):
                    print(f"    Findings: {data['findings_summary']}\n")
            else:
                print(f"\n[✗] Thread '{args.is_inspected}' HAS NOT been inspected yet.\n")
        return True

    # 2. Mark thread inspected / Record thread audit: --record-thread-audit or --mark-inspected <thread_id>
    target_audit_tid = getattr(args, "record_thread_audit", None) or getattr(args, "mark_inspected", None)
    if target_audit_tid:
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for thread audit.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        ent_val = getattr(args, "entities_str", None) or getattr(args, "identified_str", None) or ""
        unres_val = getattr(args, "unresolved", None) or ""
        cov_val = getattr(args, "coverage", None) or "full"
        res = mark_thread_inspected(
            conn=conn,
            chat_id=resolved_chat_id,
            thread_id=target_audit_tid,
            inspected_by=getattr(args, "inspected_by", None) or "entity-investigator",
            stage=getattr(args, "stage", None) or "entity_discovery",
            findings=getattr(args, "findings", None) or "",
            tags=getattr(args, "thematic_tags", None) or getattr(args, "tags", None) or "",
            spheres=getattr(args, "covered_spheres", None) or getattr(args, "sphere", None) or "",
            coverage=cov_val,
            entities_detected=ent_val,
            unresolved_pronouns=unres_val,
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n[✓] Thread '{target_audit_tid}' AUDIT CACHED for chat {resolved_chat_id}.")
            print(f"    Inspector: {res['inspected_by']} | Stage: {res['stage']} | Coverage: {res['coverage'].upper()}")
            if res.get('entities_detected'):
                print(f"    Entities: {res['entities_detected']}")
            if res.get('unresolved_pronouns'):
                print(f"    Unresolved / 'he/she' Clues: {res['unresolved_pronouns']}")
            if res.get('covered_spheres'):
                print(f"    Covered Spheres: {res['covered_spheres']}")
            if getattr(args, "findings", None):
                print(f"    Findings: {getattr(args, 'findings', None)}")
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
        
        quotes_input: List[Any] = []
        raw_quotes = getattr(args, "quote", None) or getattr(args, "quotes", None)
        if isinstance(raw_quotes, list):
            quotes_input.extend(raw_quotes)
        elif isinstance(raw_quotes, str) and raw_quotes.strip():
            quotes_input.append(raw_quotes.strip())

        raw_json_quotes = getattr(args, "quotes_json", None)
        if raw_json_quotes:
            try:
                parsed_q = json.loads(raw_json_quotes)
                if isinstance(parsed_q, list):
                    quotes_input.extend(parsed_q)
            except Exception as e:
                print(f"[!] Error parsing --quotes-json: {e}")
                sys.exit(1)

        if not summary or not quotes_input:
            print("[!] Error: --record-fact requires both --fact-summary (or --findings) and at least one --quote (or --quotes-json).")
            sys.exit(1)

        conn = sqlite3.connect(args.db)
        res = record_discovered_fact(
            conn=conn,
            chat_id=resolved_chat_id,
            fact_summary=summary,
            quotes=quotes_input,
            category=getattr(args, "category", None),
            sphere_id=getattr(args, "sphere", None),
            thread_id=getattr(args, "fact_thread", None) or getattr(args, "thread_id", None),
            anchor_msg_id=getattr(args, "anchor_id", None),
            target_agent=getattr(args, "target_agent", None),
            discovered_by=getattr(args, "discovered_by", None) or "agent",
            subject=getattr(args, "subject", None),
            fact_id=getattr(args, "fact_id", None),
            corroborate_with_system1=not getattr(args, "no_corroborate", False),
            default_role=getattr(args, "quote_role", "core_evidence"),
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if res.get("status") == "corroborated":
                print(f"\n[✓] Corroborated existing Fact #{res['fact_id']} for chat {resolved_chat_id}.")
                print(f"    Summary: {res.get('fact_summary')}")
                print(f"    Attached {res.get('quotes_added', 0)} new quotes to existing fact. Total input: {res.get('total_quotes_input', 0)}\n")
            else:
                print(f"\n[✓] Recorded new Fact #{res['fact_id']} for chat {resolved_chat_id} ({res.get('quotes_count', 1)} quotes).")
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
            default_subject=getattr(args, "subject", None),
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
            subject=getattr(args, "subject", None),
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
            subject=getattr(args, "subject", None),
        )
        conn.close()
        if args.json:
            print(json.dumps({"facts": facts}, indent=2, ensure_ascii=False))
        else:
            print_discovered_facts(facts, filter_label=f"Chat {resolved_chat_id}")
        return True

    # 8. Export structured chapter evidence package: --export-chapter-evidence <chapter>
    if getattr(args, "export_chapter_evidence", None):
        if not resolved_chat_id:
            print("[!] Error: Please specify chat using -C <chat_id> for --export-chapter-evidence.")
            sys.exit(1)
        conn = sqlite3.connect(args.db)
        res = export_chapter_evidence_package(
            conn=conn,
            chat_id=resolved_chat_id,
            target_chapter=args.export_chapter_evidence,
            sphere_id=getattr(args, "sphere", None)
        )
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("\n" + "=" * 80)
            print(f"📦 CHAPTER EVIDENCE PACKAGE: '{args.export_chapter_evidence}' (Total: {res['total_facts']} facts)")
            print("=" * 80)
            for f in res["facts"]:
                quotes_count = len(f.get("quotes", []))
                sph_tag = f" [Sphere {f['sphere_id']}]" if f.get("sphere_id") else ""
                print(f"\n[Fact #{f['fact_id']}]{sph_tag} Category: {f['category']} | Quotes: {quotes_count}")
                print(f"  Summary: {f['fact_summary']}")
                for q in f.get("quotes", []):
                    role_lbl = f"[{q['evidence_role']}]" if q.get("evidence_role") else ""
                    print(f"  ↳ {role_lbl} [#{q['msg_id']}] {q['verbatim_quote']}")
            print("=" * 80 + "\n")
        return True

    # 9. Index facts into vector store: --index-facts
    if getattr(args, "index_facts", False):
        try:
            from vector_engine import index_facts
            ok = index_facts(args.db, chat_filter=resolved_chat_id, force=getattr(args, "force", False))
            if ok:
                print(f"[✓] Successfully indexed discovered facts into vector store for chat {resolved_chat_id or 'all'}.")
            else:
                print("[!] Fact indexing completed or skipped (no facts to index or provider unavailable).")
        except Exception as e:
            print(f"[!] Fact indexing error: {e}")
        return True

    # 9. Semantic search on discovered facts: --semantic-facts <query>
    if getattr(args, "semantic_facts", None):
        try:
            from vector_engine import search_semantic_facts
            top_k = getattr(args, "limit", 5) or 5
            sph = getattr(args, "sphere", None)
            subj = getattr(args, "subject", None)
            res = search_semantic_facts(
                args.db,
                args.semantic_facts,
                top_k=top_k,
                chat_filter=resolved_chat_id,
                sphere_filter=sph,
                subject_filter=subj,
                min_score=getattr(args, "min_score", None),
            )
            if args.json:
                print(json.dumps({"query": args.semantic_facts, "results": res}, indent=2, ensure_ascii=False))
            else:
                print("=" * 80)
                print(f"🔍 SEMANTIC FACTS SEARCH: '{args.semantic_facts}' (Top {len(res)} matches)")
                print("=" * 80)
                if not res:
                    print("  No semantically matching facts found.")
                else:
                    for i, r in enumerate(res, 1):
                        score = r.get("score", 0.0)
                        f_id = r.get("fact_id")
                        cat = r.get("category", "general")
                        sph_lbl = f" | Sphere: {r.get('sphere_id')}" if r.get('sphere_id') else ""
                        subj_lbl = f" | Subject: {r.get('subject')}" if r.get('subject') else ""
                        anchor = f" | Anchor #{r.get('anchor_msg_id')}" if r.get('anchor_msg_id') else ""
                        print(f"  [{i}] Fact #{f_id} (Score: {score:.4f}) | Category: {cat}{sph_lbl}{subj_lbl}{anchor}")
                        print(f"      Summary: {r.get('fact_summary')}")
                        if r.get("verbatim_quote"):
                            print(f"      Quote:   {r.get('verbatim_quote')}")
                        print("-" * 80)
        except Exception as e:
            print(f"[!] Semantic fact search error: {e}")
        return True

    return False
