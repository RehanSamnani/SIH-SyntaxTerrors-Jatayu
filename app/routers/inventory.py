from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from typing import List
from uuid import UUID

from app.db import get_db
from app.models.inventory import InventoryItem, SupplyTemplate
from app.models.user import UserRole
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    SupplyTemplateCreate,
    SupplyTemplateResponse
)
from app.utils.auth import get_current_user, check_role

router = APIRouter(tags=["inventory"])

@router.post("/inventory", response_model=InventoryItemResponse)
async def create_inventory_item(
    item: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN))
):
    db_item = InventoryItem(**item.dict())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

@router.put("/inventory/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: UUID,
    item_update: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN))
):
    result = await db.execute(
        select(InventoryItem).filter(InventoryItem.id == item_id)
    )
    db_item = result.scalar_one_or_none()
    
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    for field, value in item_update.dict(exclude_unset=True).items():
        setattr(db_item, field, value)
    
    await db.commit()
    await db.refresh(db_item)
    return db_item

@router.get("/inventory", response_model=List[InventoryItemResponse])
async def list_inventory_items(
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(select(InventoryItem))
    return result.scalars().all()

@router.post("/supply-templates", response_model=SupplyTemplateResponse)
async def create_supply_template(
    template: SupplyTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(check_role(UserRole.ADMIN))
):
    # Verify all items exist and calculate total weight
    total_weight = 0
    items_to_check = {item.item_id: item.quantity for item in template.items}
    
    result = await db.execute(
        select(InventoryItem)
        .filter(InventoryItem.id.in_(items_to_check.keys()))
    )
    found_items = result.scalars().all()
    
    if len(found_items) != len(items_to_check):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more items not found in inventory"
        )
    
    # Calculate total weight
    for item in found_items:
        total_weight += item.weight_grams * items_to_check[item.id]
    
    # Create template
    db_template = SupplyTemplate(
        name=template.name,
        disaster_type_id=template.disaster_type_id,
        items_json=[item.dict() for item in template.items],
        total_weight_grams=total_weight
    )
    
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    return db_template

@router.get("/supply-templates/{disaster_type_id}", response_model=List[SupplyTemplateResponse])
async def list_supply_templates(
    disaster_type_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user = Depends(get_current_user)
):
    result = await db.execute(
        select(SupplyTemplate)
        .filter(SupplyTemplate.disaster_type_id == disaster_type_id)
    )
    return result.scalars().all()