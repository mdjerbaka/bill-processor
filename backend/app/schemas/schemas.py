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
    invoice_id: int
    vendor_name: str
    amount: float
    due_date: Optional[datetime] = None
    status: str
    paid_at: Optional[datetime] = None
    created_at: datetime
    invoice_number: Optional[str] = None
    job_name: Optional[str] = None

    class Config:
        from_attributes = True


class PayableListResponse(BaseModel):
    items: List[PayableSchema]
    total: int
    total_outstanding: float
    total_overdue: float


class BankBalanceRequest(BaseModel):
    bank_balance: float


class RealBalanceResponse(BaseModel):
    bank_balance: float
    total_outstanding: float
    real_available: float


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
