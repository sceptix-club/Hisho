"""API route to trigger letter ingestion from a Google Doc."""

import logging
from typing import Annotated, Iterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from llama_index.core import Document

from api.routes.auth import get_current_user
from db.models import User
from db.session import get_db
from services.docs_services.docs_service import GoogleDocsService
from services.docs_services.document_transformer import DocumentTransformer
from services.pipeline.pipeline import run_ingestion
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datastore", tags=["datastore"])


# ── Request / Response schemas ────────────────────────────────────────

class IngestionRequest(BaseModel):
    doc_id: str = Field(..., description="Google Doc ID to ingest")


class IngestionResponse(BaseModel):
    status: str
    message: str
    doc_id: str
    tabs_found: int
    documents_prepared: int


class IngestionResultResponse(BaseModel):
    status: str
    message: str
    doc_id: str
    tabs_found: int
    documents_prepared: int
    nodes_ingested: int


# ── Helpers (ported from scripts/ingest_letters.py) ───────────────────

def _flatten_tabs(tabs: list[dict]) -> Iterator[dict]:
    """Recursively yield every tab (including nested child tabs)."""
    for tab in tabs:
        yield tab
        yield from _flatten_tabs(tab.get("childTabs", []))


def _build_source_id(doc_id: str, tab_id: str) -> str:
    """Canonical composite key used to deduplicate ingested tabs."""
    return f"{doc_id}#{tab_id}"


async def _fetch_and_prepare(
    doc_id: str,
    access_token: str,
    refresh_token: str,
) -> tuple[str, list[Document], int]:
    """Fetch a Google Doc using the user's tokens, transform tabs into Documents.

    Returns:
        (doc_title, documents, total_tabs_count)
    """
    import asyncio

    service = GoogleDocsService(settings, access_token, refresh_token)
    doc = await asyncio.to_thread(service.fetch_document, doc_id, True)
    tabs = list(_flatten_tabs(doc.get("tabs", [])))
    doc_title = doc.get("title", doc_id)

    documents: list[Document] = []
    for tab in tabs:
        props = tab.get("tabProperties", {})
        tab_id = props.get("tabId", "")
        title = props.get("title") or "Untitled letter"

        document_tab = tab.get("documentTab", {})
        payload_json = DocumentTransformer.transform_to_payload(document_tab)

        if payload_json.strip() in ("", "[]"):
            continue

        documents.append(
            Document(
                text=payload_json,
                metadata={
                    "source_doc_id": _build_source_id(doc_id, tab_id),
                    "tab_title": title,
                },
            )
        )

    return doc_title, documents, len(tabs)


async def _run_ingestion_task(doc_id: str, documents: list[Document]) -> None:
    """Background task that runs the ingestion pipeline."""
    try:
        nodes = await run_ingestion(documents)
        logger.info(
            "Ingestion complete for doc %s – %d nodes ingested.", doc_id, len(nodes)
        )
    except Exception:
        logger.exception("Ingestion failed for doc %s", doc_id)


# ── Routes ────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_document(
    body: IngestionRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Kick off ingestion for a single Google Doc (fire-and-forget).

    Uses the authenticated user's Google tokens from the database.
    The response returns immediately with 202 Accepted while the pipeline
    runs in the background.
    """
    if not current_user.google_access_token or not current_user.google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account does not have Google credentials linked. Please re-login with Google.",
        )

    try:
        doc_title, documents, total_tabs = await _fetch_and_prepare(
            body.doc_id,
            current_user.google_access_token,
            current_user.google_refresh_token,
        )
    except Exception as exc:
        logger.exception("Failed to fetch Google Doc %s", body.doc_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch document: {exc}",
        )

    if not documents:
        return IngestionResponse(
            status="skipped",
            message=f"No ingestable tabs found in '{doc_title}'.",
            doc_id=body.doc_id,
            tabs_found=total_tabs,
            documents_prepared=0,
        )

    background_tasks.add_task(_run_ingestion_task, body.doc_id, documents)

    return IngestionResponse(
        status="accepted",
        message=f"Ingestion started for '{doc_title}' – {len(documents)} documents queued.",
        doc_id=body.doc_id,
        tabs_found=total_tabs,
        documents_prepared=len(documents),
    )


@router.post(
    "/ingest/sync",
    response_model=IngestionResultResponse,
)
async def ingest_document_sync(
    body: IngestionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Run ingestion synchronously and return the result.

    Uses the authenticated user's Google tokens from the database.
    The request will block until the pipeline finishes.
    """
    if not current_user.google_access_token or not current_user.google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account does not have Google credentials linked. Please re-login with Google.",
        )

    try:
        doc_title, documents, total_tabs = await _fetch_and_prepare(
            body.doc_id,
            current_user.google_access_token,
            current_user.google_refresh_token,
        )
    except Exception as exc:
        logger.exception("Failed to fetch Google Doc %s", body.doc_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch document: {exc}",
        )

    if not documents:
        return IngestionResultResponse(
            status="skipped",
            message=f"No ingestable tabs found in '{doc_title}'.",
            doc_id=body.doc_id,
            tabs_found=total_tabs,
            documents_prepared=0,
            nodes_ingested=0,
        )

    try:
        nodes = await run_ingestion(documents)
    except Exception as exc:
        logger.exception("Ingestion pipeline failed for doc %s", body.doc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failed: {exc}",
        )

    return IngestionResultResponse(
        status="completed",
        message=f"Ingested {len(nodes)} nodes from '{doc_title}'.",
        doc_id=body.doc_id,
        tabs_found=total_tabs,
        documents_prepared=len(documents),
        nodes_ingested=len(nodes),
    )
