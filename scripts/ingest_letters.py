"""Ingest letters from the tabs of a single Google Doc into pgvector memory.

Usage:
    uv run python -m scripts.ingest_letters [DOCUMENT_ID]

DOCUMENT_ID falls back to LETTERS_DOC_ID in .env. Each tab in the document is
stored as one letter (tab title = letter title). Requires GOOGLE_ACCESS_TOKEN /
GOOGLE_REFRESH_TOKEN and a running Ollama with the embedding model pulled
(`ollama pull nomic-embed-text`). Safe to re-run: already-ingested tabs are
skipped by doc_id#tab_id.
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
    doc_id = sys.argv[1] if len(sys.argv) > 1 else settings.letters_doc_id
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
        result = await session.execute(select(LetterMemory.source_doc_id))
        known = {source_id for (source_id,) in result if source_id}

        added = skipped = 0
        for tab in tabs:
            props = tab.get("tabProperties", {})
            source_id = f"{doc_id}#{props.get('tabId')}"
            if source_id in known:
                skipped += 1
                continue
            text = GoogleDocsService.extract_text(tab.get("documentTab", {}))
            if not text:
                skipped += 1
                continue
            title = props.get("title") or "Untitled letter"
            session.add(
                LetterMemory(
                    id=uuid.uuid4().hex,
                    source_doc_id=source_id,
                    title=title,
                    content=text,
                    embedding=await embed_text(f"{title}\n\n{text}"),
                )
            )
            added += 1
            print(f"  + {title}")
        await session.commit()

    print(f"Done: {added} added, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(main())
