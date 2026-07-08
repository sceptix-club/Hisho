"""Ingest letters from the tabs of a single Google Doc into pgvector memory.

Usage:
    uv run python -m scripts.ingest_letters [DOCUMENT_ID] [--force]

DOCUMENT_ID falls back to LETTERS_DOC_ID in .env. Each tab in the document is
stored as one letter (tab title = letter title). Requires GOOGLE_ACCESS_TOKEN /
GOOGLE_REFRESH_TOKEN and a running Ollama with the embedding model pulled
(`ollama pull nomic-embed-text`). Safe to re-run: already-ingested tabs are
skipped by doc_id#tab_id. Pass --force to re-extract and re-embed existing
tabs in place (e.g. after an extractor change).
"""

import asyncio
import sys
import uuid
from typing import Iterator

from sqlalchemy import select

from config import settings
from db.models import LetterMemory
from db.session import AsyncSessionLocal
from services.docs_services.docs_service import GoogleDocsService
from services.embeddings import embed_text


def _flatten_tabs(tabs: list[dict]) -> Iterator[dict]:
    for tab in tabs:
        yield tab
        yield from _flatten_tabs(tab.get("childTabs", []))


async def main() -> None:
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    doc_id = args[0] if args else settings.letters_doc_id
    if not doc_id:
        sys.exit("Pass a Google Doc ID or set LETTERS_DOC_ID in .env")
    if not (settings.google_access_token and settings.google_refresh_token):
        sys.exit("GOOGLE_ACCESS_TOKEN / GOOGLE_REFRESH_TOKEN not set in .env")

    service = GoogleDocsService(
        settings, settings.google_access_token, settings.google_refresh_token
    )
    doc = await asyncio.to_thread(service.fetch_document, doc_id, True)
    tabs = list(_flatten_tabs(doc.get("tabs", [])))
    print(f"Found {len(tabs)} tabs in '{doc.get('title', doc_id)}'")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LetterMemory))
        existing = {lm.source_doc_id: lm for lm in result.scalars()}

        added = updated = skipped = 0
        for tab in tabs:
            props = tab.get("tabProperties", {})
            source_id = f"{doc_id}#{props.get('tabId')}"
            row = existing.get(source_id)
            if row and not force:
                skipped += 1
                continue
            text = GoogleDocsService.extract_text(tab.get("documentTab", {}))
            if not text:
                skipped += 1
                continue
            title = props.get("title") or "Untitled letter"
            embedding = await embed_text(f"{title}\n\n{text}")
            if row:
                row.title, row.content, row.embedding = title, text, embedding
                updated += 1
                print(f"  ~ {title}")
            else:
                session.add(
                    LetterMemory(
                        id=uuid.uuid4().hex,
                        source_doc_id=source_id,
                        title=title,
                        content=text,
                        embedding=embedding,
                    )
                )
                added += 1
                print(f"  + {title}")
        await session.commit()

    print(f"Done: {added} added, {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(main())
