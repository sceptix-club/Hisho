"""Smart chunking of raw Google Docs API JSON for small-model template extraction.

Converts the raw ``documentTab`` JSON from the Docs API into a list of
structurally-annotated chunks that a small LLM (e.g. Qwen 7B) can process
without needing to infer document structure from lossy plain text.

Chunk types emitted:
- ``paragraph``     — a single heading paragraph
- ``paragraph_group`` — consecutive body paragraphs grouped together
- ``table``         — a self-contained table with headers and rows
- ``header``        — content from a document header
- ``footer``        — content from a document footer

Skipped elements: section breaks, empty paragraphs, table-of-contents.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Heading style detection
# ---------------------------------------------------------------------------

_HEADING_STYLES = frozenset(
    {
        "HEADING_1",
        "HEADING_2",
        "HEADING_3",
        "HEADING_4",
        "HEADING_5",
        "HEADING_6",
        "TITLE",
        "SUBTITLE",
    }
)


def _is_heading(paragraph: dict) -> bool:
    """Return True if the paragraph uses a heading/title named style."""
    style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
    return style in _HEADING_STYLES


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _text_from_elements(elements: list[dict]) -> str:
    """Extract plain text from a list of paragraph elements (textRun, etc.)."""
    parts: list[str] = []
    for el in elements:
        text_run = el.get("textRun")
        if text_run:
            parts.append(text_run.get("content", ""))
    return "".join(parts)


def _text_from_content(content: list[dict]) -> str:
    """Recursively extract plain text from a content array (paragraphs only)."""
    parts: list[str] = []
    for item in content:
        if "paragraph" in item:
            parts.append(
                _text_from_elements(item["paragraph"].get("elements", []))
            )
        elif "table" in item:
            # Flatten table cells into text for header/footer contexts
            for row in item["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    parts.append(_text_from_content(cell.get("content", [])))
    return "".join(parts)


# ---------------------------------------------------------------------------
# Table chunking
# ---------------------------------------------------------------------------


def _chunk_table(table: dict) -> dict[str, Any]:
    """Convert a Docs API table element into a structured chunk.

    Attempts to use the first row as headers.  If the first row contains
    only empty cells the table is emitted with ``headers: null`` and all
    rows are treated as data.
    """
    table_rows_raw = table.get("tableRows", [])
    if not table_rows_raw:
        return {}

    def _row_texts(row: dict) -> list[str]:
        cells: list[str] = []
        for cell in row.get("tableCells", []):
            cell_text = _text_from_content(cell.get("content", [])).strip()
            cells.append(cell_text)
        return cells

    all_rows = [_row_texts(r) for r in table_rows_raw]

    # Heuristic: first row is a header if it has at least one non-empty cell
    first_row = all_rows[0] if all_rows else []
    if any(c.strip() for c in first_row):
        headers = first_row
        data_rows = all_rows[1:]
    else:
        headers = None
        data_rows = all_rows

    # Skip entirely empty tables
    if not data_rows and not headers:
        return {}

    return {
        "type": "table",
        "role": "data_table",
        "headers": headers,
        "rows": data_rows,
    }


# ---------------------------------------------------------------------------
# Body content chunking (recursive)
# ---------------------------------------------------------------------------


def _chunk_body_content(content: list[dict]) -> list[dict[str, Any]]:
    """Walk a ``body.content`` (or nested cell content) array and emit chunks.

    Consecutive non-heading paragraphs are grouped into a single
    ``paragraph_group`` chunk to preserve contextual flows like
    "Through, → Name → Designation".
    """
    chunks: list[dict[str, Any]] = []
    # Accumulator for consecutive body paragraphs
    body_buffer: list[str] = []

    def _flush_body_buffer() -> None:
        if not body_buffer:
            return
        combined = "".join(body_buffer).strip()
        if combined:
            chunks.append(
                {
                    "type": "paragraph_group",
                    "role": "body",
                    "text": combined,
                }
            )
        body_buffer.clear()

    for item in content:
        # --- Section breaks: skip ---
        if "sectionBreak" in item:
            continue

        # --- Table of contents: skip ---
        if "tableOfContents" in item:
            continue

        # --- Paragraph ---
        if "paragraph" in item:
            para = item["paragraph"]
            text = _text_from_elements(para.get("elements", []))

            # Empty / whitespace-only paragraphs act as group separators
            if not text.strip():
                _flush_body_buffer()
                continue

            if _is_heading(para):
                _flush_body_buffer()
                chunks.append(
                    {
                        "type": "paragraph",
                        "role": "heading",
                        "text": text.strip(),
                    }
                )
            else:
                body_buffer.append(text)
            continue

        # --- Table ---
        if "table" in item:
            _flush_body_buffer()
            table_chunk = _chunk_table(item["table"])
            if table_chunk:
                chunks.append(table_chunk)
            continue

    # Flush any remaining body paragraphs
    _flush_body_buffer()
    return chunks


# ---------------------------------------------------------------------------
# Header / footer chunking
# ---------------------------------------------------------------------------


def _chunk_header_footer(
    sections: dict[str, dict],
    kind: str,  # "header" or "footer"
) -> list[dict[str, Any]]:
    """Extract chunks from document headers or footers."""
    chunks: list[dict[str, Any]] = []
    for section_id, section in sections.items():
        content = section.get("content", [])
        text = _text_from_content(content).strip()
        if not text:
            continue
        chunks.append(
            {
                "type": kind,
                "role": kind,
                "text": text,
            }
        )
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_document(document_tab: dict) -> list[dict[str, Any]]:
    """Convert a raw ``documentTab`` dict into a list of annotated chunks.

    Parameters
    ----------
    document_tab:
        The ``tab["documentTab"]`` portion of a Google Docs API response
        fetched with ``includeTabsContent=True``.

    Returns
    -------
    list[dict]
        Each dict has at minimum ``chunk_id``, ``type``, ``role``, and
        either ``text`` (for paragraphs/headers/footers) or
        ``headers``/``rows`` (for tables).
    """
    chunks: list[dict[str, Any]] = []

    # 2. Body
    body_content = document_tab.get("body", {}).get("content", [])
    chunks.extend(_chunk_body_content(body_content))

    # 3. Footers
    footers = document_tab.get("footers", {})
    if footers:
        chunks.extend(_chunk_header_footer(footers, "footer"))

    # Assign sequential chunk_ids
    for idx, chunk in enumerate(chunks, start=1):
        chunk["chunk_id"] = idx

    return chunks


def chunks_to_prompt_text(chunks: list[dict[str, Any]]) -> str:
    """Serialise chunks into the compact text representation sent to the LLM.

    Each chunk is rendered as a labelled block so the model can see the
    structure without needing to parse JSON.

    Example output::

        [CHUNK 1 | type=paragraph | role=heading]
        Subject: Annual Tech Fest 2024 Budget Approval

        [CHUNK 2 | type=paragraph_group | role=body]
        Through,
        The Head of Department - CSE
        NMAMIT, Nitte
        ...

        [CHUNK 3 | type=table | role=data_table]
        | Sl. No. | Item | Quantity | Amount (₹) |
        | 1 | Banners & Posters | 50 | 15,000 |
        | 2 | Refreshments | 200 | 25,000 |
    """
    lines: list[str] = []

    for chunk in chunks:
        cid = chunk["chunk_id"]
        ctype = chunk["type"]
        crole = chunk["role"]
        header_line = f"[CHUNK {cid} | type={ctype} | role={crole}]"
        lines.append(header_line)

        if ctype == "table":
            # Render as a pipe-delimited table
            headers = chunk.get("headers")
            rows = chunk.get("rows", [])
            if headers:
                lines.append("| " + " | ".join(headers) + " |")
            for row in rows:
                lines.append("| " + " | ".join(row) + " |")
        else:
            text = chunk.get("text", "")
            lines.append(text)

        lines.append("")  # blank separator

    return "\n".join(lines).strip()
