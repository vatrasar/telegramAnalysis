#!/usr/bin/env python3
"""
Telegram Multi-Chat Database Builder & Thread Disentangler CLI Entrypoint.
Converts one or more Telegram desktop export JSON files into an analytical SQLite database
with conversation threads reconstructed via reply DAGs, anchor resolution,
and forward burst propagation (RAT-FBP).
"""

import os
import sys
import argparse

# Ensure local script packages are resolvable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.text import extract_text, parse_iso_date, compute_file_sha256
from db_engine import (
    BURST_THRESHOLD_SECONDS,
    INFERRED_RESPONSE_SECONDS,
    SESSION_GAP_SECONDS,
    LONG_SILENCE_SECONDS,
    MAX_THREAD_MESSAGES,
    derive_chat_id,
    create_schema,
    disentangle_threads,
    insert_chat_data,
    build_databases,
)

__all__ = [
    "BURST_THRESHOLD_SECONDS",
    "INFERRED_RESPONSE_SECONDS",
    "SESSION_GAP_SECONDS",
    "LONG_SILENCE_SECONDS",
    "MAX_THREAD_MESSAGES",
    "extract_text",
    "parse_iso_date",
    "compute_file_sha256",
    "derive_chat_id",
    "create_schema",
    "disentangle_threads",
    "insert_chat_data",
    "build_databases",
]


def main():
    parser = argparse.ArgumentParser(
        description="Build analytical SQLite DB from one or more Telegram chat exports (multi-chat support)."
    )
    parser.add_argument(
        "json_files",
        nargs="+",
        help="Path(s) to Telegram export JSON files or wildcards (e.g. rozmowy/*.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="chat.db",
        help="Output SQLite database path (default: chat.db)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean/recreate database from scratch, removing existing data"
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        help="Explicitly specify or override chat_id for imported file (single chat only)"
    )
    parser.add_argument(
        "--burst-threshold",
        type=int,
        default=BURST_THRESHOLD_SECONDS,
        help=f"Max gap in seconds for burst continuation by same sender (default: {BURST_THRESHOLD_SECONDS})"
    )
    parser.add_argument(
        "--inferred-gap",
        type=int,
        default=INFERRED_RESPONSE_SECONDS,
        help=f"Max gap in seconds for inferred reply between conversation turns (default: {INFERRED_RESPONSE_SECONDS})"
    )
    parser.add_argument(
        "--session-gap",
        type=int,
        default=SESSION_GAP_SECONDS,
        help=f"Min gap in seconds to partition into a new conversation session (default: {SESSION_GAP_SECONDS})"
    )
    parser.add_argument(
        "--max-thread-messages",
        type=int,
        default=MAX_THREAD_MESSAGES,
        help=f"Max messages per thread before splitting with parent-child linkage (default: {MAX_THREAD_MESSAGES})"
    )
    args = parser.parse_args()

    build_databases(
        input_patterns=args.json_files,
        db_path=args.output,
        clean=args.clean,
        chat_id_override=args.chat_id,
        burst_threshold=args.burst_threshold,
        inferred_gap=args.inferred_gap,
        session_gap=args.session_gap,
        max_thread_messages=args.max_thread_messages
    )


if __name__ == "__main__":
    main()
