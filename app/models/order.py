from sqlalchemy import Column, String, Integer, Float, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db import Base

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    disaster_id = Column(UUID(as_uuid=True), ForeignKey("disasters.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    supply_template_id = Column(UUID(as_uuid=True), ForeignKey("supply_templates.id"), nullable=True)
    people_affected = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    eta_minutes = Column(Integer, nullable=True)
    total_weight_grams = Column(Float, nullable=False)

    # Relationships
    user = relationship("User", lazy="joined")
    disaster = relationship("Disaster", lazy="joined")
    location = relationship("Location", lazy="joined")
    supply_template = relationship("SupplyTemplate", lazy="joined")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.id} - {self.status}>"

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    quantity = Column(Float, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="items")
    item = relationship("InventoryItem", lazy="joined")

    def __repr__(self):
        return f"<OrderItem {self.item_id} - {self.quantity}>"