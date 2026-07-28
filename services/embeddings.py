import httpx

from config import settings


async def embed_text(text: str) -> list[float]:
    """Embed text with the local Ollama embedding model (768-dim vector)."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.embedding_model, "input": text[:8000]},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]
