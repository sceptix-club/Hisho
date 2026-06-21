from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Official
from db.session import get_db
from api.schemas.officials import OfficialCreate, OfficialUpdate, OfficialResponse

router = APIRouter(prefix="/officials", tags=["officials"])


@router.get("/", response_model=list[OfficialResponse])
async def list_officials(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Official).where(Official.deleted.is_(False)))
    return result.scalars().all()


@router.get("/{official_id}", response_model=OfficialResponse)
async def get_official(official_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Official).where(
            Official.id == official_id,
            Official.deleted.is_(False),
        )
    )
    official = result.scalar_one_or_none()
    if not official:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Official not found"
        )
    return official


@router.post("/", response_model=OfficialResponse, status_code=status.HTTP_201_CREATED)
async def create_official(body: OfficialCreate, db: AsyncSession = Depends(get_db)):
    official = Official(
        id=str(uuid4()),
        name=body.name,
        address=body.address,
        role=body.role,
        organization=body.organization,
        signature=body.signature,
    )
    db.add(official)
    await db.commit()
    await db.refresh(official)
    return official


@router.put("/{official_id}", response_model=OfficialResponse)
async def update_official(
    official_id: str, body: OfficialUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Official).where(
            Official.id == official_id,
            Official.deleted.is_(False),
        )
    )
    official = result.scalar_one_or_none()
    if not official:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Official not found"
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(official, field, value)

    await db.commit()
    await db.refresh(official)
    return official


@router.delete("/{official_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_official(official_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Official).where(
            Official.id == official_id,
            Official.deleted.is_(False),
        )
    )
    official = result.scalar_one_or_none()
    if not official:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Official not found"
        )

    official.deleted = True
    await db.commit()
