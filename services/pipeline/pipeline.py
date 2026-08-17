"""Assembly and execution of the LlamaIndex document ingestion pipeline."""

import logging
from typing import Sequence
import urllib.parse

from llama_index.core import Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import TransformComponent, BaseNode
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from config import settings
from services.pipeline.gdoc_parser import GoogleDocJsonParser
from services.pipeline.legacy_sync import LegacyTableSync
from services.llm_extract import LetterMetadataExtractor

logger = logging.getLogger(__name__)

def _get_pgvector_store() -> PGVectorStore:
    """Initialize the PGVectorStore from application settings.
    
    Parses the DATABASE_URL to extract connection parameters for psycopg2.
    Requires the pgvector extension to be enabled on the database.
    """
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        
    parsed = urllib.parse.urlparse(url)
    
    # We use psycopg2 directly or let PGVectorStore handle the connection details
    return PGVectorStore.from_params(
        database=parsed.path.lstrip("/"),
        host=parsed.hostname or "localhost",
        password=parsed.password or "",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        table_name="letter_nodes",
        embed_dim=768,  # For nomic-embed-text
    )

class NodeTextFormatter(TransformComponent):
    """Restructure node metadata and set node.text to the subject for embedding.

    After this component runs, each node will have:
    - ``node.text`` = subject (used by downstream OllamaEmbedding for vector search)
    - ``node.metadata`` containing ONLY: ref_no, date, subject, full_letter,
      tab_title, source_doc_id
    """

    def __call__(self, nodes: Sequence[BaseNode], **kwargs) -> Sequence[BaseNode]:
        for node in nodes:
            ref_no = node.metadata.get("ref_no") or ""
            date = node.metadata.get("date") or ""
            subject = node.metadata.get("subject") or ""
            full_letter = node.metadata.get("full_markdown") or node.text
            tab_title = node.metadata.get("tab_title") or ""
            source_doc_id = node.metadata.get("source_doc_id") or ""

            # Rebuild metadata with only the allowed keys
            node.metadata = {
                "ref_no": ref_no,
                "date": date,
                "subject": subject,
                "full_letter": full_letter,
                "tab_title": tab_title,
                "source_doc_id": source_doc_id,
            }

            # Set node.text to subject — this is what gets embedded for vector search
            node.text = subject

        return nodes

    async def acall(self, nodes: Sequence[BaseNode], **kwargs) -> Sequence[BaseNode]:
        return self.__call__(nodes, **kwargs)

def build_pipeline() -> IngestionPipeline:
    """Assemble the LlamaIndex IngestionPipeline.
    
    Components (in execution order):
    1. GoogleDocJsonParser: Converts raw JSON to Markdown.
    2. LetterMetadataExtractor: Uses Qwen 7B to extract structured data,
       populates node.metadata, and rewrites node.text to description.
    3. LegacyTableSync: Syncs to Signature, Designation, and LetterTypeMemory
       tables (generates description-based embeddings for LetterTypeMemory).
    4. NodeTextFormatter: Restructures metadata and sets node.text to subject
       for downstream vector embedding.
    5. OllamaEmbedding: Generates 768-dim vectors from subject (node.text).
    6. PGVectorStore: Inserts into the PostgreSQL letter_nodes table.
    """
    try:
        vector_store = _get_pgvector_store()
    except Exception as e:
        logger.error(f"Failed to initialize PGVectorStore: {e}")
        # Return a pipeline without vector_store for testing/fallback if needed
        # Or just re-raise. We'll re-raise for now.
        raise

    embed_model = OllamaEmbedding(
        model_name=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )

    return IngestionPipeline(
        transformations=[
            GoogleDocJsonParser(),
            LetterMetadataExtractor(),
            LegacyTableSync(),
            NodeTextFormatter(),
            embed_model,
        ],
        vector_store=vector_store,
    )

async def run_ingestion(documents: Sequence[Document]) -> list:
    """Run the ingestion pipeline on a set of documents asynchronously.
    
    Args:
        documents: A list of LlamaIndex Document objects. The `text` property
                   must contain the raw JSON string from DocumentTransformer.
                   
    Returns:
        The processed nodes that were successfully ingested.
    """
    pipeline = build_pipeline()
    logger.info(f"Starting ingestion pipeline for {len(documents)} documents...")
    
    # The pipeline handles the entire flow, including writing to Postgres
    nodes = await pipeline.arun(documents=documents)
    
    logger.info(f"Ingestion pipeline completed. Ingested {len(nodes)} nodes.")
    return nodes
