from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import List, Optional
from uuid import UUID

from app.db import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User, UserRole
from app.models.inventory import InventoryItem, SupplyTemplate
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.utils.auth import get_current_user, check_role
from app.config.drone import drone_settings

router = APIRouter(tags=["orders"])

async def calculate_total_weight(db: AsyncSession, items: List[dict]) -> float:
    """Calculate total weight for given items."""
    total_weight = 0
    item_ids = [item["item_id"] for item in items]
    
    result = await db.execute(
        select(InventoryItem).filter(InventoryItem.id.in_(item_ids))
    )
    inventory_items = {item.id: item for item in result.scalars().all()}
    
    for item in items:
        if item["item_id"] not in inventory_items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item['item_id']} not found"
            )
        total_weight += inventory_items[item["item_id"]].weight_grams * item["quantity"]
    
    return total_weight

@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # If supply template is provided, use its items
    items_to_order = []
    if order.supply_template_id:
        result = await db.execute(
            select(SupplyTemplate).filter(SupplyTemplate.id == order.supply_template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supply template not found"
            )
        items_to_order = template.items_json
        total_weight = template.total_weight_grams
    else:
        items_to_order = [item.dict() for item in order.items]
        total_weight = await calculate_total_weight(db, items_to_order)
    
    # Check payload capacity
    if total_weight > drone_settings.MAX_PAYLOAD_GRAMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total weight {total_weight}g exceeds drone payload capacity of {drone_settings.MAX_PAYLOAD_GRAMS}g"
        )
    
    # Create order
    db_order = Order(
        user_id=current_user.id,
        disaster_id=order.disaster_id,
        location_id=order.location_id,
        supply_template_id=order.supply_template_id,
        people_affected=order.people_affected,
        total_weight_grams=total_weight
    )
    db.add(db_order)
    
    # Create order items
    for item in items_to_order:
        db_item = OrderItem(
            order=db_order,
            item_id=item["item_id"],
            quantity=item["quantity"]
        )
        db.add(db_item)
    
    await db.commit()
    await db.refresh(db_order)
    return db_order

@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = None,
    disaster_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = select(Order).options(
        joinedload(Order.items).joinedload(OrderItem.item)
    )
    
    # Apply filters
    if status:
        query = query.filter(Order.status == status)
    if disaster_id:
        query = query.filter(Order.disaster_id == disaster_id)
    
    # Non-admin users can only see their own orders
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        query = query.filter(Order.user_id == current_user.id)
    
    result = await db.execute(query)
    return result.unique().scalars().all()

@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = select(Order).options(
        joinedload(Order.items).joinedload(OrderItem.item)
    ).filter(Order.id == order_id)
    
    # Non-admin users can only see their own orders
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        query = query.filter(Order.user_id == current_user.id)
    
    result = await db.execute(query)
    order = result.unique().scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return order

@router.put("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    status_update: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(check_role(UserRole.ADMIN, UserRole.DISPATCHER))
):
    result = await db.execute(
        select(Order).options(
            joinedload(Order.items).joinedload(OrderItem.item)
        ).filter(Order.id == order_id)
    )
    order = result.unique().scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Update status
    order.status = status_update.status
    await db.commit()
    await db.refresh(order)
    
    return order