from pydantic import BaseModel, Field, UUID4, model_validator
from datetime import datetime
from typing import Optional, List
from app.models.disaster import DisasterStatus

class DisasterTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    image: Optional[str] = None

class DisasterTypeCreate(DisasterTypeBase):
    pass

class DisasterTypeResponse(DisasterTypeBase):
    id: UUID4

    model_config = {"from_attributes": True}

class DisasterBase(BaseModel):
    disaster_type_id: UUID4
    description: str
    status: DisasterStatus = DisasterStatus.REPORTED

class DisasterCreate(DisasterBase):
    pass

class DisasterResponse(DisasterBase):
    id: UUID4
    reported_at: datetime
    created_by: UUID4
    disaster_type: DisasterTypeResponse

    model_config = {"from_attributes": True}

class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    pre_defined: bool = False

    @model_validator(mode='after')
    def validate_coordinates(self):
        if not -90 <= self.latitude <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        if not -180 <= self.longitude <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return self

class LocationCreate(LocationBase):
    disaster_id: UUID4

class LocationResponse(LocationBase):
    id: UUID4
    disaster_id: UUID4

    model_config = {"from_attributes": True}

class DisasterWithLocations(DisasterResponse):
    locations: List[LocationResponse]

    model_config = {"from_attributes": True}