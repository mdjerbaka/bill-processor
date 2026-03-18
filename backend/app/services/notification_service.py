"""Notification service — in-app notifications and email digests."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Notification,
    NotificationType,
    BillOccurrence,
    OccurrenceStatus,
    RecurringBill,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Manages in-app notifications and email digest generation."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def create_notification(
        self,
        type: NotificationType,
        title: str,
        message: str,
        related_bill_id: Optional[int] = None,
    ) -> Notification:
        """Create a new notification."""
        notif = Notification(
            type=type,
            title=title,
            message=message,
            related_bill_id=related_bill_id,
            user_id=self.user_id,
        )
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def get_unread(self, limit: int = 50) -> list[Notification]:
        """Get unread notifications, most recent first."""
        result = await self.db.execute(
            select(Notification)
            .where(Notification.is_read == False, Notification.user_id == self.user_id)  # noqa: E712
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all(self, include_read: bool = False, limit: int = 100) -> list[Notification]:
        """Get notifications with optional read filter."""
        q = select(Notification).where(Notification.user_id == self.user_id).order_by(Notification.created_at.desc()).limit(limit)
        if not include_read:
            q = q.where(Notification.is_read == False)  # noqa: E712
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def unread_count(self) -> int:
        """Return count of unread notifications."""
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.is_read == False,  # noqa: E712
                Notification.user_id == self.user_id,
            )
        )
        return result.scalar() or 0

    async def mark_read(self, notification_id: int) -> Optional[Notification]:
        """Mark a single notification as read."""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == self.user_id)
        )
        notif = result.scalar_one_or_none()
        if notif:
            notif.is_read = True
            await self.db.flush()
        return notif

    async def mark_all_read(self) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        result = await self.db.execute(
            select(Notification).where(Notification.is_read == False, Notification.user_id == self.user_id)  # noqa: E712
        )
        notifications = result.scalars().all()
        for n in notifications:
            n.is_read = True
        await self.db.flush()
        return len(notifications)

    # ── Notification Generation ──────────────────────────

    async def generate_due_soon_notifications(self) -> int:
        """Create notifications for bills that are due soon (not already notified)."""
        now = datetime.now(timezone.utc)
        seven_days = now + timedelta(days=7)

        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.DUE_SOON,
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= seven_days,
            )
        )
        occurrences = result.scalars().all()
        created = 0

        for occ in occurrences:
            # Check if we already notified for this occurrence
            existing = await self.db.execute(
                select(Notification).where(
                    Notification.type == NotificationType.BILL_DUE_SOON,
                    Notification.related_bill_id == occ.recurring_bill_id,
                    Notification.title.contains(occ.due_date.strftime("%Y-%m-%d")),
                    Notification.user_id == self.user_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            bill_result = await self.db.execute(
                select(RecurringBill).where(RecurringBill.id == occ.recurring_bill_id)
            )
            bill = bill_result.scalar_one_or_none()
            if not bill:
                continue

            days_until = (occ.due_date.date() - now.date()).days
            await self.create_notification(
                type=NotificationType.BILL_DUE_SOON,
                title=f"{bill.name} due {occ.due_date.strftime('%Y-%m-%d')}",
                message=f"{bill.name} (${occ.amount:,.2f}) is due in {days_until} day(s).",
                related_bill_id=bill.id,
            )
            created += 1

        return created

    async def generate_overdue_notifications(self) -> int:
        """Create notifications for overdue bills."""
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
            )
        )
        occurrences = result.scalars().all()
        created = 0

        for occ in occurrences:
            existing = await self.db.execute(
                select(Notification).where(
                    Notification.type == NotificationType.BILL_OVERDUE,
                    Notification.related_bill_id == occ.recurring_bill_id,
                    Notification.title.contains(occ.due_date.strftime("%Y-%m-%d")),
                    Notification.user_id == self.user_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            bill_result = await self.db.execute(
                select(RecurringBill).where(RecurringBill.id == occ.recurring_bill_id)
            )
            bill = bill_result.scalar_one_or_none()
            if not bill:
                continue

            await self.create_notification(
                type=NotificationType.BILL_OVERDUE,
                title=f"OVERDUE: {bill.name} was due {occ.due_date.strftime('%Y-%m-%d')}",
                message=f"{bill.name} (${occ.amount:,.2f}) is overdue!",
                related_bill_id=bill.id,
            )
            created += 1

        return created

    async def generate_credit_danger_notifications(self) -> int:
        """Create notifications for bills overdue 25+ days (credit bureau danger zone)."""
        now = datetime.now(timezone.utc)
        danger_threshold = now - timedelta(days=25)

        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
                BillOccurrence.due_date <= danger_threshold,
            )
        )
        occurrences = result.scalars().all()
        created = 0

        for occ in occurrences:
            # Check if we already sent a credit danger notification for this occurrence
            existing = await self.db.execute(
                select(Notification).where(
                    Notification.type == NotificationType.BILL_CREDIT_DANGER,
                    Notification.related_bill_id == occ.recurring_bill_id,
                    Notification.title.contains(occ.due_date.strftime("%Y-%m-%d")),
                    Notification.user_id == self.user_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            bill_result = await self.db.execute(
                select(RecurringBill).where(RecurringBill.id == occ.recurring_bill_id)
            )
            bill = bill_result.scalar_one_or_none()
            if not bill:
                continue

            days_late = (now.date() - occ.due_date.date()).days
            await self.create_notification(
                type=NotificationType.BILL_CREDIT_DANGER,
                title=f"CREDIT DANGER: {bill.name} due {occ.due_date.strftime('%Y-%m-%d')}",
                message=(
                    f"{bill.name} (${occ.amount:,.2f}) is {days_late} days overdue! "
                    f"Approaching 30-day credit bureau reporting threshold."
                ),
                related_bill_id=bill.id,
            )
            created += 1

        return created

    async def build_daily_digest_html(self) -> Optional[str]:
        """Build HTML email body for the daily digest. Returns None if nothing to report."""
        now = datetime.now(timezone.utc)
        seven_days = now + timedelta(days=7)

        # Due soon
        due_soon_result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= seven_days,
                BillOccurrence.status != OccurrenceStatus.SKIPPED,
            )
            .order_by(BillOccurrence.due_date.asc())
        )
        due_soon = due_soon_result.scalars().all()

        # Overdue
        overdue_result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
            )
            .order_by(BillOccurrence.due_date.asc())
        )
        overdue = overdue_result.scalars().all()

        if not due_soon and not overdue:
            return None

        html_parts = ["<h2>Daily Bill Digest</h2>"]

        if overdue:
            html_parts.append("<h3 style='color: #dc2626;'>Overdue Bills</h3><ul>")
            for occ in overdue:
                bill_r = await self.db.execute(
                    select(RecurringBill).where(RecurringBill.id == occ.recurring_bill_id)
                )
                bill = bill_r.scalar_one_or_none()
                name = bill.name if bill else "Unknown"
                html_parts.append(
                    f"<li><strong>{name}</strong> — ${occ.amount:,.2f} "
                    f"(due {occ.due_date.strftime('%b %d, %Y')})</li>"
                )
            html_parts.append("</ul>")

        if due_soon:
            html_parts.append("<h3>Due This Week</h3><ul>")
            for occ in due_soon:
                bill_r = await self.db.execute(
                    select(RecurringBill).where(RecurringBill.id == occ.recurring_bill_id)
                )
                bill = bill_r.scalar_one_or_none()
                name = bill.name if bill else "Unknown"
                days = (occ.due_date.date() - now.date()).days
                html_parts.append(
                    f"<li><strong>{name}</strong> — ${occ.amount:,.2f} "
                    f"(due in {days} day(s), {occ.due_date.strftime('%b %d')})</li>"
                )
            html_parts.append("</ul>")

        html_parts.append("<p><em>— Bill Processor</em></p>")
        return "\n".join(html_parts)
