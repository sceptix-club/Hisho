from pydantic import BaseModel, ConfigDict


class ApprovalChainStep(BaseModel):
    step: int
    role: str
    action: str


class LetterTypeCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    approval_chain: list[ApprovalChainStep]
    template: str


class LetterTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    approval_chain: list[ApprovalChainStep] | None = None
    template: str | None = None


class LetterTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    approval_chain: list[ApprovalChainStep]
    template: str
