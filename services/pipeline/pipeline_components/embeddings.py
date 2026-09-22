"""Embed text with a local Ollama embedding model via LlamaIndex.

Uses LlamaIndex's ``OllamaEmbedding`` and ``TextNode`` to generate
768-dim vectors — replacing the previous raw ``/api/embed`` HTTP calls.
"""

from llama_index.core.schema import TextNode

from services.pipeline.pipeline_components.embed_model import get_embed_model


async def embed_text(text: str) -> list[float]:
    """Embed text with the local Ollama embedding model (768-dim vector)."""
    node = TextNode(text=text[:8000])
    return await get_embed_model().aget_text_embedding(node.get_content())
