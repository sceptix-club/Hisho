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
from services.doc_chunker import chunk_document, chunks_to_prompt_text

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
- "placeholder": a descriptive {{snake_case_placeholder}} name or standard generic text

Examples of replacements:
- {"original_text": "Dr. K. Ramesh Babu", "placeholder": "{{recipient_name}}"}
- {"original_text": "Head of Department - CSE", "placeholder": "Head of Department - {{department_name}}"}
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
- IMPORTANT (BODY REMOVAL): Replace the entire body section of the letter (the paragraph(s) containing the core message or specific request between the salutation and closing) with a single clean placeholder text like "[Insert Letter Body Here]" or "{{letter_body}}".
- Do NOT replace structural labels ("To:", "From:", "Subject:", "Date:",
  "Ref. No.:", "Through,", "Respected Sir,", "Yours sincerely,", etc.).
- Do NOT replace generic phrases, salutations, or closing formulas.
  Examples of text you must NEVER replace:
  "Through,", "Respected Sir,", "Yours sincerely,", "Yours faithfully,",
  "The Principal", "The Head of Department".
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

    Handles two possible LLM output shapes:
    - ``{"replacements": [...]}`` — validated via ``TemplateReplacementOutput``
    - ``[...]`` — a bare list of replacement objects

    Malformed entries (e.g. missing ``placeholder``) are silently skipped
    so that a few bad items from the LLM don't crash the whole pipeline.
    """
    cleaned = _clean_llm_response(raw)
    data = json.loads(cleaned)

    # Normalise: extract the raw list of replacement dicts
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = TemplateReplacementOutput.model_validate(data).replacements
        return list(items)  # already validated as TemplateReplacement objects
    else:
        return []

    # Validate each replacement individually so bad entries are skipped
    valid: list[TemplateReplacement] = []
    for item in items:
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
    async with httpx.AsyncClient(timeout=260) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=_build_replacement_payload(text),
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    return _parse_replacements(raw)


# ── Chunked template extraction (optimised for small models) ──────────


_CHUNKED_REPLACEMENT_SYSTEM_PROMPT = """\
You are a template extraction assistant.

## YOUR TASK
You receive a letter split into labelled chunks.
Find every value that changes between letters and replace it with a placeholder.
Output ONLY a JSON object. No other text.

## INPUT FORMAT
The letter is split into chunks. Each chunk has a header line like:
[CHUNK 1 | type=paragraph | role=heading]
followed by the chunk text.

Chunk types:
- paragraph / paragraph_group: regular text (headings, body, addresses)
- table: data in rows and columns
- header / footer: text from the page header or footer area

## OUTPUT FORMAT
Return a JSON object with one key "replacements". The value is an array.
Each item has exactly two keys:
- "original_text": the EXACT text from the letter to replace. Must be copied character-for-character.
- "placeholder": a {{snake_case}} name OR descriptive generic text.

Example output:
{
  "replacements": [
    {"original_text": "Dr. K. Ramesh Babu", "placeholder": "{{recipient_name}}"},
    {"original_text": "12/03/2024", "placeholder": "{{date}}"},
    {"original_text": "Ref. No. NMAMIT/CSE/2024-25/001", "placeholder": "{{reference_number}}"},
    {"original_text": "Head of Department - CSE", "placeholder": "Head of Department - {{department_name}}"},
    {"original_text": "Annual Tech Fest 2024", "placeholder": "{{event_name}}"},
    {"original_text": "50,000", "placeholder": "{{amount}}"},
    {"original_text": "Seminar Hall - Block A", "placeholder": "{{venue}}"}
  ]
}

## WHAT TO REPLACE
Replace these kinds of values:
- Person names (Dr. K. Ramesh Babu → {{recipient_name}})
- Dates (12/03/2024 → {{date}})
- Reference numbers (Ref. No. NMAMIT/CSE/2024-25/001 → {{reference_number}})
- Department names when part of a title (CSE → {{department_name}})
- Event names (Annual Tech Fest 2024 → {{event_name}})
- Money amounts (₹50,000 → {{amount}})
- Venue / location names (Seminar Hall → {{venue}})
- Specific quantities and counts
- The main body paragraph(s) between salutation and closing → {{letter_body}}

For TABLE chunks:
- Replace specific data values in cells (amounts, names, items)
- Do NOT replace column header labels (like "Sl. No.", "Item", "Amount")
- Do NOT replace row numbers (1, 2, 3...)

## WHAT TO NEVER REPLACE
Never replace any of these:
- "Through," / "To:" / "From:" / "Subject:" / "Date:" / "Ref. No.:"
- "Respected Sir," / "Respected Madam,"
- "Yours sincerely," / "Yours faithfully,"
- "The Principal" / "The Head of Department"
- Table column headers
- Generic greetings or closing formulas

## RULES
1. original_text MUST be an exact substring of the input text.
2. Use descriptive snake_case names inside {{ and }}.
3. Every item MUST have both "original_text" and "placeholder" keys.
4. Output ONLY valid JSON. No markdown. No commentary.
"""


def _build_chunked_replacement_payload(chunks_text: str) -> dict:
    """Build the Ollama /api/chat request for chunked replacement extraction."""
    return {
        "model": _OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": _CHUNKED_REPLACEMENT_SYSTEM_PROMPT},
            {"role": "user", "content": chunks_text[:12000]},
        ],
        "format": "json",
    }


async def identify_template_replacements_chunked(
    document_tab: dict,
) -> list[TemplateReplacement]:
    """Chunk a raw Google Docs ``documentTab`` and extract template replacements.

    Unlike :func:`identify_template_replacements` which operates on plain
    text, this function preserves document structure by converting the raw
    API JSON into labelled chunks (paragraphs, tables, headers, footers)
    before sending them to the LLM.  This yields much better results with
    small models like Qwen 7B that struggle to infer structure from flat
    text.

    Args:
        document_tab: The ``tab["documentTab"]`` portion of a Docs API
            response (fetched with ``includeTabsContent=True``).

    Returns:
        A list of :class:`TemplateReplacement` pairs ready for
        ``replaceAllText`` via the Docs API.
    """
    chunks = chunk_document(document_tab)
    if not chunks:
        return []

    chunks_text = chunks_to_prompt_text(chunks)
    print(f"    📦 Chunked document into {len(chunks)} chunks "
          f"({len(chunks_text)} chars)")

    async with httpx.AsyncClient(timeout=260) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=_build_chunked_replacement_payload(chunks_text),
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    return _parse_replacements(raw)

