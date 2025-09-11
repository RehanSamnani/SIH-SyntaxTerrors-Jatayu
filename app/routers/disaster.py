from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import List
from uuid import UUID

from app.db import get_db
from app.models.disaster import Disaster, DisasterType, Location, DisasterStatus
from app.models.user import UserRole
from app.schemas.disaster import (
    DisasterCreate,
    DisasterResponse,
    LocationCreate,
    LocationResponse,
    DisasterWithLocations
)
from app.utils.auth import get_current_user, check_role

router = APIRouter(tags=["disasters"])

@router.post("/disasters", response_model=DisasterResponse)
async def create_disaster(
    disaster: DisasterCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(check_role(UserRole.ADMIN, UserRole.DISPATCHER))
):
    # Verify disaster type exists
    result = await db.execute(
        select(DisasterType).filter(DisasterType.id == disaster.disaster_type_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disaster type not found"
        )
    
    # Create new disaster
    db_disaster = Disaster(
        **disaster.dict(),
        created_by=current_user.id
    )
    
    db.add(db_disaster)
    await db.commit()
    await db.refresh(db_disaster)
    
    return db_disaster

@router.get("/disasters", response_model=List[DisasterResponse])
async def list_disasters(
    status: DisasterStatus = None,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)  # Just to ensure authentication
):
    query = select(Disaster).options(joinedload(Disaster.disaster_type))
    
    if status:
        query = query.filter(Disaster.status == status)
    
    result = await db.execute(query)
    disasters = result.unique().scalars().all()
    
    return disasters

@router.get("/disasters/{disaster_id}", response_model=DisasterWithLocations)
async def get_disaster(
    disaster_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(Disaster)
        .options(joinedload(Disaster.disaster_type), joinedload(Disaster.locations))
        .filter(Disaster.id == disaster_id)
    )
    disaster = result.unique().scalar_one_or_none()
    
    if not disaster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disaster not found"
        )
    
    return disaster

@router.post("/locations", response_model=LocationResponse)
async def create_location(
    location: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(check_role(UserRole.ADMIN, UserRole.DISPATCHER))
):
    # Verify disaster exists
    result = await db.execute(
        select(Disaster).filter(Disaster.id == location.disaster_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disaster not found"
        )
    
    # Create new location
    db_location = Location(**location.dict())
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    
    return db_location

@router.get("/locations/{disaster_id}", response_model=List[LocationResponse])
async def list_locations(
    disaster_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(Location).filter(Location.disaster_id == disaster_id)
    )
    locations = result.scalars().all()
    
    if not locations:
        # Verify if disaster exists
        disaster_exists = await db.execute(
            select(Disaster).filter(Disaster.id == disaster_id)
        )
        if not disaster_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Disaster not found"
            )
    
    return locations