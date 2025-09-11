from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import datetime
from uuid import UUID

from app.db import get_db
from app.models.telemetry import (
    Telemetry, 
    Obstacle, 
    ProofOfDelivery, 
    ObstacleSeverity,
    TelemetryStatus
)
from app.models.drone import Mission, MissionStatus
from app.schemas.telemetry import (
    TelemetryCreate,
    TelemetryResponse,
    ObstacleCreate,
    ObstacleResponse,
    ProofOfDeliveryCreate,
    ProofOfDeliveryResponse
)
from app.utils.auth import get_current_user

router = APIRouter(tags=["telemetry"])

async def handle_critical_telemetry(
    db: AsyncSession,
    mission_id: UUID,
    telemetry_status: TelemetryStatus
):
    """Handle critical telemetry by updating mission status if needed."""
    if telemetry_status == TelemetryStatus.CRITICAL:
        result = await db.execute(
            select(Mission).filter(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()
        if mission and mission.status == MissionStatus.IN_PROGRESS:
            mission.status = MissionStatus.FAILED
            await db.commit()

@router.post("/telemetry", response_model=TelemetryResponse)
async def upload_telemetry(
    telemetry: TelemetryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    # Verify mission exists and is active
    result = await db.execute(
        select(Mission).filter(Mission.id == telemetry.mission_id)
    )
    mission = result.scalar_one_or_none()
    if not mission or mission.status not in [MissionStatus.ASSIGNED, MissionStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or inactive mission"
        )

    # Create telemetry record
    db_telemetry = Telemetry(**telemetry.dict())
    db.add(db_telemetry)
    await db.commit()
    await db.refresh(db_telemetry)

    # Handle critical telemetry in background
    background_tasks.add_task(
        handle_critical_telemetry,
        db,
        telemetry.mission_id,
        telemetry.status
    )

    return db_telemetry

@router.get("/telemetry/{mission_id}", response_model=List[TelemetryResponse])
async def get_telemetry_history(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(Telemetry)
        .filter(Telemetry.mission_id == mission_id)
        .order_by(Telemetry.timestamp.desc())
    )
    return result.scalars().all()

@router.post("/obstacles", response_model=ObstacleResponse)
async def log_obstacle(
    obstacle: ObstacleCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    # Create obstacle record
    db_obstacle = Obstacle(**obstacle.dict())
    db.add(db_obstacle)
    
    # If severity is HIGH, update mission status
    if obstacle.severity == ObstacleSeverity.HIGH:
        result = await db.execute(
            select(Mission).filter(Mission.id == obstacle.mission_id)
        )
        mission = result.scalar_one_or_none()
        if mission and mission.status == MissionStatus.IN_PROGRESS:
            mission.status = MissionStatus.FAILED
            mission.command_log = (mission.command_log or []) + [{
                "timestamp": datetime.utcnow().isoformat(),
                "event": "mission_aborted",
                "reason": "high_severity_obstacle_detected"
            }]
    
    await db.commit()
    await db.refresh(db_obstacle)
    
    # Return error code for high severity obstacles
    if obstacle.severity == ObstacleSeverity.HIGH:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="High severity obstacle detected. Mission paused."
        )
    
    return db_obstacle

@router.post("/proof/{mission_id}", response_model=ProofOfDeliveryResponse)
async def upload_delivery_proof(
    mission_id: UUID,
    proof: ProofOfDeliveryCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    # Verify mission exists and is in progress
    result = await db.execute(
        select(Mission).filter(Mission.id == mission_id)
    )
    mission = result.scalar_one_or_none()
    if not mission or mission.status != MissionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mission or mission not in progress"
        )
    
    # Create proof of delivery
    db_proof = ProofOfDelivery(
        mission_id=mission_id,
        **proof.dict()
    )
    db.add(db_proof)
    
    # Update mission status to completed
    mission.status = MissionStatus.COMPLETED
    mission.completed_at = datetime.utcnow()
    mission.command_log = (mission.command_log or []) + [{
        "timestamp": datetime.utcnow().isoformat(),
        "event": "delivery_completed",
        "proof_id": str(db_proof.id)
    }]
    
    await db.commit()
    await db.refresh(db_proof)
    
    return db_proof