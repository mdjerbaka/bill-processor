"""Vendor accounts (Top Vendor Accounts) management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    VendorAccountCreate,
    VendorAccountListResponse,
    VendorAccountSchema,
    VendorAccountUpdate,
)
from app.services.vendor_accounts_service import VendorAccountsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vendor-accounts", tags=["vendor-accounts"])


@router.get("", response_model=VendorAccountListResponse)
async def list_vendor_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = VendorAccountsService(db, user.id)
    accounts = await svc.list_accounts()
    total_amount = await svc.get_total()
    items = [VendorAccountSchema.model_validate(a) for a in accounts]
    return VendorAccountListResponse(items=items, total=len(items), total_amount=total_amount)


@router.post("", response_model=VendorAccountSchema, status_code=201)
async def create_vendor_account(
    data: VendorAccountCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = VendorAccountsService(db, user.id)
    account = await svc.create_account(data.model_dump())
    await db.commit()
    await db.refresh(account)
    return VendorAccountSchema.model_validate(account)


@router.put("/{account_id}", response_model=VendorAccountSchema)
async def update_vendor_account(
    account_id: int,
    data: VendorAccountUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = VendorAccountsService(db, user.id)
    account = await svc.update_account(account_id, data.model_dump(exclude_unset=True))
    if not account:
        raise HTTPException(status_code=404, detail="Vendor account not found")
    await db.commit()
    await db.refresh(account)
    return VendorAccountSchema.model_validate(account)


@router.delete("/{account_id}")
async def delete_vendor_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = VendorAccountsService(db, user.id)
    deleted = await svc.delete_account(account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vendor account not found")
    await db.commit()
    return {"detail": "Vendor account deleted"}
