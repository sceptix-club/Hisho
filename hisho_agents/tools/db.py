from sqlalchemy import select

from db.session import AsyncSessionLocal
from db.models import LetterType, Official


async def list_letter_types() -> str:
    """List all available letter types with their names and descriptions.

    Returns:
        A formatted string of all letter types (id, name, description) for the
        agent to choose from.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LetterType))
        types = result.scalars().all()
        if not types:
            return "No letter types found in the database."

        lines = ["Available letter types:", ""]
        for lt in types:
            lines.append(f"- {lt.id}: {lt.name}")
            if lt.description:
                lines.append(f"  {lt.description}")
            lines.append("")
        return "\n".join(lines).strip()


async def get_approval_chain_from_db(letter_type_id: str) -> str:
    """Fetch the approval chain for a letter type and resolve official names.

    Args:
        letter_type_id: The slug/id of the letter type (e.g. "event_permission").

    Returns:
        A formatted string listing each step, the role, the action required,
        and the current official holding that position.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LetterType).where(LetterType.id == letter_type_id)
        )
        letter_type = result.scalar_one_or_none()
        if not letter_type:
            return f"No letter type found with id '{letter_type_id}'."

        chain = letter_type.approval_chain
        if not chain:
            return f"Letter type '{letter_type_id}' has no approval chain defined."

        lines = [f"Approval Chain for: {letter_type.name}", ""]
        for step in sorted(chain, key=lambda s: s["step"]):
            off_result = await session.execute(
                select(Official).where(
                    Official.role == step["role"],
                    Official.deleted.is_(False),
                )
            )
            official = off_result.scalar_one_or_none()
            name = official.name if official else "— (vacant) —"
            lines.append(
                f"Step {step['step']}: {step['role']} — {step['action']}"
            )
            lines.append(f"  Current: {name}")
            lines.append("")

        return "\n".join(lines).strip()
