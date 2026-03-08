"""QuickBooks Online OAuth and integration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import Invoice, InvoiceStatus, User
from app.schemas.schemas import InvoiceSchema
from app.services.quickbooks_service import QuickBooksService
from sqlalchemy import select

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])
settings = get_settings()


@router.get("/connect")
async def qbo_connect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the QuickBooks OAuth2 authorization URL."""
    from app.core.security import decrypt_value
    from app.models.models import AppSetting

    # Check DB settings first, then fall back to .env
    client_id = settings.qbo_client_id
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "qbo_client_id")
    )
    db_setting = result.scalar_one_or_none()
    if db_setting and db_setting.value:
        client_id = db_setting.value

    if not client_id:
        raise HTTPException(status_code=400, detail="QuickBooks client ID not configured. Go to Settings to add your QuickBooks credentials.")

    svc = QuickBooksService(db)
    auth_url = await svc.get_auth_url()
    return {"auth_url": auth_url}


@router.get("/callback")
async def qbo_callback(
    code: str = Query(...),
    state: str = Query("qbo_connect"),
    realmId: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """QuickBooks OAuth2 callback — exchanges code for tokens."""
    svc = QuickBooksService(db)
    success = await svc.exchange_code(code, realmId)

    if not success:
        return RedirectResponse(
            url=f"{settings.app_url}/settings?qbo_error=token_exchange_failed"
        )

    await db.commit()
    return RedirectResponse(
        url=f"{settings.app_url}/settings?qbo_connected=true"
    )


@router.get("/status")
async def qbo_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check QuickBooks connection status."""
    svc = QuickBooksService(db)
    connected = await svc.is_connected()

    # Get default account settings
    from app.models.models import AppSetting
    expense_acct = None
    bank_acct = None
    try:
        r1 = await db.execute(select(AppSetting).where(AppSetting.key == "qbo_default_expense_account"))
        s1 = r1.scalar_one_or_none()
        if s1:
            expense_acct = s1.value
        r2 = await db.execute(select(AppSetting).where(AppSetting.key == "qbo_default_bank_account"))
        s2 = r2.scalar_one_or_none()
        if s2:
            bank_acct = s2.value
    except Exception:
        pass

    return {
        "connected": connected,
        "default_expense_account": expense_acct,
        "default_bank_account": bank_acct,
    }


@router.get("/accounts/all")
async def qbo_all_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List expense and bank accounts from QuickBooks for settings dropdowns."""
    svc = QuickBooksService(db)
    expense_accounts = await svc.get_accounts("Expense")
    bank_accounts = await svc.get_accounts("Bank")
    return {
        "expense_accounts": [{"id": str(a["Id"]), "name": a.get("FullyQualifiedName", a.get("Name", ""))} for a in expense_accounts],
        "bank_accounts": [{"id": str(a["Id"]), "name": a.get("FullyQualifiedName", a.get("Name", ""))} for a in bank_accounts],
    }


@router.post("/defaults")
async def save_qbo_defaults(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save default QBO account IDs for auto-send and auto-pay."""
    from app.models.models import AppSetting

    for key in ["qbo_default_expense_account", "qbo_default_bank_account"]:
        short_key = key.replace("qbo_default_", "")
        value = req.get(short_key) or req.get(key)
        if value is not None:
            result = await db.execute(select(AppSetting).where(AppSetting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = str(value)
            else:
                db.add(AppSetting(key=key, value=str(value)))

    await db.commit()
    return {"saved": True}


@router.get("/vendors")
async def qbo_vendors(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List vendors from QuickBooks."""
    svc = QuickBooksService(db)
    vendors = await svc.get_vendors()
    return {"vendors": vendors}


@router.get("/accounts")
async def qbo_accounts(
    account_type: str = Query("Expense"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List accounts from QuickBooks."""
    svc = QuickBooksService(db)
    accounts = await svc.get_accounts(account_type)
    return {"accounts": accounts}


@router.post("/send-bill/{invoice_id}")
async def send_bill_to_qbo(
    invoice_id: int,
    qbo_vendor_id: str = Query(...),
    qbo_account_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send an approved invoice to QuickBooks as a Bill."""
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.APPROVED, InvoiceStatus.AUTO_MATCHED):
        raise HTTPException(status_code=400, detail="Invoice must be approved first")

    svc = QuickBooksService(db)
    bill_id = await svc.create_bill(invoice, qbo_vendor_id, qbo_account_id)
    if not bill_id:
        raise HTTPException(status_code=500, detail="Failed to create bill in QuickBooks")

    invoice.qbo_bill_id = bill_id
    invoice.qbo_vendor_id = qbo_vendor_id
    invoice.status = InvoiceStatus.SENT_TO_QB
    await db.flush()
    await db.commit()

    return {"qbo_bill_id": bill_id, "status": "sent_to_qb"}


@router.post("/disconnect")
async def qbo_disconnect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Disconnect from QuickBooks by removing stored OAuth tokens."""
    from app.models.models import QBOToken

    result = await db.execute(select(QBOToken))
    tokens = result.scalars().all()
    if not tokens:
        raise HTTPException(status_code=400, detail="QuickBooks is not connected")

    for token in tokens:
        await db.delete(token)
    await db.commit()
    return {"disconnected": True}
