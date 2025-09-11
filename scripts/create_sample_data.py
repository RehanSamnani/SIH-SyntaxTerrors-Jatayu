import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Import models and enums
from app.models.user import User, UserRole
from app.models.disaster import DisasterType, Disaster, DisasterStatus
from app.models.inventory import InventoryItem, ItemType, UnitType
from app.models.drone import Drone, DroneStatus
from app.db import Base

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv("DATABASE_URL")
if database_url is None:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert regular Postgres URL to async format
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

async def create_sample_data():
    # Create async engine
    engine = create_async_engine(database_url)
    
    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        # Create admin user
        admin_user = User(
            email="admin@example.com",
            name="Admin User",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LedYQNB8UHUHzh5.W",  # password: admin123
            role=UserRole.ADMIN
        )
        session.add(admin_user)

        # Create disaster types
        disaster_types = [
            DisasterType(name="Flood", description="Flooding and water-related disasters"),
            DisasterType(name="Earthquake", description="Seismic activity and aftermaths"),
            DisasterType(name="Fire", description="Wild fires and urban fires")
        ]
        for dt in disaster_types:
            session.add(dt)

        # Create inventory items
        inventory_items = [
            InventoryItem(
                name="Water Bottle",
                type=ItemType.WATER,
                stock_quantity=1000,
                unit=UnitType.PIECE,
                weight_grams=500
            ),
            InventoryItem(
                name="First Aid Kit",
                type=ItemType.MEDICAL,
                stock_quantity=100,
                unit=UnitType.PACK,
                weight_grams=1000
            ),
            InventoryItem(
                name="Emergency Food Pack",
                type=ItemType.FOOD,
                stock_quantity=500,
                unit=UnitType.PACK,
                weight_grams=1500
            )
        ]
        for item in inventory_items:
            session.add(item)

        # Create drones
        drones = [
            Drone(
                identifier="DRONE-001",
                payload_capacity_grams=5000,
                status=DroneStatus.IDLE
            ),
            Drone(
                identifier="DRONE-002",
                payload_capacity_grams=3000,
                status=DroneStatus.IDLE
            )
        ]
        for drone in drones:
            session.add(drone)

        # Commit all changes
        await session.commit()

        print("Sample data created successfully!")

    # Close engine
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_sample_data())