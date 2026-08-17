"""Embed text with a local Ollama embedding model via LlamaIndex.

Uses LlamaIndex's ``OllamaEmbedding`` and ``TextNode`` to generate
768-dim vectors — replacing the previous raw ``/api/embed`` HTTP calls.
"""

import asyncio

from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.schema import TextNode

from config import settings


_embed_model = OllamaEmbedding(
    model_name=settings.embedding_model,
    base_url=settings.ollama_base_url,
)


async def embed_text(text: str) -> list[float]:
    """Embed text with the local Ollama embedding model (768-dim vector).

    Wraps only the provided text into a LlamaIndex TextNode and generates
    the embedding vector for it.
    """
    node = TextNode(text=text[:8000])
    embedding = await _embed_model.aget_text_embedding(node.get_content())
    node.embedding = embedding
    return embedding
