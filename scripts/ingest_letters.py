"""Ingest letters from the tabs of a single Google Doc into pgvector memory.

Usage:
    uv run python -m scripts.ingest_letters [DOCUMENT_ID] [--force]

DOCUMENT_ID falls back to LETTERS_DOC_ID in .env. 

This script has been refactored to use the new LlamaIndex-native IngestionPipeline.
It reads tabs from the Google Doc, feeds them into the pipeline. The pipeline
automatically handles:
- Parsing and LLM metadata extraction
- Syncing to legacy tables (LetterTypeMemory, Designation, Signature)
- Embedding and storing in the vector database
"""

import asyncio
import sys
from typing import Iterator

from llama_index.core import Document

from config import settings
from services.docs_services.docs_service import GoogleDocsService
from services.docs_services.document_transformer import DocumentTransformer
from services.pipeline.pipeline import run_ingestion


def _flatten_tabs(tabs: list[dict]) -> Iterator[dict]:
    """Recursively yield every tab (including nested child tabs)."""
    for tab in tabs:
        yield tab
        yield from _flatten_tabs(tab.get("childTabs", []))


def _build_source_id(doc_id: str, tab_id: str) -> str:
    """Canonical composite key used to deduplicate ingested tabs."""
    return f"{doc_id}#{tab_id}"


async def _fetch_doc_tabs(
    doc_id: str,
) -> tuple[str, list[dict], GoogleDocsService]:
    """Fetch a Google Doc and return (doc_title, flattened_tabs, service)."""
    service = GoogleDocsService(
        settings, settings.google_access_token, settings.google_refresh_token
    )
    doc = await asyncio.to_thread(service.fetch_document, doc_id, True)
    tabs = list(_flatten_tabs(doc.get("tabs", [])))
    title = doc.get("title", doc_id)
    return title, tabs, service




async def main() -> None:
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    doc_id = args[0] if args else settings.letters_doc_id
    if not doc_id:
        sys.exit("Pass a Google Doc ID or set LETTERS_DOC_ID in .env")
    if not (settings.google_access_token and settings.google_refresh_token):
        sys.exit("GOOGLE_ACCESS_TOKEN / GOOGLE_REFRESH_TOKEN not set in .env")

    doc_title, tabs, docs_service = await _fetch_doc_tabs(doc_id)
    print(f"Found {len(tabs)} tabs in '{doc_title}'")

    # Prepare LlamaIndex Documents
    documents = []
    for tab in tabs:
        props = tab.get("tabProperties", {})
        tab_id = props.get("tabId", "")
        title = props.get("title") or "Untitled letter"
        
        document_tab = tab.get("documentTab", {})
        payload_json = DocumentTransformer.transform_to_payload(document_tab)
        
        if payload_json.strip() in ("", "[]"):
            continue
            
        doc = Document(
            text=payload_json,
            metadata={
                "source_doc_id": _build_source_id(doc_id, tab_id),
                "tab_title": title
            }
        )
        documents.append(doc)

    print(f"Prepared {len(documents)} documents for ingestion.")

    # Pipeline handles everything: parse, extract, sync legacy tables, embed, store
    try:
        nodes = await run_ingestion(documents)
    except Exception as e:
        print(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"Done: ingested {len(nodes)} nodes (legacy table sync handled by pipeline).")

if __name__ == "__main__":
    asyncio.run(main())
