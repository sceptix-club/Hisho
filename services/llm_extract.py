"""Extract structured letter metadata via the local Ollama chat model.

Uses the same Ollama instance as embedding — calls ``/api/chat`` with
``settings.letter_model`` (stripping the ``ollama_chat/`` LiteLLM prefix)
and a JSON-mode system prompt that matches ``LetterExtractionOutput``.
"""

import json
import re

import httpx
from pydantic import BaseModel, Field

from config import settings

_OLLAMA_MODEL = settings.letter_model.removeprefix("ollama_chat/")




class ApprovalStep(BaseModel):
    step_number: int = Field(description="Sequence number starting at 1")
    designation_title: str = Field(
        description="Full title of the post, e.g., 'Head of Department - CSE'"
    )
    designation_code: str = Field(
        description="Short unique code for the designation, e.g., 'HOD_CSE'"
    )


class LetterExtractionOutput(BaseModel):
    type_name: str = Field(
        description="Categorical name of the letter type, e.g., 'Fund Release Request'"
    )
    description: str = Field(
        description=(
            "A concise summary of the letter's purpose for semantic vector search"
        )
    )
    approval_chain: list[ApprovalStep] = Field(
        description=(
            "Ordered list of approvers from bottom (first) to top (final recipient)"
        )
    )
    required_sections: list[str] = Field(
        description=(
            "List of detected structural blocks, e.g. "
            "['ref_no', 'date', 'recipient', 'through_chain', "
            "'subject', 'budget_table', 'sign_off']"
        )
    )



_SYSTEM_PROMPT = """\
You are a structured-data extraction assistant. You will receive the full
plain-text of an official letter. Respond with **only** a JSON object that
conforms to the schema below — no markdown fences, no commentary.

Schema:
{
  "type_name": "<string – categorical name of the letter type>",
  "description": "<string – concise summary of the letter's purpose>",
  "approval_chain": [
    {
      "step_number": <int – sequence starting at 1, bottom-up>,
      "designation_title": "<string – full title of the post>",
      "designation_code": "<string – short unique code, e.g. HOD_CSE>"
    }
  ],
  "required_sections": ["<string>", "..."]
}

Rules:
- type_name should be a human-readable category.
- description is a one- or two-sentence summary suitable for semantic search.
- approval_chain is ordered bottom-up: step 1 is the first endorser, the
  last step is the final recipient / approver.
- required_sections lists detected structural blocks using snake_case keys
  (e.g. ref_no, date, recipient, through_chain, subject, body,
  budget_table, sign_off).
- Output ONLY valid JSON. No extra text.
"""




def _build_chat_payload(text: str) -> dict:
    """Build the Ollama /api/chat request body for letter extraction."""
    return {
        "model": _OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text[:12000]},
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




async def extract_letter_metadata(text: str) -> LetterExtractionOutput:
    """Send letter text to Ollama and return validated extraction."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=_build_chat_payload(text),
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    return _parse_extraction(raw)


class TemplateReplacement(BaseModel):
    original_text: str = Field(
        description="Exact text from the letter to replace"
    )
    placeholder: str = Field(
        description="{{snake_case}} placeholder name for the template"
    )


class TemplateReplacementOutput(BaseModel):
    replacements: list[TemplateReplacement] = Field(
        description="List of text-to-placeholder replacement pairs"
    )


_REPLACEMENT_SYSTEM_PROMPT = """\
You are a template extraction assistant. You will receive the full plain-text
of an official letter. Identify every instance-specific value that should be
replaced with a reusable placeholder to turn this letter into a generic
template.

Output a JSON object with a single key "replacements" containing an array of
objects, each with:
- "original_text": the EXACT text as it appears in the letter (character-for-
  character match required)
- "placeholder": a descriptive {{snake_case_placeholder}} name

Examples of replacements:
- {"original_text": "Dr. K. Ramesh Babu", "placeholder": "{{recipient_name}}"}
- {"original_text": "Head of Department - CSE", "placeholder": "{{recipient_designation}}"}
- {"original_text": "12/03/2024", "placeholder": "{{date}}"}
- {"original_text": "Ref. No. NMAMIT/CSE/2024-25/001", "placeholder": "{{reference_number}}"}
- {"original_text": "Annual Tech Fest 2024", "placeholder": "{{event_name}}"}
- {"original_text": "₹50,000", "placeholder": "{{amount}}"}
- {"original_text": "Seminar Hall - Block A", "placeholder": "{{venue}}"}

Rules:
- original_text MUST be an EXACT substring of the input letter text.
- Use descriptive snake_case names for placeholders, wrapped in {{ and }}.
- Replace ALL instance-specific values: names, dates, amounts, reference
  numbers, addresses, event names, venue names, department names, etc.
- For body paragraphs that describe the specific request, replace KEY VALUES
  within them (dates, names, amounts) — do NOT replace entire paragraphs.
- Do NOT replace structural labels ("To:", "From:", "Subject:", "Date:",
  "Ref. No.:", "Through,", "Respected Sir,", "Yours sincerely,", etc.).
- Do NOT replace generic phrases, salutations, or closing formulas.
  Examples of text you must NEVER replace:
  "Through,", "Respected Sir,", "Yours sincerely,", "Yours faithfully,",
  "The Principal", "The Head of Department", entire body paragraphs.
- Each original_text should be long enough to be unambiguous — prefer
  "Head of Department - CSE" over just "CSE".
- Every object MUST have both "original_text" and "placeholder" keys.
  Never omit the "placeholder" key.
- Output ONLY valid JSON. No markdown fences, no commentary.
"""


def _build_replacement_payload(text: str) -> dict:
    """Build the Ollama /api/chat request body for replacement identification."""
    return {
        "model": _OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": _REPLACEMENT_SYSTEM_PROMPT},
            {"role": "user", "content": text[:12000]},
        ],
        "format": "json",
    }


def _parse_replacements(raw: str) -> list[TemplateReplacement]:
    """Parse and validate the raw LLM JSON string into replacement pairs.

    Malformed entries (e.g. missing ``placeholder``) are silently skipped
    so that a few bad items from the LLM don't crash the whole pipeline.
    """
    cleaned = _clean_llm_response(raw)
    data = json.loads(cleaned)

    # Validate each replacement individually so bad entries are skipped
    valid: list[TemplateReplacement] = []
    for item in data.get("replacements", []):
        try:
            valid.append(TemplateReplacement.model_validate(item))
        except Exception:
            # Skip malformed entries (e.g. missing placeholder)
            continue
    return valid


async def identify_template_replacements(text: str) -> list[TemplateReplacement]:
    """Send letter text to Ollama and return replacement pairs for templating.

    The LLM identifies instance-specific values in the letter and suggests
    ``{{placeholder}}`` replacements.  These pairs are then applied via the
    Google Docs ``replaceAllText`` API on a formatted copy of the original
    document, producing a template that preserves all original formatting.
    """
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=_build_replacement_payload(text),
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    return _parse_replacements(raw)

