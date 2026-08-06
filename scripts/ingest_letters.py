"""Ingest letters from the tabs of a single Google Doc into pgvector memory.

Usage:
    uv run python -m scripts.ingest_letters [DOCUMENT_ID] [--force]

DOCUMENT_ID falls back to LETTERS_DOC_ID in .env. Each tab in the document is
passed through a local LLM to extract structured metadata (type_name,
description, approval_chain, required_sections). The description is embedded
into a 768-dim vector and stored in ``letter_type_memory``; unique designations
from the approval chain are upserted into the ``designations`` table. Requires
GOOGLE_ACCESS_TOKEN / GOOGLE_REFRESH_TOKEN and a running Ollama with the
embedding model pulled (`ollama pull nomic-embed-text`) and the chat model
available. Safe to re-run: already-ingested tabs are skipped by
doc_id#tab_id. Pass --force to re-extract and re-embed existing tabs in
place (e.g. after an extractor change).
"""


import asyncio
import sys
import uuid
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import LetterTypeMemory, Designation, Signature
from db.session import AsyncSessionLocal
from services.docs_services.docs_service import GoogleDocsService
from services.docs_services.document_transformer import DocumentTransformer
from services.embeddings import embed_text
from services.llm_extract import (
    LetterExtractionOutput,
    extract_letter_metadata,
)




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




# _load_existing_memories removed because LetterTypeMemory no longer has source_doc_id


async def _load_existing_designations(
    session: AsyncSession,
) -> dict[str, Designation]:
    """Return a title→Designation dict for dedup."""
    result = await session.execute(select(Designation))
    return {d.title: d for d in result.scalars()}



def _create_memory_row(
    extraction: LetterExtractionOutput,
    embedding: list[float],
    template_url: str | None = None,
) -> LetterTypeMemory:
    """Build a new LetterTypeMemory row from the extraction output."""
    return LetterTypeMemory(
        id=uuid.uuid4().hex,
        letter_type=extraction.letter_type,
        primary_domain=extraction.primary_domain,
        description=extraction.description,
        approval_chain=[
            step.model_dump(exclude={"incumbent"}) 
            for step in extraction.approval_chain
        ],
        table_info=extraction.table_info.model_dump() if extraction.table_info else None,
        embedding=embedding,
        template_url=template_url,
    )


def _upsert_designations(
    session: AsyncSession,
    extraction: LetterExtractionOutput,
    existing_titles: dict[str, Designation],
) -> int:
    """Insert any new designations from the approval chain. Returns count added."""
    count = 0
    for step in extraction.approval_chain:
        if step.designation_title in existing_titles:
            continue
        desg = Designation(
            id=uuid.uuid4().hex,
            title=step.designation_title,
            incumbent=step.incumbent,
        )
        session.add(desg)
        existing_titles[step.designation_title] = desg
        count += 1
    return count




async def _process_tab(
    session: AsyncSession,
    tab: dict,
    doc_id: str,
    existing_codes: dict[str, Designation],
    template_url: str | None = None,
) -> tuple[str, int]:
    """Process a single tab: extract, embed, upsert.

    Returns:
        (status, designations_added) where status is "added" or "skipped".
    """
    props = tab.get("tabProperties", {})
    tab_id = props.get("tabId", "")
    source_id = _build_source_id(doc_id, tab_id)

    document_tab = tab.get("documentTab", {})
    payload_json = DocumentTransformer.transform_to_payload(document_tab)
    if payload_json.strip() in ("", "[]"):
        return "skipped", 0

    title = props.get("title") or "Untitled letter"
    print(f"  ⏳ Extracting metadata from '{title}' …")

    extraction = await extract_letter_metadata(payload_json)
    embedding = await embed_text(extraction.description)

    session.add(
        _create_memory_row(
            extraction, embedding,
            template_url=template_url,
        )
    )
    print(f"  + {title} → {extraction.letter_type} ({extraction.primary_domain})")
    status = "added"

    # Use signature images and signee names identified by the LLM and store them
    if extraction.signatures:
        valid_signatures = [sig for sig in extraction.signatures if sig.url]
        for sig in valid_signatures:
            session.add(Signature(
                id=uuid.uuid4().hex,
                source_doc_id=source_id,
                image_url=sig.url,
                name=sig.name,
            ))
        print(f"  📸 Found {len(extraction.signatures)} signature(s)")

    desg_count = _upsert_designations(session, extraction, existing_codes)
    return status, desg_count




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

    template_url = None
    
    # --- Process each original tab for metadata extraction and DB upsert ---
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        await session.execute(delete(LetterTypeMemory))
        await session.execute(delete(Signature))
        
        existing_codes = await _load_existing_designations(session)

        added = updated = skipped = designations_added = 0

        for tab in tabs:
            print(f"  🔍 Processing tab: {tab.get('tabProperties', {}).get('title', 'unknown')}")
            status, desg_count = await _process_tab(
                session, tab, doc_id, existing_codes,
                template_url=template_url,
            )
            if status == "added":
                added += 1
            else:
                skipped += 1
            designations_added += desg_count

        await session.commit()

    print(
        f"Done: {added} added, {updated} updated, {skipped} skipped, "
        f"{designations_added} new designations"
    )



if __name__ == "__main__":
    asyncio.run(main())
