"""Pydantic response schemas for datastore endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LetterNodeResponse(BaseModel):
    """A single letter node from the LlamaIndex data_letter_node table."""

    id: int
    text: str | None = None
    metadata_: dict[str, Any] | None = None
    node_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_doc_id: str
    image_url: str
    name: str | None = None
    created_at: datetime


class LetterTypeMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    letter_type: str
    primary_domain: str
    description: str
    approval_chain: list[dict[str, Any]]
    table_info: dict[str, Any] | None = None
    template_url: str | None = None
    created_at: datetime


class DesignationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    incumbent: str | None = None
    created_at: datetime
