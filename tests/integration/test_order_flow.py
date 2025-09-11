import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from app.models.user import User, UserRole
from app.models.drone import Drone, DroneStatus
from app.models.inventory import InventoryItem, ItemType, UnitType
from app.models.disaster import DisasterType, Disaster, DisasterStatus
from app.models.order import Order, OrderStatus

# Test data
TEST_ADMIN = {
    "email": "admin@test.com",
    "password": "adminpass123",
    "name": "Test Admin",
    "role": UserRole.ADMIN
}

TEST_DRONE = {
    "identifier": "TEST-DRONE-001",
    "payload_capacity_grams": 5000
}

TEST_INVENTORY_ITEM = {
    "name": "Water Bottle",
    "type": ItemType.WATER,
    "stock_quantity": 100,
    "unit": UnitType.PIECE,
    "weight_grams": 1000
}

@pytest.fixture
async def admin_token(async_client: AsyncClient):
    # Register admin user
    response = await async_client.post("/auth/register", json=TEST_ADMIN)
    assert response.status_code == 200
    
    # Login
    login_response = await async_client.post(
        "/auth/login",
        data={
            "username": TEST_ADMIN["email"],
            "password": TEST_ADMIN["password"]
        }
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]

@pytest.fixture
async def test_drone(async_client: AsyncClient, admin_token: str):
    response = await async_client.post(
        "/drones",
        json=TEST_DRONE,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    return response.json()

@pytest.fixture
async def test_inventory(async_client: AsyncClient, admin_token: str):
    response = await async_client.post(
        "/inventory",
        json=TEST_INVENTORY_ITEM,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    return response.json()

@pytest.mark.asyncio
async def test_complete_order_flow(
    async_client: AsyncClient,
    admin_token: str,
    test_drone,
    test_inventory
):
    # 1. Create disaster type
    disaster_type_data = {
        "name": "Flood",
        "description": "Flooding disaster"
    }
    response = await async_client.post(
        "/disaster-types",
        json=disaster_type_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    disaster_type = response.json()

    # 2. Create disaster
    disaster_data = {
        "disaster_type_id": disaster_type["id"],
        "description": "Test disaster",
        "status": DisasterStatus.ACTIVE
    }
    response = await async_client.post(
        "/disasters",
        json=disaster_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    disaster = response.json()

    # 3. Create location
    location_data = {
        "name": "Test Location",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "disaster_id": disaster["id"]
    }
    response = await async_client.post(
        "/locations",
        json=location_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    location = response.json()

    # 4. Create order
    order_data = {
        "disaster_id": disaster["id"],
        "location_id": location["id"],
        "people_affected": 50,
        "items": [
            {
                "item_id": test_inventory["id"],
                "quantity": 2
            }
        ]
    }
    response = await async_client.post(
        "/orders",
        json=order_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    order = response.json()

    # 5. Create mission
    mission_data = {
        "order_id": order["id"],
        "drone_id": test_drone["id"],
        "waypoints": [
            {
                "lat": location_data["latitude"],
                "lon": location_data["longitude"],
                "alt": 100,
                "hold_time": 30
            }
        ]
    }
    response = await async_client.post(
        "/missions",
        json=mission_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    mission = response.json()

    # 6. Update mission status to in_progress
    response = await async_client.put(
        f"/missions/{mission['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # 7. Upload telemetry
    telemetry_data = {
        "mission_id": mission["id"],
        "drone_id": test_drone["id"],
        "lat": location_data["latitude"],
        "lon": location_data["longitude"],
        "alt": 100,
        "pitch": 0,
        "roll": 0,
        "yaw": 0,
        "battery_level": 90,
        "status": "nominal"
    }
    response = await async_client.post(
        "/telemetry",
        json=telemetry_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # 8. Complete delivery with proof
    proof_data = {
        "receiver_name": "John Doe",
        "receiver_signature": "https://example.com/signature.png",
        "photo_url": "https://example.com/photo.jpg"
    }
    response = await async_client.post(
        f"/proof/{mission['id']}",
        json=proof_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # 9. Verify final states
    response = await async_client.get(
        f"/missions/{mission['id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    final_mission = response.json()
    assert final_mission["status"] == "completed"