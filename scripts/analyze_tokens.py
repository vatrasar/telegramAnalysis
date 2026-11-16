#!/usr/bin/env python3
"""CLI Entrypoint for Agent Token Analytics and Search Method Benchmarking."""

import os
import sys
import json
import argparse

# Add scripts directory to path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from agent_analytics import (
    get_latest_conversation,
    search_conversations_by_role,
    parse_agent_tree,
    aggregate_tree_profile,
    render_ascii_tree,
    render_summary_card,
    render_timeline,
    generate_markdown_report,
    run_comparative_benchmark,
    render_benchmark_table,
    analyze_thread_redundancy,
    render_thread_redundancy_table
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Agent Token Analytics & Entity Search Method Benchmark Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze latest active conversation:
  python3 project/scripts/analyze_tokens.py --latest

  # Analyze specific agent session with subagents tree:
  python3 project/scripts/analyze_tokens.py --conv 9aaa2706-52ba-4f0f-8798-c85cd758a37c --tree

  # Search past sessions by subagent role:
  python3 project/scripts/analyze_tokens.py --search-role "entity-supervisor"

  # Run comparative benchmark across entity search methods:
  python3 project/scripts/analyze_tokens.py --benchmark -C c_1027532109
        """
    )

    parser.add_argument("--conv", "-c", type=str, help="Conversation UUID or path to transcript.jsonl")
    parser.add_argument("--latest", action="store_true", help="Analyze most recently active conversation")
    parser.add_argument("--search-role", type=str, help="Search past conversations by subagent role / type")
    parser.add_argument("--tree", "-t", action="store_true", help="Display full agent/subagent hierarchy tree")
    parser.add_argument("--threads", "--redundancy", action="store_true", help="Display thread re-read & cross-agent redundancy audit")
    parser.add_argument("--timeline", action="store_true", help="Display turn-by-turn timeline table")
    parser.add_argument("--limit-turns", type=int, default=30, help="Number of turns to show in timeline (default: 30)")
    parser.add_argument("--md", action="store_true", help="Output in Markdown format")
    parser.add_argument("--json", action="store_true", help="Output raw structured JSON metrics")
    parser.add_argument("--cost-model", type=str, default="flash", help="Pricing model tier (flash, flash_lite, pro)")

    # Benchmark arguments
    parser.add_argument("--benchmark", "-b", action="store_true", help="Run comparative benchmark on entity search methods")
    parser.add_argument("-C", "--chat-id", type=str, default="c_1027532109", help="Target chat ID for benchmarking")
    parser.add_argument("-d", "--db", type=str, default=None, help="Path to chat.db (default: ../chat.db)")
    parser.add_argument("--sample", type=int, default=None, help="Sample limit of threads for benchmarking")

    return parser.parse_args()


def resolve_db_path(explicit_db: str = None) -> str:
    """Resolve path to chat.db complying with stateless agent principle."""
    if explicit_db and os.path.exists(explicit_db):
        return explicit_db
    # Standard location: parent workspace root
    parent_db = os.path.abspath(os.path.join(SCRIPTS_DIR, "..", "..", "chat.db"))
    if os.path.exists(parent_db):
        return parent_db
    # Fallback to local
    local_db = os.path.abspath(os.path.join(SCRIPTS_DIR, "..", "chat.db"))
    if os.path.exists(local_db):
        return local_db
    return "chat.db"


def main():
    args = parse_args()

    # 1. Search conversations by subagent role
    if args.search_role:
        print(f"\n🔍 Searching conversations invoking subagent role: '{args.search_role}'...\n")
        results = search_conversations_by_role(args.search_role)
        if not results:
            print("No matching conversations found.")
            sys.exit(0)

        print(f"{'Conversation ID':<38} {'Modified':<20} {'Steps':<7} {'Tokens':<10} {'Roles / Types'}")
        print("-" * 100)
        for r in results:
            roles_str = ", ".join(r["roles"] or r["types"])
            print(f"{r['conversation_id']:<38} {r['modified_at'][:19]:<20} {r['steps']:<7} {r['total_tokens']:<10,} {roles_str[:40]}")
        print("\nUse: python3 project/scripts/analyze_tokens.py --conv <ID> --tree to inspect full details.\n")
        sys.exit(0)

    # 2. Comparative Benchmark Mode
    if args.benchmark:
        db_path = resolve_db_path(args.db)
        print(f"\n🚀 Running Comparative Entity Search Benchmark on Database: {db_path} [Chat: {args.chat_id}]...")
        try:
            bench_results = run_comparative_benchmark(
                db_path=db_path,
                chat_id=args.chat_id,
                sample_threads=args.sample
            )
            if args.json:
                print(json.dumps(bench_results, indent=2, ensure_ascii=False))
            else:
                print(render_benchmark_table(bench_results))
        except Exception as e:
            print(f"Benchmark error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # 3. Conversation Token Analysis Mode
    target_conv = args.conv
    if not target_conv and args.latest:
        target_conv = get_latest_conversation()
        if not target_conv:
            print("Could not locate any active conversations in brain directory.", file=sys.stderr)
            sys.exit(1)

    if not target_conv:
        # Default to latest if no argument passed
        target_conv = get_latest_conversation()

    if not target_conv:
        print("Please specify a conversation ID using --conv <ID> or use --latest.", file=sys.stderr)
        sys.exit(1)

    # Parse and aggregate
    tree = parse_agent_tree(target_conv)
    if tree.get("error"):
        print(f"Error parsing conversation '{target_conv}': {tree.get('error')}", file=sys.stderr)
        sys.exit(1)

    aggregate_tree_profile(tree, cost_model=args.cost_model)
    redundancy_metrics = analyze_thread_redundancy(tree)
    tree["thread_redundancy"] = redundancy_metrics

    if args.json:
        # Output clean JSON
        print(json.dumps(tree, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.md:
        print(generate_markdown_report(tree))
        if args.threads:
            print("\n```text\n" + render_thread_redundancy_table(redundancy_metrics) + "\n```")
        sys.exit(0)

    # Standard ASCII output
    print("\n" + render_summary_card(tree))

    # Thread redundancy report (shown if explicitly requested or if high redundancy detected)
    if args.threads or (args.tree and redundancy_metrics.get("total_redundant_operations", 0) > 0):
        print("\n" + render_thread_redundancy_table(redundancy_metrics))

    if args.tree or tree.get("children"):
        print("\n🌳 AGENT & SUBAGENT HIERARCHY TREE:")
        print(render_ascii_tree(tree))
        print("=" * 84 + "\n")

    if args.timeline:
        print(render_timeline(tree, limit=args.limit_turns))


if __name__ == "__main__":
    main()
