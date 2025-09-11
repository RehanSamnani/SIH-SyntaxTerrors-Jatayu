from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.db import get_db
from app.models.drone import Drone, Mission, Waypoint, DroneStatus, MissionStatus
from app.models.order import Order
from app.models.user import UserRole
from app.schemas.drone import (
    DroneCreate,
    DroneResponse,
    MissionCreate,
    MissionResponse,
    MissionStatusUpdate
)
from app.utils.auth import get_current_user, check_role

router = APIRouter(tags=["drones"])

@router.post("/drones", response_model=DroneResponse)
async def register_drone(
    drone: DroneCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN))
):
    # Check if identifier is already used
    result = await db.execute(
        select(Drone).filter(Drone.identifier == drone.identifier)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drone identifier already registered"
        )
    
    db_drone = Drone(**drone.dict())
    db.add(db_drone)
    await db.commit()
    await db.refresh(db_drone)
    
    return db_drone

@router.get("/drones", response_model=List[DroneResponse])
async def list_drones(
    status: Optional[DroneStatus] = None,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    query = select(Drone)
    if status:
        query = query.filter(Drone.status == status)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/missions", response_model=MissionResponse)
async def create_mission(
    mission: MissionCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN, UserRole.DISPATCHER))
):
    # Verify drone exists and is available
    result = await db.execute(
        select(Drone).filter(Drone.id == mission.drone_id)
    )
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drone not found"
        )
    if drone.status != DroneStatus.IDLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Drone is not available (current status: {drone.status})"
        )
    
    # Verify order exists and get payload weight
    result = await db.execute(
        select(Order).filter(Order.id == mission.order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Validate payload capacity
    if order.total_weight_grams > drone.payload_capacity_grams:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order weight ({order.total_weight_grams}g) exceeds drone capacity ({drone.payload_capacity_grams}g)"
        )
    
    # Create mission
    db_mission = Mission(
        drone_id=mission.drone_id,
        order_id=mission.order_id
    )
    db.add(db_mission)
    
    # Add waypoints
    for i, waypoint in enumerate(mission.waypoints):
        db_waypoint = Waypoint(
            mission=db_mission,
            sequence_order=i,
            **waypoint.dict()
        )
        db.add(db_waypoint)
    
    # Update drone status
    drone.status = DroneStatus.IN_MISSION
    
    await db.commit()
    await db.refresh(db_mission)
    return db_mission

@router.get("/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(Mission)
        .options(joinedload(Mission.waypoints))
        .filter(Mission.id == mission_id)
    )
    mission = result.unique().scalar_one_or_none()
    
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found"
        )
    
    return mission

@router.put("/missions/{mission_id}/status", response_model=MissionResponse)
async def update_mission_status(
    mission_id: UUID,
    status_update: MissionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN, UserRole.DISPATCHER))
):
    # Get mission with its drone
    result = await db.execute(
        select(Mission)
        .options(joinedload(Mission.waypoints), joinedload(Mission.drone))
        .filter(Mission.id == mission_id)
    )
    mission = result.unique().scalar_one_or_none()
    
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found"
        )
    
    # Update mission status and timestamps
    if status_update.status == MissionStatus.IN_PROGRESS and not mission.started_at:
        mission.started_at = datetime.utcnow()
    elif status_update.status in [MissionStatus.COMPLETED, MissionStatus.FAILED]:
        mission.completed_at = datetime.utcnow()
        # Update drone status
        mission.drone.status = DroneStatus.IDLE
    
    mission.status = status_update.status
    await db.commit()
    await db.refresh(mission)
    
    return mission