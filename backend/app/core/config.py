from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── App ──────────────────────────────────────────────
    app_name: str = "Bill Processor"
    app_url: str = "http://localhost:3000"
    debug: bool = False

    # ── Database ─────────────────────────────────────────
    database_url: str = ""

    # ── Redis ────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Security ─────────────────────────────────────────
    secret_key: str = ""
    encryption_key: str = ""
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── OCR ──────────────────────────────────────────────
    ocr_provider: Literal["none", "azure", "aws", "openai", "google", "paddleocr"] = "none"
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # ── OpenAI (LLM fallback) ────────────────────────────
    openai_api_key: str = ""

    # ── QuickBooks Online ────────────────────────────────
    qbo_client_id: str = ""
    qbo_client_secret: str = ""
    qbo_redirect_uri: str = "http://localhost:8000/api/v1/quickbooks/callback"
    qbo_environment: Literal["sandbox", "production"] = "sandbox"

    # ── Microsoft 365 (Graph API email) ───────────────────
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = "common"
    ms_redirect_uri: str = "http://localhost:8000/api/v1/microsoft/callback"

    # ── Email polling ────────────────────────────────────
    email_poll_interval_seconds: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
