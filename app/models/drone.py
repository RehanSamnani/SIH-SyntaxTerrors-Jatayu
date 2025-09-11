from sqlalchemy import Column, String, Float, Integer, Enum, DateTime, ForeignKey, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db import Base

class DroneStatus(str, enum.Enum):
    IDLE = "idle"
    IN_MISSION = "in_mission"
    MAINTENANCE = "maintenance"
    ERROR = "error"

class MissionStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Drone(Base):
    __tablename__ = "drones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String, unique=True, nullable=False)
    payload_capacity_grams = Column(Float, nullable=False)
    status = Column(Enum(DroneStatus), nullable=False, default=DroneStatus.IDLE)
    last_telemetry = Column(JSONB, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # Relationships
    missions = relationship("Mission", back_populates="drone")
    health_logs = relationship("DroneHealthLog", back_populates="drone")

    def __repr__(self):
        return f"<Drone {self.identifier} - {self.status}>"

class DroneHealthLog(Base):
    __tablename__ = "drone_health_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    health_status = Column(String, nullable=False)
    battery_percent = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    drone = relationship("Drone", back_populates="health_logs")

    def __repr__(self):
        return f"<DroneHealthLog {self.drone_id} - {self.health_status}>"

class Mission(Base):
    __tablename__ = "missions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    status = Column(Enum(MissionStatus), nullable=False, default=MissionStatus.ASSIGNED)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    command_log = Column(JSONB, nullable=True, default=list)

    # Relationships
    drone = relationship("Drone", back_populates="missions")
    order = relationship("Order")
    waypoints = relationship("Waypoint", back_populates="mission", order_by="Waypoint.sequence_order")

    def __repr__(self):
        return f"<Mission {self.id} - {self.status}>"

class Waypoint(Base):
    __tablename__ = "waypoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=False)
    lat = Column(DECIMAL(9, 6), nullable=False)
    lon = Column(DECIMAL(9, 6), nullable=False)
    alt = Column(Float, nullable=False)  # Altitude in meters
    hold_time = Column(Integer, default=0)  # Hold time in seconds
    sequence_order = Column(Integer, nullable=False)

    # Relationships
    mission = relationship("Mission", back_populates="waypoints")

    def __repr__(self):
        return f"<Waypoint {self.sequence_order} ({self.lat}, {self.lon}, {self.alt}m)>"