"""Letter type categories available to the LLM extraction prompt.

Each entry pairs the machine-readable enum value used as ``letter_type`` in
``LetterExtractionOutput`` with the description the LLM uses to disambiguate.
Keep this as the single source of truth for the categories shown to the model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LetterTypeCategory:
    value: str
    description: str

    def __str__(self) -> str:
        return f"{self.value} ({self.description})"


LETTER_TYPE_CATEGORIES: list[LetterTypeCategory] = [
    LetterTypeCategory(
        value="FINANCIAL_REQUEST",
        description="Releasing funds, budget approvals, sponsorships, reimbursements",
    ),
    LetterTypeCategory(
        value="VENUE_PERMISSION",
        description="Requesting classrooms, auditoriums, labs, halls",
    ),
    LetterTypeCategory(
        value="EQUIPMENT_REQUEST",
        description="Borrowing cameras, systems, AV gear, vehicles, physical assets",
    ),
    LetterTypeCategory(
        value="EVENT_APPROVAL",
        description="Permission to host workshops, hackathons, seminars, fests",
    ),
    LetterTypeCategory(
        value="ACADEMIC_DUTY_LEAVE",
        description="Attendance clearance, duty leave for students/staff",
    ),
    LetterTypeCategory(
        value="OFFICIAL_CIRCULAR",
        description="Notices, announcements, mandates sent downward",
    ),
    LetterTypeCategory(
        value="INVITATION",
        description="Inviting chief guests, speakers, external judges",
    ),
    LetterTypeCategory(
        value="GENERAL_CORRESPONDENCE",
        description="Any formal letter that does not fit above",
    ),
]


    



def format_letter_types_block() -> str:
    """Render the bullet list of letter types for the system prompt."""
    return "\n".join(
        f"- {category}" for category in LETTER_TYPE_CATEGORIES
    )
