from sqlalchemy import Column, String, Float, Enum, DateTime, ForeignKey, Integer, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db import Base
from app.models.drone import Mission, MissionStatus

class ObstacleType(str, enum.Enum):
    TREE = "tree"
    BUILDING = "building"
    POWER_LINE = "power_line"
    BIRD = "bird"
    AIRCRAFT = "aircraft"
    OTHER = "other"

class ObstacleSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TelemetryStatus(str, enum.Enum):
    NOMINAL = "nominal"
    WARNING = "warning"
    CRITICAL = "critical"

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=False)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    lat = Column(DECIMAL(9, 6), nullable=False)
    lon = Column(DECIMAL(9, 6), nullable=False)
    alt = Column(Float, nullable=False)  # Altitude in meters
    pitch = Column(Float, nullable=False)  # Degrees
    roll = Column(Float, nullable=False)  # Degrees
    yaw = Column(Float, nullable=False)  # Degrees
    battery_level = Column(Float, nullable=False)  # Percentage
    status = Column(Enum(TelemetryStatus), nullable=False, default=TelemetryStatus.NOMINAL)

    # Relationships
    mission = relationship("Mission")
    drone = relationship("Drone")

    def __repr__(self):
        return f"<Telemetry {self.drone_id} @ {self.timestamp}>"

class Obstacle(Base):
    __tablename__ = "obstacles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=False)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    object_type = Column(Enum(ObstacleType), nullable=False)
    confidence = Column(Float, nullable=False)  # Detection confidence (0-1)
    bbox = Column(JSONB, nullable=False)  # Bounding box coordinates
    severity = Column(Enum(ObstacleSeverity), nullable=False)

    # Relationships
    mission = relationship("Mission")
    drone = relationship("Drone")

    def __repr__(self):
        return f"<Obstacle {self.object_type} @ {self.timestamp}>"

class ProofOfDelivery(Base):
    __tablename__ = "proof_of_delivery"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), unique=True, nullable=False)
    delivered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    receiver_name = Column(String, nullable=False)
    receiver_signature = Column(String, nullable=False)  # URL to signature image
    photo_url = Column(String, nullable=False)

    # Relationships
    mission = relationship("Mission")