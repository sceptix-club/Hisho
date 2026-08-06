import httpx
from typing import Any

from config import settings

async def call_ollama_api(endpoint: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    """
    Helper function to make API calls to the local Ollama instance.
    
    Args:
        endpoint: The API endpoint (e.g., '/api/chat', '/api/embed').
        payload: The JSON payload to send in the request body.
        timeout: The timeout for the request in seconds.
        
    Returns:
        The JSON response from the Ollama API.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
