"""Agent token analytics, thread redundancy auditor, and search method benchmark suite."""

from .transcript_parser import (
    resolve_conversation_path,
    get_latest_conversation,
    search_conversations_by_role,
    parse_raw_transcript,
    extract_subagent_conversations,
    parse_agent_tree
)

from .token_profiler import (
    compute_node_metrics,
    aggregate_tree_profile,
    calculate_cost,
    calculate_duration_seconds,
    format_duration
)

from .formatter import (
    render_ascii_tree,
    render_summary_card,
    render_timeline,
    generate_markdown_report,
    format_tokens
)

from .benchmark import (
    run_comparative_benchmark,
    render_benchmark_table,
    run_lexical_regex_search
)

from .thread_redundancy import (
    analyze_thread_redundancy,
    render_thread_redundancy_table
)

__all__ = [
    "resolve_conversation_path",
    "get_latest_conversation",
    "search_conversations_by_role",
    "parse_raw_transcript",
    "extract_subagent_conversations",
    "parse_agent_tree",
    "compute_node_metrics",
    "aggregate_tree_profile",
    "calculate_cost",
    "calculate_duration_seconds",
    "format_duration",
    "render_ascii_tree",
    "render_summary_card",
    "render_timeline",
    "generate_markdown_report",
    "format_tokens",
    "run_comparative_benchmark",
    "render_benchmark_table",
    "run_lexical_regex_search",
    "analyze_thread_redundancy",
    "render_thread_redundancy_table"
]
