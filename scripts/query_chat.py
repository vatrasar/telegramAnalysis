#!/usr/bin/env python3
"""Telegram Multi-Chat Analysis Query CLI.

Provides quantitative mining (Phase 1) and qualitative psychological retrieval (Phase 2)
over preprocessed SQLite and vector chat data with multi-chat support.

Supports:
- Multi-chat filtering via --chat <chat_id_or_name> and chat catalog via --list-chats
- Multi-query simultaneous execution (e.g. --stats --gaps --timeline in one call)
- Repeated batch queries (--semantic "q1" --semantic "q2" or -s "term1" -s "term2")
- Batch JSON execution via --batch-json <file_or_string>
- Structured JSON output mode via --json (agent-friendly token-efficient output)
"""

import os
import sys

# Ensure project/scripts directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query_engine import (
    format_duration,
    format_message_text,
    SAFE_MESSAGE_CHAR_LIMIT,
    get_chats_catalog,
    resolve_chat,
    print_chats_catalog,
    get_stats,
    print_stats,
    get_silence_gaps,
    print_silence_gaps,
    get_timeline,
    print_timeline,
    get_burning_days,
    print_burning_days,
    get_intensive_threads,
    print_intensive_threads,
    get_triaged_threads,
    print_triaged_threads,
    get_search_messages,
    print_search_messages,
    get_search_threads_fts,
    print_search_threads_fts,
    get_semantic_batch_results,
    print_semantic_results,
    get_thread,
    print_thread,
    get_thread_slice,
    print_thread_slice,
    get_single_message,
    print_single_message,
    get_thread_snippets,
    print_thread_snippets,
    get_quote_chain,
    print_quote_chain,
    get_chronological_around,
    print_chronological_around,
    ensure_entities_tables,
    get_chat_entities,
    print_chat_entities,
    register_entity,
    get_chat_descriptors,
    print_chat_descriptors,
    audit_descriptor,
    print_descriptor_audit,
    run_watchdog_check,
    print_watchdog_result,
    run_anomaly_check,
    print_anomaly_check_result,
    skip_watchdog_thread,
    print_watchdog_status,
    check_watchdog_gate,
    run_sequential_watchdog_scan,
    build_parser,
    run_query_cli,
    main,
)

if __name__ == "__main__":
    main()
