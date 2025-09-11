from pydantic import BaseModel, UUID4, Field, model_validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from app.models.telemetry import TelemetryStatus, ObstacleType, ObstacleSeverity

class TelemetryBase(BaseModel):
    lat: Decimal = Field(..., ge=-90, le=90)
    lon: Decimal = Field(..., ge=-180, le=180)
    alt: float
    pitch: float
    roll: float
    yaw: float
    battery_level: float = Field(..., ge=0, le=100)
    status: TelemetryStatus

    @model_validator(mode='after')
    def validate_coordinates(self):
        if not -90 <= float(self.lat) <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        if not -180 <= float(self.lon) <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return self

class TelemetryCreate(TelemetryBase):
    mission_id: UUID4
    drone_id: UUID4

class TelemetryResponse(TelemetryBase):
    id: UUID4
    timestamp: datetime

    model_config = {"from_attributes": True}

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

    @model_validator(mode='after')
    def validate_coordinates(self):
        if self.x2 <= self.x1:
            raise ValueError('x2 must be greater than x1')
        if self.y2 <= self.y1:
            raise ValueError('y2 must be greater than y1')
        return self

class ObstacleCreate(BaseModel):
    mission_id: UUID4
    drone_id: UUID4
    object_type: ObstacleType
    confidence: float = Field(..., ge=0, le=1)
    bbox: BoundingBox
    severity: ObstacleSeverity

class ObstacleResponse(ObstacleCreate):
    id: UUID4
    timestamp: datetime

    model_config = {"from_attributes": True}

class ProofOfDeliveryCreate(BaseModel):
    receiver_name: str = Field(..., min_length=2, max_length=100)
    receiver_signature: str  # URL to signature image
    photo_url: str

class ProofOfDeliveryResponse(ProofOfDeliveryCreate):
    id: UUID4
    mission_id: UUID4
    delivered_at: datetime

    model_config = {"from_attributes": True}