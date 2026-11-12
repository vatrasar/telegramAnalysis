"""Query Engine package for Telegram Multi-Chat Analysis.

Provides quantitative overview (Phase 1), qualitative psychological retrieval (Phase 2),
FTS5 full-text search, semantic search, entity disambiguation, and watchdog gates.
"""

from .formatters import (
    format_duration,
    format_message_text,
    SAFE_MESSAGE_CHAR_LIMIT,
)
from .catalog import (
    get_chats_catalog,
    resolve_chat,
    print_chats_catalog,
)
from .stats_overview import (
    get_stats,
    print_stats,
    get_timeline,
    print_timeline,
)
from .silence_gaps import (
    get_silence_gaps,
    print_silence_gaps,
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
from .entities import (
    ensure_entities_tables,
    get_chat_entities,
    print_chat_entities,
    register_entity,
    get_chat_descriptors,
    print_chat_descriptors,
    audit_descriptor,
    print_descriptor_audit,
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
from .watchdog_scan import (
    run_sequential_watchdog_scan,
)
from .cli_args import build_parser
from .cli import run_query_cli, main

__all__ = [
    "format_duration",
    "format_message_text",
    "SAFE_MESSAGE_CHAR_LIMIT",
    "get_chats_catalog",
    "resolve_chat",
    "print_chats_catalog",
    "get_stats",
    "print_stats",
    "get_silence_gaps",
    "print_silence_gaps",
    "get_timeline",
    "print_timeline",
    "get_burning_days",
    "print_burning_days",
    "get_intensive_threads",
    "print_intensive_threads",
    "get_triaged_threads",
    "print_triaged_threads",
    "get_search_messages",
    "print_search_messages",
    "get_search_threads_fts",
    "print_search_threads_fts",
    "get_semantic_batch_results",
    "print_semantic_results",
    "get_thread",
    "print_thread",
    "get_thread_slice",
    "print_thread_slice",
    "get_single_message",
    "print_single_message",
    "get_thread_snippets",
    "print_thread_snippets",
    "get_quote_chain",
    "print_quote_chain",
    "get_chronological_around",
    "print_chronological_around",
    "ensure_entities_tables",
    "get_chat_entities",
    "print_chat_entities",
    "register_entity",
    "get_chat_descriptors",
    "print_chat_descriptors",
    "audit_descriptor",
    "print_descriptor_audit",
    "run_watchdog_check",
    "print_watchdog_result",
    "run_anomaly_check",
    "print_anomaly_check_result",
    "skip_watchdog_thread",
    "print_watchdog_status",
    "check_watchdog_gate",
    "run_sequential_watchdog_scan",
    "build_parser",
    "run_query_cli",
    "main",
]
