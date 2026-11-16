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
]
