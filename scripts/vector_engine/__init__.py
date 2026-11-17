"""Vector Engine package for embedding generation and semantic similarity search."""

from .client import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENROUTER_ENDPOINT,
    is_local_ml_available,
    serialize_vector,
    deserialize_vector,
    dot_product,
    fetch_openrouter_embeddings,
)
from .indexer import (
    init_vector_table,
    index_threads,
    init_fact_vector_table,
    index_facts,
)
from .search import (
    search_semantic_batch,
    search_semantic,
    search_semantic_facts,
)
from .chunks import (
    init_chunk_vector_table,
    chunk_thread_messages,
    ensure_thread_chunks_embedded,
    resolve_thread_snippet,
)

__all__ = [
    "DEFAULT_LOCAL_MODEL",
    "DEFAULT_OPENROUTER_ENDPOINT",
    "is_local_ml_available",
    "serialize_vector",
    "deserialize_vector",
    "dot_product",
    "fetch_openrouter_embeddings",
    "init_vector_table",
    "index_threads",
    "init_fact_vector_table",
    "index_facts",
    "search_semantic_batch",
    "search_semantic",
    "search_semantic_facts",
    "init_chunk_vector_table",
    "chunk_thread_messages",
    "ensure_thread_chunks_embedded",
    "resolve_thread_snippet",
]
