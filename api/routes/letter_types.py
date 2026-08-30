from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import LetterType
from db.session import get_db
from api.routes.auth import get_current_user
from api.schemas.letter_types import (
    LetterTypeCreate,
    LetterTypeUpdate,
    LetterTypeResponse,
)

router = APIRouter(prefix="/letter-types", tags=["letter-types"])


@router.get("", response_model=list[LetterTypeResponse], include_in_schema=False)
@router.get("/", response_model=list[LetterTypeResponse])
async def list_letter_types(
    db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(select(LetterType))
    return result.scalars().all()


@router.get("/{letter_type_id}", response_model=LetterTypeResponse)
async def get_letter_type(
    letter_type_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(select(LetterType).where(LetterType.id == letter_type_id))
    letter_type = result.scalar_one_or_none()
    if not letter_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Letter type not found"
        )
    return letter_type


@router.post(
    "", response_model=LetterTypeResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False
)
@router.post(
    "/", response_model=LetterTypeResponse, status_code=status.HTTP_201_CREATED
)
async def create_letter_type(
    body: LetterTypeCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    letter_type = LetterType(
        id=body.id,
        name=body.name,
        description=body.description,
        approval_chain=[s.model_dump() for s in body.approval_chain],
        template=body.template,
    )
    db.add(letter_type)
    await db.commit()
    await db.refresh(letter_type)
    return letter_type


@router.put("/{letter_type_id}", response_model=LetterTypeResponse)
async def update_letter_type(
    letter_type_id: str,
    body: LetterTypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(LetterType).where(LetterType.id == letter_type_id))
    letter_type = result.scalar_one_or_none()
    if not letter_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Letter type not found"
        )

    update_data = body.model_dump(exclude_unset=True)
    if "approval_chain" in update_data:
        update_data["approval_chain"] = [s.model_dump() for s in body.approval_chain]

    for field, value in update_data.items():
        setattr(letter_type, field, value)

    await db.commit()
    await db.refresh(letter_type)
    return letter_type


@router.delete("/{letter_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_letter_type(
    letter_type_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(select(LetterType).where(LetterType.id == letter_type_id))
    letter_type = result.scalar_one_or_none()
    if not letter_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Letter type not found"
        )

    await db.delete(letter_type)
    await db.commit()
