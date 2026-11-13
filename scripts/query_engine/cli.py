"""CLI orchestration and batch query dispatcher for query_chat."""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, List, Optional

from .cli_args import build_parser
from .cli_actions import (
    handle_entity_actions,
    handle_watchdog_actions,
    handle_checklist_actions,
)
from .facts_actions import handle_facts_and_inspection_actions
from .catalog import get_chats_catalog, resolve_chat, print_chats_catalog
from .stats_overview import (
    get_stats,
    print_stats,
    get_silence_gaps,
    print_silence_gaps,
    get_timeline,
    print_timeline,
)
from .stats_triage import (
    get_burning_days,
    print_burning_days,
    get_intensive_threads,
    print_intensive_threads,
    get_triaged_threads,
    print_triaged_threads,
)
from .search import (
    get_search_messages,
    print_search_messages,
    get_search_threads_fts,
    print_search_threads_fts,
    get_semantic_batch_results,
    print_semantic_results,
)
from .inspector_thread import (
    get_thread,
    print_thread,
    get_thread_slice,
    print_thread_slice,
    get_single_message,
    print_single_message,
)
from .inspector_context import (
    get_thread_snippets,
    print_thread_snippets,
    get_quote_chain,
    print_quote_chain,
    get_chronological_around,
    print_chronological_around,
)


def _extract_list(cli_arg: Optional[List[Any]], config_key: str, batch_config: Dict[str, Any]) -> List[Any]:
    items = list(cli_arg or [])
    from_cfg = batch_config.get(config_key)
    if isinstance(from_cfg, list):
        items.extend(from_cfg)
    elif isinstance(from_cfg, (str, int)):
        items.append(from_cfg)
    return items


def run_query_cli(argv: Optional[List[str]] = None) -> None:
    """Main CLI entrypoint for query_chat."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Support batch directives from JSON file or JSON string
    batch_config: Dict[str, Any] = {}
    if args.batch_json:
        if os.path.exists(args.batch_json):
            with open(args.batch_json, "r", encoding="utf-8") as f:
                batch_config = json.load(f)
        else:
            try:
                batch_config = json.loads(args.batch_json)
            except Exception as e:
                print(f"[!] Error parsing --batch-json: {e}")
                sys.exit(1)

    if not os.path.exists(args.db):
        print(f"[!] Database file '{args.db}' not found.")
        print("    Build it first using: python3 project/scripts/db_builder.py rozmowy/*.json -o chat.db")
        sys.exit(1)

    # Catalog command
    if args.list_chats or batch_config.get("list_chats", False):
        catalog = get_chats_catalog(args.db)
        if args.json:
            print(json.dumps({"chats": catalog}, indent=2, ensure_ascii=False))
        else:
            print_chats_catalog(catalog)
        return

    # Resolve chat filter
    filter_chat_arg = args.chat or batch_config.get("chat")
    resolved_chat_id, resolved_chat_name = resolve_chat(args.db, filter_chat_arg)

    # Auto-resolve chat if exactly one chat exists in DB
    if not resolved_chat_id:
        catalog = get_chats_catalog(args.db)
        if len(catalog) == 1:
            resolved_chat_id = catalog[0]["chat_id"]
            resolved_chat_name = catalog[0]["chat_name"]

    # Delegate early-exit operations
    if handle_entity_actions(args, batch_config, resolved_chat_id, resolved_chat_name):
        return

    if handle_facts_and_inspection_actions(args, batch_config, resolved_chat_id, resolved_chat_name):
        return

    if handle_watchdog_actions(args, resolved_chat_id):
        return

    if handle_checklist_actions(args, batch_config, resolved_chat_id):
        return

    # Merge CLI flags with batch config
    run_stats = args.stats or batch_config.get("stats", False)
    run_gaps = args.gaps or batch_config.get("gaps", False)
    run_timeline = args.timeline or batch_config.get("timeline", False)
    run_burning = args.burning_days or batch_config.get("burning_days", False)
    run_intensive = args.intensive_threads or batch_config.get("intensive_threads", False)
    run_anomalies_only = args.anomalies_only or batch_config.get("anomalies_only", False)
    run_peaks = args.emotional_peaks or batch_config.get("emotional_peaks", False)
    peak_type = args.peak_type or batch_config.get("peak_type")
    run_advice = args.advice_seeking or batch_config.get("advice_seeking", False)
    run_triaged = args.triaged_threads or run_anomalies_only or run_peaks or run_advice or batch_config.get("triaged_threads", False)
    run_triage_status = args.triage_status or batch_config.get("triage_status", False)
    min_salience = float(batch_config.get("min_salience", args.min_salience))
    triage_category = batch_config.get("triage_category", args.triage_category)
    min_hours = batch_config.get("min_hours", args.min_hours)
    min_days = batch_config.get("min_days", getattr(args, "min_days", None))
    if min_days is not None:
        min_hours = float(min_days) * 24.0
    else:
        min_hours = float(min_hours)
    min_words = batch_config.get("min_words", args.min_words)
    min_messages = batch_config.get("min_messages", args.min_messages)
    limit = batch_config.get("limit", args.limit)
    window = batch_config.get("window", args.window)

    search_queries = _extract_list(args.search, "search", batch_config)
    search_thread_queries = _extract_list(args.search_threads, "search_threads", batch_config)
    thread_ids = [str(x) for x in _extract_list(args.thread, "thread", batch_config)]
    thread_snippets = [str(x) for x in _extract_list(args.thread_snippets, "thread_snippets", batch_config)]
    explicit_mentions = [str(x) for x in _extract_list(args.mentions, "mentions", batch_config)]
    msg_ids = [int(x) for x in _extract_list(args.msg, "msg", batch_config)]
    from_msgs = [int(x) for x in _extract_list(args.from_msg, "from_msg", batch_config)]
    chains = [int(x) for x in _extract_list(args.chain, "chain", batch_config)]
    around_msgs = [int(x) for x in _extract_list(args.around, "around", batch_config)]
    semantic_queries = [str(x) for x in _extract_list(args.semantic, "semantic", batch_config)]
    sender_filter = args.sender or batch_config.get("sender")

    has_actions = any([
        run_stats, run_gaps, run_timeline, run_burning, run_intensive,
        run_triaged, run_triage_status,
        search_queries, search_thread_queries, thread_ids, thread_snippets, msg_ids,
        from_msgs, chains, around_msgs, semantic_queries
    ])

    if not has_actions:
        parser.print_help()
        sys.exit(0)

    aggregated: Dict[str, Any] = {}
    if resolved_chat_id:
        aggregated["filter_chat"] = {"chat_id": resolved_chat_id, "chat_name": resolved_chat_name}

    # 1. Quantitative Stats
    if run_stats:
        stats_data = get_stats(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["stats"] = stats_data
        else:
            print_stats(stats_data)

    # 2. Silence Gaps
    if run_gaps:
        gaps_data = get_silence_gaps(args.db, min_hours=min_hours, chat_id=resolved_chat_id)
        if args.json:
            aggregated["silence_gaps"] = gaps_data
        else:
            print_silence_gaps(gaps_data)

    # 3. Monthly Timeline
    if run_timeline:
        timeline_data = get_timeline(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["timeline"] = timeline_data
        else:
            print_timeline(timeline_data)

    # 4. Burning Days
    if run_burning:
        burning_data = get_burning_days(args.db, chat_id=resolved_chat_id)
        if args.json:
            aggregated["burning_days"] = burning_data
        else:
            print_burning_days(burning_data)

    # 5. Intensive Substantive Threads
    if run_intensive:
        intensive_data = get_intensive_threads(
            args.db, min_words=min_words, min_messages=min_messages, limit=limit, chat_id=resolved_chat_id
        )
        if args.json:
            aggregated["intensive_threads"] = intensive_data
        else:
            print_intensive_threads(intensive_data)

    # 5b. System-1 Triaged Threads (Jev Qualified)
    if run_triage_status:
        try:
            from triage_threads import print_reduction_report, init_triage_table
            t_conn = sqlite3.connect(args.db)
            init_triage_table(t_conn)
            print_reduction_report(t_conn, chat_id=resolved_chat_id)
            t_conn.close()
        except ImportError:
            print("[!] Could not import print_reduction_report from triage_threads.")
        except Exception as e:
            print(f"[!] Error displaying triage status: {e}")

    if run_triaged:
        triaged_data = get_triaged_threads(
            args.db, limit=limit, chat_id=resolved_chat_id, min_salience=min_salience, category=triage_category,
            anomalies_only=run_anomalies_only,
            emotional_peaks_only=run_peaks,
            peak_type=peak_type,
            advice_seeking_only=run_advice
        )
        if args.json:
            aggregated["triaged_threads"] = triaged_data
        else:
            print_triaged_threads(triaged_data)

    # 6. Keyword Search (Individual Messages)
    if search_queries:
        search_results: Dict[str, Any] = {}
        for q in search_queries:
            msgs = get_search_messages(args.db, q, limit=limit, chat_id=resolved_chat_id, sender=sender_filter)
            if args.json:
                search_results[q] = msgs
            else:
                print_search_messages(q, msgs)
        if args.json:
            aggregated["search_messages"] = search_results

    # 7. Keyword Search (Full Threads)
    if search_thread_queries:
        st_results: Dict[str, Any] = {}
        for q in search_thread_queries:
            threads = get_search_threads_fts(args.db, q, limit=limit, chat_id=resolved_chat_id)
            if args.json:
                st_results[q] = threads
            else:
                print_search_threads_fts(q, threads)
        if args.json:
            aggregated["search_threads"] = st_results

    # 8. Retrieve Full Threads (or Summaries only)
    if thread_ids:
        thread_results: Dict[str, Any] = {}
        for t_id in thread_ids:
            t_obj = get_thread(args.db, t_id, chat_id=resolved_chat_id)
            if t_obj:
                if args.json:
                    if getattr(args, "summary_only", False):
                        summary_obj = {k: v for k, v in t_obj.items() if k not in ("messages", "dialogue_text")}
                        thread_results[t_id] = summary_obj
                    else:
                        thread_results[t_id] = t_obj
                else:
                    print_thread(t_obj, summary_only=getattr(args, "summary_only", False))
            else:
                if args.json:
                    thread_results[t_id] = None
                else:
                    print(f"\n[!] Thread/Message '{t_id}' not found.")
        if args.json:
            aggregated["threads"] = thread_results

    # 8b. Inspect Single Messages (with pagination / full display)
    if msg_ids:
        msg_results: Dict[str, Any] = {}
        for m_id in msg_ids:
            m_obj = get_single_message(args.db, m_id, chat_id=resolved_chat_id)
            if m_obj:
                if args.json:
                    msg_results[str(m_id)] = m_obj
                else:
                    print_single_message(m_obj, part=args.part, part_size=args.part_size, show_all=args.all)
            else:
                if args.json:
                    msg_results[str(m_id)] = None
                else:
                    print(f"\n[!] Message #{m_id} not found.")
        if args.json:
            aggregated["messages"] = msg_results

    # 9. Retrieve Thread Slices
    if from_msgs:
        slice_results: Dict[str, Any] = {}
        for m_id in from_msgs:
            s_obj = get_thread_slice(args.db, m_id, limit=limit, window_before=window, chat_id=resolved_chat_id)
            if s_obj:
                if args.json:
                    slice_results[str(m_id)] = s_obj
                else:
                    print_thread_slice(s_obj)
            else:
                if args.json:
                    slice_results[str(m_id)] = None
                else:
                    print(f"\n[!] Message #{m_id} not found.")
        if args.json:
            aggregated["thread_slices"] = slice_results

    # 9b. Retrieve Focused Thread Snippets around candidate entities
    if thread_snippets:
        snippet_window = window if window > 0 else 4
        snippet_results: Dict[str, Any] = {}
        for ts_id in thread_snippets:
            snip_obj = get_thread_snippets(args.db, ts_id, mentions=explicit_mentions, window=snippet_window, chat_id=resolved_chat_id)
            if snip_obj:
                if args.json:
                    snippet_results[str(ts_id)] = snip_obj
                else:
                    print_thread_snippets(snip_obj)
            else:
                if args.json:
                    snippet_results[str(ts_id)] = None
                else:
                    print(f"\n[!] Thread '{ts_id}' not found.")
        if args.json:
            aggregated["thread_snippets"] = snippet_results

    # 10. Trace Causal Quote Chains
    if chains:
        chain_results: Dict[str, Any] = {}
        for c_id in chains:
            chain_obj = get_quote_chain(args.db, c_id, chat_id=resolved_chat_id)
            if chain_obj:
                if args.json:
                    chain_results[str(c_id)] = chain_obj
                else:
                    print_quote_chain(chain_obj)
            else:
                if args.json:
                    chain_results[str(c_id)] = None
                else:
                    print(f"\n[!] Message #{c_id} not found.")
        if args.json:
            aggregated["quote_chains"] = chain_results

    # 11. Retrieve Chronological Window Across Thread Boundaries (N-5 ... N+5 Audit)
    if around_msgs:
        around_window = window if window > 0 else (limit if limit != 10 else 5)
        around_results: Dict[str, Any] = {}
        for a_id in around_msgs:
            a_obj = get_chronological_around(args.db, a_id, window=around_window, chat_id=resolved_chat_id)
            if a_obj:
                if args.json:
                    around_results[str(a_id)] = a_obj
                else:
                    print_chronological_around(a_obj)
            else:
                if args.json:
                    around_results[str(a_id)] = None
                else:
                    print(f"\n[!] Message #{a_id} not found.")
        if args.json:
            aggregated["chronological_around"] = around_results

    # 12. Batch Semantic Search
    if semantic_queries:
        sem_res = get_semantic_batch_results(args.db, semantic_queries, top_k=limit, chat_id=resolved_chat_id)
        if args.json:
            aggregated["semantic_search"] = sem_res
        else:
            for q, results in sem_res.items():
                print_semantic_results(q, results)

    # Output structured JSON if requested
    if args.json:
        print(json.dumps(aggregated, indent=2, ensure_ascii=False))


def main() -> None:
    """CLI entrypoint alias."""
    run_query_cli()
