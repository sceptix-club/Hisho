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

import logging
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
    identify_template_replacements,
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
) -> tuple[dict[str, Designation], set[str]]:
    """Return (code→Designation dict, set of known titles) for dedup."""
    result = await session.execute(select(Designation))
    by_code: dict[str, Designation] = {}
    known_titles: set[str] = set()
    for d in result.scalars():
        by_code[d.code] = d
        known_titles.add(d.title)
    return by_code, known_titles



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
    known_titles: set[str],
) -> int:
    """Insert any new designations from the approval chain. Returns count added."""
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
    known_titles: set[str],
    docs_service: GoogleDocsService,
    template_folder_id: str,
) -> tuple[str, int]:
    """Process a single tab: extract, embed, generate template, upsert.

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

    # --- Copy-and-replace template generation ---
    # Step 1: Create an exact copy of the original doc via Drive copy
    print(f"  📋 Copying original document for '{title}' …")
    template_doc = await asyncio.to_thread(
        docs_service.copy_document_to_folder,
        doc_id,
        f"Template - {extraction.type_name}",
        template_folder_id,
    )
    
    copy_doc_id = template_doc["document_id"]

    # Step 2: Delete all tabs except the one we're processing
    print(f"  🗑️  Removing extra tabs from copy …")
    await asyncio.to_thread(
        docs_service.delete_tabs_except,
        copy_doc_id,
        tab_id,
    )

    # Step 3: Fetch JSON of the copy and extract text from our tab
    print(f"  📄 Fetching JSON of the copy …")
    copy_doc = await asyncio.to_thread(
        docs_service.fetch_document, copy_doc_id, True
    )
    copy_tabs = list(_flatten_tabs(copy_doc.get("tabs", [])))
    copy_tab = next(
        (t for t in copy_tabs
         if t.get("tabProperties", {}).get("tabId") == tab_id),
        None,
    )
    copy_text = (
        GoogleDocsService.extract_text(copy_tab.get("documentTab", {}))
        if copy_tab
        else text  # fallback to original text if tab not found
    )

    print(f"  📝 Identifying template replacements for '{title}' …")
    replacements = await identify_template_replacements(copy_text)
    print(f"     Found {len(replacements)} replacements")

    # Step 5: Apply placeholder replacements on the copy
    await asyncio.to_thread(
        docs_service.apply_template_replacements,
        copy_doc_id,
        [r.model_dump() for r in replacements],
    )
    template_url = template_doc["url"]
    print(f"  ✅ Template created: {template_url}")


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

    desg_count = _upsert_designations(session, extraction, existing_codes, known_titles)
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

    template_folder_id = await asyncio.to_thread(
        docs_service.ensure_folder, "Templates"
    )
    print(f"Using Templates folder (id={template_folder_id})")

    async with AsyncSessionLocal() as session:
        existing = await _load_existing_memories(session)
        existing_codes, known_titles = await _load_existing_designations(session)

        added = updated = skipped = designations_added = 0

        for tab in tabs:
            logging.critical(f"Processing tab: {tab}")
            status, desg_count = await _process_tab(
                session, tab, doc_id, force, existing, existing_codes, known_titles,
                docs_service, template_folder_id,
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
