from pydantic import BaseModel, UUID4, Field, model_validator
from typing import List, Optional
from datetime import datetime

from app.models.order import OrderStatus

class OrderItemCreate(BaseModel):
    item_id: UUID4
    quantity: float = Field(..., gt=0)

class OrderCreate(BaseModel):
    disaster_id: UUID4
    location_id: UUID4
    supply_template_id: Optional[UUID4] = None
    people_affected: int = Field(..., gt=0)
    items: List[OrderItemCreate]

    @model_validator(mode='after')
    def check_template_or_items(self):
        if not self.supply_template_id and not self.items:
            raise ValueError("Either supply_template_id or items must be provided")
        return self

class OrderItemResponse(OrderItemCreate):
    id: UUID4
    item_name: str
    item_weight_grams: float

    model_config = {"from_attributes": True}

class OrderResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    disaster_id: UUID4
    location_id: UUID4
    status: OrderStatus
    supply_template_id: Optional[UUID4]
    people_affected: int
    created_at: datetime
    eta_minutes: Optional[int]
    total_weight_grams: float
    items: List[OrderItemResponse]

    model_config = {"from_attributes": True}

class OrderStatusUpdate(BaseModel):
    status: OrderStatus