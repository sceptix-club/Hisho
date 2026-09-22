"""Shared Ollama embedding model instance for the ingestion pipeline.

A single lazily-created ``OllamaEmbedding`` is reused by every pipeline
component (and any other consumer) instead of each module building its own.
"""

from __future__ import annotations

from llama_index.embeddings.ollama import OllamaEmbedding

from config import settings

_embed_model: OllamaEmbedding | None = None


def get_embed_model() -> OllamaEmbedding:
    """Return the shared ``OllamaEmbedding`` instance, creating it on first use."""
    global _embed_model
    if _embed_model is None:
        _embed_model = OllamaEmbedding(
            model_name=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )
    return _embed_model
