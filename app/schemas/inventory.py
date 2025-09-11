from pydantic import BaseModel, UUID4, Field, model_validator
from typing import List, Optional
from datetime import datetime
from app.models.inventory import ItemType, UnitType

class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: ItemType
    stock_quantity: float = Field(..., ge=0)
    unit: UnitType
    weight_grams: float = Field(..., gt=0)
    images: Optional[List[str]] = []

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    stock_quantity: float = Field(..., ge=0)

class InventoryItemResponse(InventoryItemBase):
    id: UUID4
    updated_at: datetime

    model_config = {"from_attributes": True}

class TemplateItem(BaseModel):
    item_id: UUID4
    quantity: float = Field(..., gt=0)

class SupplyTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    disaster_type_id: UUID4
    items: List[TemplateItem]

    @model_validator(mode='after')
    def check_items_not_empty(self):
        if not self.items:
            raise ValueError("Supply template must contain at least one item")
        return self

class SupplyTemplateCreate(SupplyTemplateBase):
    pass

class SupplyTemplateResponse(BaseModel):
    id: UUID4
    name: str
    disaster_type_id: UUID4
    items: List[TemplateItem]
    total_weight_grams: float

    model_config = {"from_attributes": True}