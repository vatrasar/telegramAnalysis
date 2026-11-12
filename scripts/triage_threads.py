#!/usr/bin/env python3
"""
System-1 Dialogue Thread Triage Engine CLI Entrypoint.
Applies fast, typed System-1 evaluation via OpenRouter to screen ALL conversation
threads in the SQLite database (chat.db).
Supports both OpenRouter Decision Models and standard Chat Completions models.
"""

import os
import sys
import sqlite3
import argparse

# Ensure local script packages are resolvable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import load_config
from common.db import get_default_db_path, connect_db
from triage_engine import (
    init_triage_table,
    call_openrouter_decisions,
    call_openrouter_chat_completions,
    evaluate_single_thread,
    verify_unregistered_entities_decider,
    verify_secondary_anomaly_decider,
    call_openrouter_summary,
    call_openrouter_extraction,
    print_reduction_report,
    run_triage,
    run_enrichment,
)

DEFAULT_DB_PATH = get_default_db_path()

__all__ = [
    "DEFAULT_DB_PATH",
    "load_config",
    "init_triage_table",
    "call_openrouter_decisions",
    "call_openrouter_chat_completions",
    "evaluate_single_thread",
    "verify_unregistered_entities_decider",
    "verify_secondary_anomaly_decider",
    "call_openrouter_summary",
    "call_openrouter_extraction",
    "print_reduction_report",
    "run_triage",
    "run_enrichment",
]


def main():
    parser = argparse.ArgumentParser(description="System-1 Dialogue Thread Triage Engine")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of threads to triage (useful for quick pilot test)")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already triaged threads")
    parser.add_argument("--concurrency", "-c", type=int, help="Number of concurrent API workers (default: 4)")
    parser.add_argument("--threshold", "-t", type=float, help="Override salience score threshold for escalation")
    parser.add_argument("--model", "-m", help="Override triage model name")
    parser.add_argument("--chat-id", help="Filter by specific chat ID")
    parser.add_argument("--status", action="store_true", help="Print existing triage and reduction report without running API")
    parser.add_argument("--enrich", action="store_true", help="Batch run Scaledown summaries and entity extractions on salient threads")
    parser.add_argument("--summarize-only", action="store_true", help="Generate summaries only for salient threads")
    parser.add_argument("--extract-only", action="store_true", help="Extract candidate entities only for salient threads")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[ERROR] Database file not found at: {args.db}")
        return 1

    if args.status:
        conn = connect_db(args.db)
        init_triage_table(conn)
        print_reduction_report(conn, chat_id=args.chat_id)
        conn.close()
        return 0

    if args.enrich or args.summarize_only or args.extract_only:
        return run_enrichment(
            db_path=args.db,
            limit=args.limit,
            force=args.force,
            concurrency_override=args.concurrency,
            chat_id=args.chat_id,
            do_summary=not args.extract_only,
            do_extraction=not args.summarize_only
        )

    return run_triage(
        db_path=args.db,
        limit=args.limit,
        force=args.force,
        concurrency_override=args.concurrency,
        threshold_override=args.threshold,
        model_override=args.model,
        chat_id=args.chat_id
    )


if __name__ == "__main__":
    sys.exit(main())
