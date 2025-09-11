import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Import all models
from app.models.user import User
from app.models.disaster import DisasterType, Disaster, Location
from app.models.inventory import InventoryItem, SupplyTemplate
from app.models.order import Order, OrderItem
from app.models.drone import Drone, Mission, Waypoint, DroneHealthLog
from app.models.telemetry import Telemetry, Obstacle, ProofOfDelivery
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

async def create_tables():
    # Create async engine
    engine = create_async_engine(database_url)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Close engine
    await engine.dispose()

    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())