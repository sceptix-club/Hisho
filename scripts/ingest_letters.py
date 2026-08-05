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
from db.models import LetterTypeMemory, Designation
from db.session import AsyncSessionLocal
from services.docs_services.docs_service import GoogleDocsService
from services.embeddings import embed_text
from services.llm_extract import (
    LetterExtractionOutput,
    extract_letter_metadata,
    identify_template_replacements_chunked,
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




async def _load_existing_memories(
    session: AsyncSession,
) -> dict[str, LetterTypeMemory]:
    """Return a dict of source_doc_id → LetterTypeMemory for skip checks."""
    result = await session.execute(select(LetterTypeMemory))
    return {ltm.source_doc_id: ltm for ltm in result.scalars()}


async def _load_existing_designations(
    session: AsyncSession,
) -> dict[str, Designation]:
    """Return a code→Designation dict for dedup."""
    result = await session.execute(select(Designation))
    return {d.code: d for d in result.scalars()}



def _update_memory_row(
    row: LetterTypeMemory,
    extraction: LetterExtractionOutput,
    embedding: list[float],
    template_url: str | None = None,
) -> None:
    """Overwrite an existing LetterTypeMemory row with fresh extraction."""
    row.type_name = extraction.type_name
    row.description = extraction.description
    row.approval_chain = [step.model_dump() for step in extraction.approval_chain]
    row.required_sections = extraction.required_sections
    row.embedding = embedding
    if template_url is not None:
        row.template_url = template_url


def _create_memory_row(
    doc_id: str,
    tab_id: str,
    source_id: str,
    extraction: LetterExtractionOutput,
    embedding: list[float],
    template_url: str | None = None,
) -> LetterTypeMemory:
    """Build a new LetterTypeMemory row from the extraction output."""
    return LetterTypeMemory(
        id=uuid.uuid4().hex,
        doc_id=doc_id,
        tab_id=tab_id,
        source_doc_id=source_id,
        type_name=extraction.type_name,
        description=extraction.description,
        approval_chain=[step.model_dump() for step in extraction.approval_chain],
        required_sections=extraction.required_sections,
        embedding=embedding,
        template_url=template_url,
    )


def _upsert_designations(
    session: AsyncSession,
    extraction: LetterExtractionOutput,
    existing_codes: dict[str, Designation],
) -> int:
    """Insert any new designations from the approval chain. Returns count added."""
    known_titles = {d.title for d in existing_codes.values()}
    count = 0
    for step in extraction.approval_chain:
        if step.designation_code in existing_codes:
            continue
        if step.designation_title in known_titles:
            continue
        desg = Designation(
            id=uuid.uuid4().hex,
            title=step.designation_title,
            code=step.designation_code,
        )
        session.add(desg)
        existing_codes[step.designation_code] = desg
        known_titles.add(step.designation_title)
        count += 1
    return count




async def _process_tab(
    session: AsyncSession,
    tab: dict,
    doc_id: str,
    force: bool,
    existing: dict[str, LetterTypeMemory],
    existing_codes: dict[str, Designation],
    template_url: str | None = None,
) -> tuple[str, int]:
    """Process a single tab: extract, embed, upsert.

    Template generation (copy + per-tab replacement) is handled separately
    by the caller. This function only handles metadata extraction, embedding,
    and DB persistence.

    Returns:
        (status, designations_added) where status is one of
        "added", "updated", or "skipped".
    """
    props = tab.get("tabProperties", {})
    tab_id = props.get("tabId", "")
    source_id = _build_source_id(doc_id, tab_id)

    row = existing.get(source_id)
    if row and not force:
        return "skipped", 0

    document_tab = tab.get("documentTab", {})
    text = GoogleDocsService.extract_text(document_tab)
    if not text:
        return "skipped", 0

    title = props.get("title") or "Untitled letter"
    print(f"  ⏳ Extracting metadata from '{title}' …")

    extraction = await extract_letter_metadata(text)
    embedding = await embed_text(extraction.description)

    if row:
        _update_memory_row(row, extraction, embedding, template_url=template_url)
        print(f"  ~ {title} → {extraction.type_name}")
        status = "updated"
    else:
        session.add(
            _create_memory_row(
                doc_id, tab_id, source_id, extraction, embedding,
                template_url=template_url,
            )
        )
        print(f"  + {title} → {extraction.type_name}")
        status = "added"

    desg_count = _upsert_designations(session, extraction, existing_codes)
    return status, desg_count


async def _generate_template_from_copy(
    docs_service: GoogleDocsService,
    copy_doc_id: str,
    copy_tabs: list[dict],
) -> None:
    """Iterate over all tabs in the copied document, chunk each tab's raw
    JSON structure, and use the chunked pipeline to identify replacements.

    Uses :func:`identify_template_replacements_chunked` which preserves
    document structure (tables, headings, headers/footers) so that small
    models like Qwen 7B can reliably identify placeholders.
    """
    for copy_tab in copy_tabs:
        props = copy_tab.get("tabProperties", {})
        tab_title = props.get("title") or "Untitled tab"
        tab_id = props.get("tabId", "")

        document_tab = copy_tab.get("documentTab", {})
        if not document_tab.get("body", {}).get("content"):
            print(f"    ⏭️  Skipping empty tab '{tab_title}'")
            continue

        print(f"    📝 Identifying template replacements for tab '{tab_title}' …")
        replacements = await identify_template_replacements_chunked(document_tab)
        print(f"       Found {len(replacements)} replacements")

        if replacements:
            await asyncio.to_thread(
                docs_service.apply_template_replacements,
                copy_doc_id,
                [r.model_dump() for r in replacements],
                tab_id,
            )
            print(f"✅ Replacements applied for tab '{tab_title}'")




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

    template_folder_id = await asyncio.to_thread(
        docs_service.ensure_folder, "Templates"
    )
    print(f"Using Templates folder (id={template_folder_id})")

    # --- Create a single copy of the original document ---
    print(f"📋 Copying original document '{doc_title}' …")
    template_doc = await asyncio.to_thread(
        docs_service.copy_document_to_folder,
        doc_id,
        f"Template - {doc_title}",
        template_folder_id,
    )
    copy_doc_id = template_doc["document_id"]
    template_url = template_doc["url"]
    print(f"✅ Copy created: {template_url}")

    # --- Fetch the copy's tabs and apply replacements per tab ---
    print(f"📄 Fetching copy's tabs …")
    copy_doc = await asyncio.to_thread(
        docs_service.fetch_document, copy_doc_id, True
    )
    copy_tabs = list(_flatten_tabs(copy_doc.get("tabs", [])))
    print(f"   Copy has {len(copy_tabs)} tabs")

    await _generate_template_from_copy(docs_service, copy_doc_id, copy_tabs)
    print(f"✅ Template generation complete: {template_url}")

    # --- Process each original tab for metadata extraction and DB upsert ---
    async with AsyncSessionLocal() as session:
        existing = await _load_existing_memories(session)
        existing_codes = await _load_existing_designations(session)

        added = updated = skipped = designations_added = 0

        for tab in tabs:
            print(f"  🔍 Processing tab: {tab.get('tabProperties', {}).get('title', 'unknown')}")
            status, desg_count = await _process_tab(
                session, tab, doc_id, force, existing, existing_codes,
                template_url=template_url,
            )
            if status == "added":
                added += 1
            elif status == "updated":
                updated += 1
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
