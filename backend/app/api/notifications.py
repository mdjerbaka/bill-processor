"""Notification routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import NotificationListResponse, NotificationSchema
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    include_read: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List notifications."""
    svc = NotificationService(db, user.id)
    notifications = await svc.get_all(include_read=include_read)
    items = [
        NotificationSchema(
            id=n.id,
            type=n.type.value,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            related_bill_id=n.related_bill_id,
            created_at=n.created_at,
        )
        for n in notifications
    ]
    return NotificationListResponse(items=items, total=len(items))


@router.get("/count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get unread notification count."""
    svc = NotificationService(db, user.id)
    count = await svc.unread_count()
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    svc = NotificationService(db, user.id)
    notif = await svc.mark_read(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"detail": "Marked as read"}


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    svc = NotificationService(db, user.id)
    count = await svc.mark_all_read()
    await db.commit()
    return {"detail": f"Marked {count} notifications as read", "count": count}
