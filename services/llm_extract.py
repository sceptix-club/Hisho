"""Extract structured letter metadata via the local Ollama chat model.

Uses the same Ollama instance as embedding — calls ``/api/chat`` with
``settings.letter_model`` (stripping the ``ollama_chat/`` LiteLLM prefix)
and a JSON-mode system prompt that matches ``LetterExtractionOutput``.
"""

import json
import re

from pydantic import BaseModel, Field

from config import settings
from services.ollama_client import call_ollama_api

_OLLAMA_MODEL = settings.letter_model.removeprefix("ollama_chat/")




class ApprovalStep(BaseModel):
    step_number: int = Field(description="Sequence number starting at 1")
    designation_title: str = Field(
        description="The designation name (e.g. 'Head of Department - CSE'). Omit college/company name."
    )
    incumbent: str | None = Field(description="The name of the person holding the designation, if present.", default=None)


class TableInfo(BaseModel):
    summary: str | None = Field(description="High level summary, e.g. Budget breakdown", default=None)
    category: str | None = Field(description="<FINANCIAL | TIMELINE | ROSTER | INVENTORY | OTHER>", default=None)
    headers: list[str] = Field(
        description="List of column headers in the table, if any. Empty list if none.",
        default_factory=list
    )


class SignatureInfo(BaseModel):
    url: str | None = Field(description="URL of the image that acts as a signature", default=None)
    name: str | None = Field(description="The name of the signee.", default=None)


class LetterExtractionOutput(BaseModel):
    letter_type: str = Field(
        description="Exactly one enum value from list above"
    )
    primary_domain: str = Field(
        description="<FINANCE | LOGISTICS | INFRASTRUCTURE | ACADEMICS | EVENT | GENERAL>"
    )
    description: str = Field(
        description=(
            "A clear, general-purpose summary using the full body that projects the letter's intent."
        )
    )
    table_info: TableInfo | None = Field(
        description="Information about the tabular data block, if one exists",
        default=None,
    )
    approval_chain: list[ApprovalStep] = Field(
        description=(
            "Ordered list of approvers from bottom (first) to top (final recipient)"
        )
    )
    signatures: list[SignatureInfo] = Field(
        description="List of identified signatures and their designations",
        default_factory=list
    )



_SYSTEM_PROMPT = """\
You are a structured-data extraction assistant for an institutional document archiving system. 
Analyze the provided JSON document structure (which contains text, tables, and image URLs) and output ONLY a JSON object conforming strictly to the schema below.

Categories for `letter_type` (Choose EXACTLY ONE based on Intent + Domain):
- FINANCIAL_REQUEST (Releasing funds, budget approvals, sponsorships, reimbursements)
- VENUE_PERMISSION (Requesting classrooms, auditoriums, labs, halls)
- EQUIPMENT_REQUEST (Borrowing cameras, systems, AV gear, vehicles, physical assets)
- EVENT_APPROVAL (Permission to host workshops, hackathons, seminars, fests)
- ACADEMIC_DUTY_LEAVE (Attendance clearance, duty leave for students/staff)
- OFFICIAL_CIRCULAR (Notices, announcements, mandates sent downward)
- INVITATION (Inviting chief guests, speakers, external judges)
- GENERAL_CORRESPONDENCE (Any formal letter that does not fit above)

Schema:
{
  "reference_number": "<string or null - Ref No from header>",
  "letter_type": "<string - Exactly one enum value from list above>",
  "primary_domain": "<string - FINANCE | LOGISTICS | INFRASTRUCTURE | ACADEMICS | EVENT | GENERAL>",
  "description": "<string - Abstract 1-sentence summary WITHOUT specific dates, names, or item lists. E.g. 'Requesting temporary equipment loan for an upcoming technical workshop.'>",
  "table_info": { // Set to null if there are no tables
    "summary": "<string or null - High level summary, e.g. Budget breakdown>",
    "category": "<string or null - FINANCIAL | TIMELINE | ROSTER | INVENTORY | OTHER>",
    "headers": ["<string - Column 1 header>", "<string - Column 2 header>"]
  },
  "approval_chain": [
    {
      "step_number": <int - bottom-up sequence starting at 1>,
      "designation_title": "<string - The designation name exactly what is written in the line nothing removed nothing added >",
      "incumbent": "<string or null - The name of the person holding the designation, if present exact name no addition from your side>"
    }
  ],
  "signatures": [
    {
      "url": "<string - URL of image that is a signature>",
      "name": "<string - The name of the signee>"
    }
  ]
}

Rules:
- DO NOT default to a generic 'REQUEST' for letter_type. Always qualify it using the subject and target domain.
- `description` MUST be abstract and general. Never include specific dates (e.g. 13 July 2026), specific names, or itemized lists.
- `approval_chain` MUST be bottom-up (Step 1 is the first endorser, final step is the top recipient).
- `signatures` MUST ONLY include URLs of images that act as signatures (typically found at the end of the document or near approval titles), ignoring logos, letterheads, or structural images. It MUST also include the name of the signee.
- Output raw JSON only. No markdown formatting, no backticks, no commentary.
"""



def _build_chat_payload(payload_json: str) -> dict:
    """Build the Ollama /api/chat request body for letter extraction."""
    return {
        "model": _OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": payload_json[:12000]},
        ],
        "format": "json",
    }


def _clean_llm_response(raw: str) -> str:
    """Strip markdown code-fences the model sometimes wraps around JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _parse_extraction(raw: str) -> LetterExtractionOutput:
    """Parse and validate the raw LLM JSON string into a typed output."""
    cleaned = _clean_llm_response(raw)
    data = json.loads(cleaned)
    return LetterExtractionOutput.model_validate(data)




async def extract_letter_metadata(payload_json: str) -> LetterExtractionOutput:
    """Send letter JSON payload to Ollama and return validated extraction."""
    resp_data = await call_ollama_api(
        "/api/chat",
        payload=_build_chat_payload(payload_json),
        timeout=120,
    )
    raw = resp_data["message"]["content"]

    return _parse_extraction(raw)