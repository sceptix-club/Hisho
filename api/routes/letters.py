from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.routes.auth import get_current_user
from api.schemas.letters import LetterResponse
from db.models import Letter
from db.session import get_db

router = APIRouter(prefix="/letters", tags=["letters"])


@router.get("", response_model=list[LetterResponse], include_in_schema=False)
@router.get("/", response_model=list[LetterResponse])
async def get_letters(
    db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Letter)
        .where(Letter.user_id == current_user.id)
        .order_by(Letter.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{letter_id}", response_model=LetterResponse)
async def get_letter(
    letter_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Letter).where(Letter.id == letter_id, Letter.user_id == current_user.id)
    )
    letter = result.scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
    return letter
