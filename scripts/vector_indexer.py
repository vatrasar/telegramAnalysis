#!/usr/bin/env python3
"""Thread Vector Indexer with OpenRouter & Local Embedding Support (Multi-Chat Aware).

Embeds conversation threads and computes cosine similarity for psychological concept retrieval.

Supported modes:
1. OpenRouter / OpenAI API: Uses standard library urllib (zero dependencies needed).
2. Local Sentence-Transformers: Runs on local GPU (RTX 4060) or CPU.
3. Zero-dependency Fallback: SQLite FTS5 BM25 search.
"""

import os
import sys
import argparse

# Ensure project/scripts directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import load_config  # noqa: F401
from vector_engine import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENROUTER_ENDPOINT,
    is_local_ml_available,
    serialize_vector,
    deserialize_vector,
    dot_product,
    fetch_openrouter_embeddings,
    init_vector_table,
    index_threads,
    search_semantic_batch,
    search_semantic,
)


def main():
    parser = argparse.ArgumentParser(
        description="Embed conversation threads for semantic psychological search (multi-chat aware)."
    )
    parser.add_argument("--db", default="chat.db", help="Path to SQLite database")
    parser.add_argument("--index", action="store_true", help="Run indexing on threads")
    parser.add_argument("--chat", "-C", type=str, help="Filter indexing or search to a specific chat (id or name)")
    parser.add_argument("--force", action="store_true", help="Force re-indexing of already embedded threads")
    parser.add_argument(
        "--concurrency", "-c", type=int, help="Number of concurrent API workers for embedding batches (default: 4)"
    )
    parser.add_argument("--search", type=str, help="Semantic search query")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--model", type=str, help="Override model name")
    args = parser.parse_args()

    if args.index:
        index_threads(
            args.db,
            model_override=args.model,
            chat_filter=args.chat,
            force=args.force,
            concurrency_override=args.concurrency
        )
    elif args.search:
        results = search_semantic(args.db, args.search, top_k=args.top_k, chat_filter=args.chat)
        print(f"\n--- Top {len(results)} Semantic Matches for: '{args.search}' ---")
        for i, res in enumerate(results, 1):
            c_label = res.get("chat_name", res.get("chat_id"))
            print(f"\n[{i}] Thread: {res['thread_id']} | Chat: {c_label} | Date: {res['start_date'][:10]} | Score: {res['score']}")
            print(f"Participants: {res['participants']}")
            print(res["dialogue_text"])
            print("-" * 50)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
