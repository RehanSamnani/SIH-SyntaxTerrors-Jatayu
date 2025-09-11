from pydantic import BaseModel, UUID4, constr, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from app.models.drone import DroneStatus, MissionStatus

class DroneBase(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=50)
    payload_capacity_grams: float = Field(..., gt=0)

class DroneCreate(DroneBase):
    pass

class DroneHealthLogCreate(BaseModel):
    health_status: str
    battery_percent: float = Field(..., ge=0, le=100)
    temperature: float

class DroneResponse(DroneBase):
    id: UUID4
    status: DroneStatus
    last_telemetry: Optional[Dict[str, Any]]
    last_seen: Optional[datetime]

    model_config = {"from_attributes": True}

class WaypointBase(BaseModel):
    lat: Decimal = Field(..., ge=-90, le=90)
    lon: Decimal = Field(..., ge=-180, le=180)
    alt: float = Field(..., ge=0)
    hold_time: Optional[int] = 0

    @model_validator(mode='after')
    def validate_coordinates(self):
        if not -90 <= float(self.lat) <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        if not -180 <= float(self.lon) <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        if self.alt < 0:
            raise ValueError('Altitude must be non-negative')
        return self

class WaypointCreate(WaypointBase):
    pass

class WaypointResponse(WaypointBase):
    id: UUID4
    sequence_order: int

    model_config = {"from_attributes": True}

class MissionCreate(BaseModel):
    order_id: UUID4
    drone_id: UUID4
    waypoints: List[WaypointCreate]

    @model_validator(mode='after')
    def check_waypoints(self):
        if not self.waypoints:
            raise ValueError("Mission must have at least one waypoint")
        return self

class MissionResponse(BaseModel):
    id: UUID4
    drone_id: UUID4
    order_id: UUID4
    status: MissionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    command_log: Optional[List[Dict[str, Any]]]
    waypoints: List[WaypointResponse]

    model_config = {"from_attributes": True}

class MissionStatusUpdate(BaseModel):
    status: MissionStatus

    @model_validator(mode='after')
    def validate_status_transition(self):
        valid_transitions = {
            MissionStatus.ASSIGNED: [MissionStatus.IN_PROGRESS, MissionStatus.FAILED],
            MissionStatus.IN_PROGRESS: [MissionStatus.COMPLETED, MissionStatus.FAILED],
            MissionStatus.COMPLETED: [],  # Terminal state
            MissionStatus.FAILED: [],  # Terminal state
        }
        return self