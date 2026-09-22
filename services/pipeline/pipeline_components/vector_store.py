"""PGVectorStore construction from application settings."""

import urllib.parse

from llama_index.vector_stores.postgres import PGVectorStore

from config import settings

VECTOR_TABLE_NAME = "letter_nodes"


def get_pgvector_store() -> PGVectorStore:
    """Initialize the PGVectorStore from application settings.

    PGVectorStore uses psycopg2 (sync), so the asyncpg URL scheme is rewritten
    first.
    """
    # PGVectorStore connects synchronously; strip the async driver prefix
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")

    parsed = urllib.parse.urlparse(url)

    return PGVectorStore.from_params(
        database=parsed.path.lstrip("/"),
        host=parsed.hostname or "localhost",
        password=parsed.password or "",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        table_name=VECTOR_TABLE_NAME,
        embed_dim=768,  # For nomic-embed-text
    )
