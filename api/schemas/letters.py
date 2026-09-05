from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_number: str
    letter_type_id: str
    description: str
    title: str
    approved: bool
    content: str | None = None
    user_facts: str = ""
    approval_chain: str = ""
    style_references: str = ""
    status: str = "pending"
    user_id: str = "default"
    session_id: str | None = None
    created_at: datetime
    updated_at: datetime
