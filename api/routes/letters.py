from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Letter
from db.session import get_db

router = APIRouter(prefix="/letters", tags=["letters"])


@router.get("", include_in_schema=False)
@router.get("/")
async def get_letters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Letter))
    letters = result.scalars().all()
    if not letters:
        return {"message": "empty"}
    else:
        return letters
