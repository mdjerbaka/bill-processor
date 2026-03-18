from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


# ── Email Config ─────────────────────────────────────────
class EmailConfigRequest(BaseModel):
    imap_host: str
    imap_port: int = 993
    imap_username: str
    imap_password: str
    use_ssl: bool = True


class EmailConfigResponse(BaseModel):
    imap_host: str
    imap_port: int
    imap_username: str
    use_ssl: bool
    is_connected: bool = False


# ── OCR / API Keys ───────────────────────────────────────
class OCRConfigRequest(BaseModel):
    ocr_provider: str = "openai"  # openai | azure | aws | none
    openai_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_api_key: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None


class OCRConfigResponse(BaseModel):
    ocr_provider: str
    openai_key_set: bool = False
    azure_endpoint: Optional[str] = None
    azure_key_set: bool = False
    aws_key_set: bool = False
    aws_region: Optional[str] = None


# ── Invoice / Bill ───────────────────────────────────────
class InvoiceLineItemSchema(BaseModel):
    id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    product_code: Optional[str] = None


class InvoiceSchema(BaseModel):
    id: int
    email_id: Optional[int] = None
    attachment_id: Optional[int] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    total_amount: Optional[float] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    confidence_score: Optional[float] = None
    job_id: Optional[int] = None
    job_name: Optional[str] = None
    match_method: Optional[str] = None
    status: str
    qbo_bill_id: Optional[str] = None
    qbo_payment_id: Optional[str] = None
    error_message: Optional[str] = None
    line_items: List[InvoiceLineItemSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceUpdateRequest(BaseModel):
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    total_amount: Optional[float] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    job_id: Optional[int] = None
    line_items: Optional[List[InvoiceLineItemSchema]] = None


class InvoiceListResponse(BaseModel):
    items: List[InvoiceSchema]
    total: int
    page: int
    page_size: int


# ── Job ──────────────────────────────────────────────────
class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    code: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None


class JobSchema(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    source: str
    external_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    items: List[JobSchema]
    total: int


# ── Vendor → Job Mapping ────────────────────────────────
class VendorJobMappingCreate(BaseModel):
    vendor_name_pattern: str
    job_id: int
    auto_assign: bool = False


class VendorJobMappingSchema(BaseModel):
    id: int
    vendor_name_pattern: str
    job_id: int
    job_name: Optional[str] = None
    auto_assign: bool
    match_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Payable ──────────────────────────────────────────────
class PayableSchema(BaseModel):
    id: int
    invoice_id: Optional[int] = None
    vendor_name: str
    amount: float
    due_date: Optional[datetime] = None
    status: str
    paid_at: Optional[datetime] = None
    created_at: datetime
    invoice_number: Optional[str] = None
    job_name: Optional[str] = None
    is_permanent: bool = False

    class Config:
        from_attributes = True


class PayableListResponse(BaseModel):
    items: List[PayableSchema]
    total: int
    total_outstanding: float
    total_overdue: float


class BankBalanceRequest(BaseModel):
    bank_balance: float


class PayableCreateRequest(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=500)
    amount: float
    due_date: Optional[datetime] = None
    status: Optional[str] = "outstanding"
    invoice_number: Optional[str] = None
    is_permanent: Optional[bool] = False


class PayableUpdateRequest(BaseModel):
    vendor_name: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    invoice_number: Optional[str] = None
    is_permanent: Optional[bool] = None


class InvoiceCreateRequest(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=500)
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    total_amount: Optional[float] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    job_id: Optional[int] = None
    line_items: Optional[List[InvoiceLineItemSchema]] = None


class RealBalanceResponse(BaseModel):
    bank_balance: float
    total_outstanding: float
    buffer: float = 0.0
    real_available: float


class BufferRequest(BaseModel):
    buffer: float


# ── Job Match Suggestion ─────────────────────────────────
class JobMatchSuggestion(BaseModel):
    job_id: int
    job_name: str
    confidence: float
    reason: str


# ── Health Check ─────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    last_email_poll: Optional[datetime] = None
    db_connected: bool
    redis_connected: bool


# ── Setup Status ─────────────────────────────────────────
class SetupStatusResponse(BaseModel):
    is_setup_complete: bool
    has_user: bool
    has_email_config: bool
    has_qbo_connection: bool
    has_jobs: bool


# ── Recurring Bills ──────────────────────────────────────
class RecurringBillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    vendor_name: str = Field(min_length=1, max_length=500)
    amount: float = Field(gt=0)
    frequency: str  # weekly, monthly, quarterly, semi_annual, annual, biennial
    due_day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    due_month: Optional[int] = Field(default=None, ge=1, le=12)
    category: str = "other"
    notes: Optional[str] = None
    is_auto_pay: bool = False
    alert_days_before: int = Field(default=7, ge=1, le=90)


class RecurringBillUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=500)
    vendor_name: Optional[str] = Field(default=None, max_length=500)
    amount: Optional[float] = Field(default=None, gt=0)
    frequency: Optional[str] = None
    due_day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    due_month: Optional[int] = Field(default=None, ge=1, le=12)
    category: Optional[str] = None
    notes: Optional[str] = None
    is_auto_pay: Optional[bool] = None
    alert_days_before: Optional[int] = Field(default=None, ge=1, le=90)


class RecurringBillSchema(BaseModel):
    id: int
    name: str
    vendor_name: str
    amount: float
    frequency: str
    due_day_of_month: Optional[int] = None
    due_month: Optional[int] = None
    category: str
    notes: Optional[str] = None
    is_auto_pay: bool
    is_active: bool
    next_due_date: Optional[datetime] = None
    alert_days_before: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecurringBillListResponse(BaseModel):
    items: List[RecurringBillSchema]
    total: int


class BillOccurrenceSchema(BaseModel):
    id: int
    recurring_bill_id: int
    due_date: datetime
    amount: float
    status: str
    notes: Optional[str] = None
    bill_name: Optional[str] = None
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    is_auto_pay: Optional[bool] = None
    paid_at: Optional[datetime] = None
    matched_invoice_id: Optional[int] = None
    days_overdue: Optional[int] = None
    included_in_cashflow: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class BillOccurrenceListResponse(BaseModel):
    items: List[BillOccurrenceSchema]
    total: int


class NotificationSchema(BaseModel):
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    related_bill_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationSchema]
    total: int


class CashFlowSummary(BaseModel):
    bank_balance: float
    outstanding_checks: float
    expected_receivables: float = 0.0
    total_payables: float = 0.0
    total_upcoming_7d: float
    total_upcoming_30d: float
    total_overdue: float
    real_available: float
    bills_due_soon: List[BillOccurrenceSchema] = []
    overdue_bills: List[BillOccurrenceSchema] = []


# ── Receivable Checks ────────────────────────────────────
class ReceivableCheckCreate(BaseModel):
    job_name: str = Field(min_length=1, max_length=500)
    invoiced_amount: float = Field(ge=0)
    collect: bool = False
    notes: Optional[str] = None


class ReceivableCheckUpdate(BaseModel):
    job_name: Optional[str] = Field(default=None, max_length=500)
    invoiced_amount: Optional[float] = Field(default=None, ge=0)
    collect: Optional[bool] = None
    notes: Optional[str] = None


class ReceivableCheckSchema(BaseModel):
    id: int
    job_name: str
    invoiced_amount: float
    collect: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReceivableCheckListResponse(BaseModel):
    items: List[ReceivableCheckSchema]
    total: int
    total_invoiced: float
    total_receivables: float
