from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db import Base

class DisasterStatus(str, enum.Enum):
    REPORTED = "reported"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"

class DisasterType(Base):
    __tablename__ = "disaster_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    image = Column(String)  # URL to image
    
    # Relationships
    disasters = relationship("Disaster", back_populates="disaster_type")

    def __repr__(self):
        return f"<DisasterType {self.name}>"

class Disaster(Base):
    __tablename__ = "disasters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disaster_type_id = Column(UUID(as_uuid=True), ForeignKey("disaster_types.id"), nullable=False)
    description = Column(Text, nullable=False)
    reported_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(DisasterStatus), nullable=False, default=DisasterStatus.REPORTED)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    disaster_type = relationship("DisasterType", back_populates="disasters")
    creator = relationship("User")
    locations = relationship("Location", back_populates="disaster")

    def __repr__(self):
        return f"<Disaster {self.id} - {self.status}>"

class Location(Base):
    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    pre_defined = Column(Boolean, default=False)
    disaster_id = Column(UUID(as_uuid=True), ForeignKey("disasters.id"), nullable=False)
    
    # Relationships
    disaster = relationship("Disaster", back_populates="locations")

    def __repr__(self):
        return f"<Location {self.name} ({self.latitude}, {self.longitude})>"