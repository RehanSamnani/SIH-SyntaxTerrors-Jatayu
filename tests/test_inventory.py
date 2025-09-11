import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import InventoryItem, ItemType, UnitType, SupplyTemplate
from app.models.disaster import DisasterType
from app.models.user import User, UserRole
from app.utils.auth import create_access_token

# Test data
TEST_ADMIN = {
    "email": "admin@test.com",
    "password": "adminpass123",
    "name": "Test Admin",
    "role": UserRole.ADMIN
}

TEST_ITEMS = [
    {
        "name": "Water Bottle",
        "type": ItemType.WATER,
        "stock_quantity": 100,
        "unit": UnitType.PIECE,
        "weight_grams": 1000
    },
    {
        "name": "First Aid Kit",
        "type": ItemType.MEDICAL,
        "stock_quantity": 50,
        "unit": UnitType.PACK,
        "weight_grams": 500
    }
]

@pytest.fixture
async def admin_token(async_client: AsyncClient):
    # Register admin user
    response = await async_client.post("/auth/register", json=TEST_ADMIN)
    assert response.status_code == 200
    admin_data = response.json()
    
    # Login to get token
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
async def disaster_type(db: AsyncSession):
    disaster_type = DisasterType(
        name="Flood",
        description="Flooding disaster type"
    )
    db.add(disaster_type)
    await db.commit()
    await db.refresh(disaster_type)
    return disaster_type

@pytest.fixture
async def inventory_items(async_client: AsyncClient, admin_token: str):
    items = []
    for item_data in TEST_ITEMS:
        response = await async_client.post(
            "/inventory",
            json=item_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        items.append(response.json())
    return items

@pytest.mark.asyncio
async def test_supply_template_weight_calculation(
    async_client: AsyncClient,
    admin_token: str,
    disaster_type,
    inventory_items
):
    # Create template with items
    template_data = {
        "name": "Basic Relief Pack",
        "disaster_type_id": str(disaster_type.id),
        "items": [
            {
                "item_id": items["id"],
                "quantity": 2
            } for items in inventory_items
        ]
    }
    
    response = await async_client.post(
        "/supply-templates",
        json=template_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    template = response.json()
    
    # Calculate expected total weight
    expected_weight = sum(
        item["weight_grams"] * 2  # quantity is 2 for each item
        for item in TEST_ITEMS
    )
    
    assert template["total_weight_grams"] == expected_weight

@pytest.mark.asyncio
async def test_supply_template_with_invalid_items(
    async_client: AsyncClient,
    admin_token: str,
    disaster_type
):
    # Try to create template with non-existent items
    template_data = {
        "name": "Invalid Template",
        "disaster_type_id": str(disaster_type.id),
        "items": [
            {
                "item_id": str(uuid.uuid4()),
                "quantity": 1
            }
        ]
    }
    
    response = await async_client.post(
        "/supply-templates",
        json=template_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400
    assert "items not found" in response.json()["detail"].lower()