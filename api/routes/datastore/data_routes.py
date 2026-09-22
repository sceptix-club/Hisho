"""Read-only datastore endpoints for browsing ingested data."""

import json
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Signature, LetterTypeMemory, Designation
from db.session import get_db, engine
from api.schemas.datastore_schemas import (
    LetterNodeResponse,
    SignatureResponse,
    LetterTypeMemoryResponse,
    DesignationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datastore", tags=["datastore"])


# ── Letter Nodes (LlamaIndex PGVectorStore: data_letter_node) ─────────

@router.get("/letter-nodes", response_model=list[LetterNodeResponse])
async def list_letter_nodes():
    """List all letter nodes from the LlamaIndex-managed data_letter_node table.

    This table is NOT backed by a SQLAlchemy model – it is managed by
    PGVectorStore, so we query it with raw SQL via the async engine.
    """
    query = text(
        "SELECT id, text, metadata_, node_id FROM data_letter_nodes ORDER BY id"
    )
    async with engine.connect() as conn:
        result = await conn.execute(query)
        rows = result.mappings().all() 

    nodes: list[LetterNodeResponse] = []
    for row in rows:
        meta = row["metadata_"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                pass

        nodes.append(
            LetterNodeResponse(
                id=row["id"],
                text=row["text"],
                metadata_=meta,
                node_id=row["node_id"],
            )
        )
    return nodes


# ── Signatures (PG table) ────────────────────────────────────────────

@router.get("/signatures", response_model=list[SignatureResponse])
async def list_signatures(db: AsyncSession = Depends(get_db)):
    """List all extracted signature records."""
    result = await db.execute(select(Signature).order_by(Signature.created_at.desc()))
    return result.scalars().all()


# ── Letter Type Memory (PG table) ────────────────────────────────────

@router.get("/letter-type-memory", response_model=list[LetterTypeMemoryResponse])
async def list_letter_type_memory(db: AsyncSession = Depends(get_db)):
    """List all LLM-extracted letter type metadata records."""
    result = await db.execute(
        select(LetterTypeMemory).order_by(LetterTypeMemory.created_at.desc())
    )
    return result.scalars().all()


# ── Designations (PG table) ──────────────────────────────────────────

@router.get("/designations", response_model=list[DesignationResponse])
async def list_designations(db: AsyncSession = Depends(get_db)):
    """List all unique designations extracted from letter approval chains."""
    result = await db.execute(
        select(Designation).order_by(Designation.created_at.desc())
    )
    return result.scalars().all()
