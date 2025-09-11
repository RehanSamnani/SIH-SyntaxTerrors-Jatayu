from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db import Base

class ItemType(str, enum.Enum):
    MEDICAL = "medical"
    FOOD = "food"
    WATER = "water"
    SHELTER = "shelter"
    CLOTHING = "clothing"
    TOOL = "tool"
    COMMUNICATION = "communication"
    OTHER = "other"

class UnitType(str, enum.Enum):
    PIECE = "piece"
    KG = "kg"
    LITER = "liter"
    PACK = "pack"
    BOX = "box"

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(Enum(ItemType), nullable=False)
    stock_quantity = Column(Float, nullable=False, default=0)
    unit = Column(Enum(UnitType), nullable=False)
    weight_grams = Column(Float, nullable=False)
    images = Column(JSON, default=list)  # List of image URLs
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InventoryItem {self.name} - {self.stock_quantity} {self.unit}>"

class SupplyTemplate(Base):
    __tablename__ = "supply_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    disaster_type_id = Column(UUID(as_uuid=True), ForeignKey("disaster_types.id"), nullable=False)
    items_json = Column(JSONB, nullable=False)  # List of {item_id, quantity}
    total_weight_grams = Column(Float, nullable=False)

    # Relationships
    disaster_type = relationship("DisasterType", back_populates="supply_templates")

    def __repr__(self):
        return f"<SupplyTemplate {self.name} - {self.total_weight_grams}g>"

# Add relationship to DisasterType model
from app.models.disaster import DisasterType
DisasterType.supply_templates = relationship("SupplyTemplate", back_populates="disaster_type")