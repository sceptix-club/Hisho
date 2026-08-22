from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OfficialCreate(BaseModel):
    name: str
    address: str
    role: str
    organization: str
    signature: str


class OfficialUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    role: str | None = None
    organization: str | None = None
    signature: str | None = None


class OfficialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    role: str
    organization: str
    signature: str
    created_at: datetime
    updated_at: datetime
