from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ── Helpers ──────────────────────────────────────────────
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────
class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    AUTO_MATCHED = "auto_matched"
    APPROVED = "approved"
    SENT_TO_QB = "sent_to_qb"
    PAID = "paid"
    FAILED = "failed"


class PayableStatus(str, enum.Enum):
    OUTSTANDING = "outstanding"
    SCHEDULED = "scheduled"
    PAID = "paid"
    OVERDUE = "overdue"


class JobSource(str, enum.Enum):
    MANUAL = "manual"
    BUILDERTREND_CSV = "buildertrend_csv"
    QUICKBOOKS = "quickbooks"


class BillFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    BIENNIAL = "biennial"
    CUSTOM = "custom"


class BillCategory(str, enum.Enum):
    MORTGAGE = "mortgage"
    VEHICLE = "vehicle"
    ELECTRIC = "electric"
    WATER = "water"
    SEWER = "sewer"
    INTERNET = "internet"
    VEHICLE_INSURANCE = "vehicle_insurance"
    HEALTH_INSURANCE = "health_insurance"
    LIABILITY_INSURANCE = "liability_insurance"
    LIFE_INSURANCE = "life_insurance"
    CREDIT_CARD = "credit_card"
    BOOKKEEPER = "bookkeeper"
    LOAN = "loan"
    SUBSCRIPTION = "subscription"
    TRASH = "trash"
    PHONE = "phone"
    WORKERS_COMP = "workers_comp"
    CPA = "cpa"
    TAXES = "taxes"
    REGISTRATION = "registration"
    LICENSE = "license"
    PAYROLL = "payroll"
    SUBCONTRACTOR = "subcontractor"
    OTHER = "other"


class OccurrenceStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    SKIPPED = "skipped"
    PAID = "paid"


class NotificationType(str, enum.Enum):
    BILL_DUE_SOON = "bill_due_soon"
    BILL_OVERDUE = "bill_overdue"
    BILL_CREDIT_DANGER = "bill_credit_danger"
    DAILY_DIGEST = "daily_digest"
    BALANCE_LOW = "balance_low"
    EMAIL_NO_ATTACHMENT = "email_no_attachment"


class PaymentMethod(str, enum.Enum):
    CHECK = "check"
    ACH = "ach"
    DEBIT = "debit"
    ONLINE = "online"
    WIRE = "wire"
    OTHER = "other"


class PaymentOutStatus(str, enum.Enum):
    OUTSTANDING = "outstanding"
    CLEARED = "cleared"


# ── User ─────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Email ────────────────────────────────────────────────
class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(500), unique=True, nullable=True)
    from_address: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(1000))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    attachments: Mapped[List["Attachment"]] = relationship(back_populates="email", cascade="all, delete-orphan")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="email", cascade="all, delete-orphan")


# ── Attachment ───────────────────────────────────────────
class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[int]] = mapped_column(ForeignKey("emails.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    email: Mapped["Email"] = relationship(back_populates="attachments")


# ── Invoice ──────────────────────────────────────────────
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email_id: Mapped[Optional[int]] = mapped_column(ForeignKey("emails.id"), nullable=True)
    attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"), nullable=True)

    # Extracted fields
    vendor_name: Mapped[Optional[str]] = mapped_column(String(500))
    vendor_address: Mapped[Optional[str]] = mapped_column(Text)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(200))
    invoice_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Optional[float]] = mapped_column(Float)
    subtotal: Mapped[Optional[float]] = mapped_column(Float)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float)

    # Full extracted JSON for reference
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)

    # Matching
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    match_method: Mapped[Optional[str]] = mapped_column(String(50))  # auto, ai, manual

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # QuickBooks
    qbo_bill_id: Mapped[Optional[str]] = mapped_column(String(100))
    qbo_vendor_id: Mapped[Optional[str]] = mapped_column(String(100))
    qbo_payment_id: Mapped[Optional[str]] = mapped_column(String(100))

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Soft-delete (junk bin)
    is_junked: Mapped[bool] = mapped_column(Boolean, default=False)
    junked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    email: Mapped[Optional["Email"]] = relationship(back_populates="invoices")
    job: Mapped[Optional["Job"]] = relationship(back_populates="invoices")
    line_items: Mapped[List["InvoiceLineItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    payable: Mapped[Optional["Payable"]] = relationship(back_populates="invoice", uselist=False)


# ── Invoice Line Item ────────────────────────────────────
class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[float]] = mapped_column(Float)
    unit_price: Mapped[Optional[float]] = mapped_column(Float)
    amount: Mapped[Optional[float]] = mapped_column(Float)
    product_code: Mapped[Optional[str]] = mapped_column(String(100))

    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")


# ── Job ──────────────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    source: Mapped[JobSource] = mapped_column(Enum(JobSource), default=JobSource.MANUAL)
    external_id: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_junked: Mapped[bool] = mapped_column(Boolean, default=False)
    junked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="job")
    vendor_mappings: Mapped[List["VendorJobMapping"]] = relationship(back_populates="job")


# ── Vendor → Job Mapping ────────────────────────────────
class VendorJobMapping(Base):
    __tablename__ = "vendor_job_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_name_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=False)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["Job"] = relationship(back_populates="vendor_mappings")


# ── Payable ──────────────────────────────────────────────
class Payable(Base):
    __tablename__ = "payables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), unique=True, nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[PayableStatus] = mapped_column(
        Enum(PayableStatus), default=PayableStatus.OUTSTANDING
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False)
    included_in_cashflow: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    is_junked: Mapped[bool] = mapped_column(Boolean, default=False)
    junked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Denormalized fields (copied from Invoice/Job before invoice deletion)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    job_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qbo_bill_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    qbo_vendor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attachment_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    attachment_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payable")


# ── App Settings (key-value store) ───────────────────────
class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("key", "user_id", name="uq_app_settings_key_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── QuickBooks Tokens ────────────────────────────────────
class QBOToken(Base):
    __tablename__ = "qbo_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    realm_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── Microsoft 365 Tokens ────────────────────────────────
class MSGraphToken(Base):
    __tablename__ = "ms_graph_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    email_address: Mapped[Optional[str]] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── Recurring Bill ───────────────────────────────────────
class RecurringBill(Base):
    __tablename__ = "recurring_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    frequency: Mapped[BillFrequency] = mapped_column(Enum(BillFrequency), nullable=False)
    due_day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    due_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[BillCategory] = mapped_column(Enum(BillCategory), default=BillCategory.OTHER)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_auto_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_days_before: Mapped[int] = mapped_column(Integer, default=7)
    custom_months: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # e.g. [1,4,8,10] for custom frequency
    included_in_cashflow: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    occurrences: Mapped[List["BillOccurrence"]] = relationship(back_populates="recurring_bill", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="recurring_bill")


# ── Bill Occurrence ──────────────────────────────────────
class BillOccurrence(Base):
    __tablename__ = "bill_occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recurring_bill_id: Mapped[int] = mapped_column(ForeignKey("recurring_bills.id"), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(OccurrenceStatus), default=OccurrenceStatus.UPCOMING
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    matched_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    included_in_cashflow: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    recurring_bill: Mapped["RecurringBill"] = relationship(back_populates="occurrences")


# ── Notification ─────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_bill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recurring_bills.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    recurring_bill: Mapped[Optional["RecurringBill"]] = relationship(back_populates="notifications")


# ── Receivable Check ─────────────────────────────────────
class ReceivableCheck(Base):
    __tablename__ = "receivable_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    job_name: Mapped[str] = mapped_column(String(500), nullable=False)
    invoiced_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    collect: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qbo_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── Payment Out (Check Register) ─────────────────────────
class PaymentOut(Base):
    __tablename__ = "payments_out"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), default=PaymentMethod.OTHER)
    check_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(500), nullable=False)
    job_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[PaymentOutStatus] = mapped_column(Enum(PaymentOutStatus), default=PaymentOutStatus.OUTSTANDING)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payable_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payables.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── Vendor Account (Top Vendor Accounts) ─────────────────
class VendorAccount(Base):
    __tablename__ = "vendor_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    vendor_name: Mapped[str] = mapped_column(String(500), nullable=False)
    account_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    as_of_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes_due_dates: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    included_in_cashflow: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
