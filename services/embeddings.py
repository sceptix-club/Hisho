

from config import settings
from services.ollama_client import call_ollama_api


async def embed_text(text: str) -> list[float]:
    """Embed text with the local Ollama embedding model (768-dim vector)."""
    payload = {"model": settings.embedding_model, "input": text[:8000]}
    resp_data = await call_ollama_api("/api/embed", payload, timeout=60)
    return resp_data["embeddings"][0]
