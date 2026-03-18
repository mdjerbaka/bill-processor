"""QuickBooks Online integration service.

Handles OAuth2 flow, bill creation, bill payment, and vendor/class sync.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.models import Invoice, QBOToken

logger = logging.getLogger(__name__)
settings = get_settings()

QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_API_BASE = {
    "sandbox": "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}
QBO_SCOPES = "com.intuit.quickbooks.accounting"


class QuickBooksService:
    """Manages QuickBooks Online API interactions."""

    def __init__(self, db: AsyncSession, user_id: int = None):
        self.db = db
        self.user_id = user_id
        self._cached_creds: dict | None = None

    async def _get_qb_creds(self) -> dict:
        """Load QB credentials from DB (app_settings), falling back to .env."""
        if self._cached_creds:
            return self._cached_creds

        from app.models.models import AppSetting

        creds = {
            "client_id": settings.qbo_client_id,
            "client_secret": settings.qbo_client_secret,
            "redirect_uri": settings.qbo_redirect_uri,
            "environment": settings.qbo_environment,
        }

        db_keys = {
            "qbo_client_id": ("client_id", False),
            "qbo_client_secret": ("client_secret", True),
            "qbo_redirect_uri": ("redirect_uri", False),
            "qbo_environment": ("environment", False),
        }

        for db_key, (cred_key, is_encrypted) in db_keys.items():
            try:
                result = await self.db.execute(
                    select(AppSetting).where(AppSetting.key == db_key, AppSetting.user_id == self.user_id)
                )
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    val = decrypt_value(setting.value) if setting.is_encrypted else setting.value
                    if val:
                        creds[cred_key] = val
            except Exception as e:
                logger.debug(f"Could not read QB setting {db_key} from DB: {e}")

        self._cached_creds = creds
        return creds

    # ── OAuth2 Flow ──────────────────────────────────────

    async def get_auth_url(self, state: str = "qbo_connect") -> str:
        """Generate the QuickBooks OAuth2 authorization URL."""
        creds = await self._get_qb_creds()
        params = {
            "client_id": creds["client_id"],
            "response_type": "code",
            "scope": QBO_SCOPES,
            "redirect_uri": creds["redirect_uri"],
            "state": state,
        }
        return f"{QBO_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, realm_id: str) -> bool:
        """Exchange authorization code for access/refresh tokens."""
        creds = await self._get_qb_creds()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QBO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": creds["redirect_uri"],
                },
                auth=(creds["client_id"], creds["client_secret"]),
                headers={"Accept": "application/json"},
            )

        if response.status_code != 200:
            logger.error(f"QBO token exchange failed: {response.text}")
            return False

        data = response.json()
        await self._save_tokens(data, realm_id)
        return True

    async def _refresh_tokens(self, token: QBOToken) -> bool:
        """Refresh the access token using the refresh token."""
        creds = await self._get_qb_creds()
        refresh_token = decrypt_value(token.refresh_token)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                QBO_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(creds["client_id"], creds["client_secret"]),
                headers={"Accept": "application/json"},
            )

        if response.status_code != 200:
            logger.error(f"QBO token refresh failed: {response.text}")
            return False

        data = response.json()
        await self._save_tokens(data, token.realm_id)
        return True

    async def _save_tokens(self, data: dict, realm_id: str) -> None:
        """Save or update QBO tokens in the database."""
        result = await self.db.execute(select(QBOToken).limit(1))
        token = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        access_expires = now + timedelta(seconds=data.get("expires_in", 3600))
        refresh_expires = now + timedelta(seconds=data.get("x_refresh_token_expires_in", 8726400))

        if token:
            token.access_token = encrypt_value(data["access_token"])
            token.refresh_token = encrypt_value(data["refresh_token"])
            token.realm_id = realm_id
            token.expires_at = access_expires
            token.refresh_expires_at = refresh_expires
        else:
            token = QBOToken(
                access_token=encrypt_value(data["access_token"]),
                refresh_token=encrypt_value(data["refresh_token"]),
                realm_id=realm_id,
                expires_at=access_expires,
                refresh_expires_at=refresh_expires,
            )
            self.db.add(token)

        await self.db.flush()

    async def _get_valid_token(self) -> Optional[QBOToken]:
        """Get a valid access token, refreshing if needed."""
        result = await self.db.execute(select(QBOToken).limit(1))
        token = result.scalar_one_or_none()
        if not token:
            return None

        now = datetime.now(timezone.utc)

        # Ensure stored datetimes are timezone-aware for comparison
        expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=timezone.utc)
        refresh_expires_at = token.refresh_expires_at if token.refresh_expires_at.tzinfo else token.refresh_expires_at.replace(tzinfo=timezone.utc)

        # Refresh if within 10 minutes of expiry
        if expires_at <= now + timedelta(minutes=10):
            if refresh_expires_at <= now:
                logger.error("QBO refresh token expired — re-authorization required")
                return None
            success = await self._refresh_tokens(token)
            if not success:
                return None
            # Re-fetch after refresh
            result = await self.db.execute(select(QBOToken).limit(1))
            token = result.scalar_one_or_none()

        return token

    async def _api_request(
        self, method: str, path: str, json_data: dict = None
    ) -> Optional[dict]:
        """Make an authenticated API request to QuickBooks."""
        token = await self._get_valid_token()
        if not token:
            logger.error("No valid QBO token available")
            return None

        creds = await self._get_qb_creds()
        base_url = QBO_API_BASE[creds["environment"]]
        realm_id = token.realm_id
        access_token = decrypt_value(token.access_token)
        url = f"{base_url}/v3/company/{realm_id}/{path}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                json=json_data,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 201):
            # Parse detailed error from QBO response
            detail = ""
            err_body = None
            try:
                err_body = response.json()
                fault = err_body.get("Fault", {})
                errors = fault.get("Error", [{}])
                if errors:
                    detail = errors[0].get("Detail", errors[0].get("Message", ""))
            except Exception:
                detail = response.text[:500]
            logger.error(
                f"QBO API error {method} {path}: {response.status_code} \u2014 {detail}"
            )
            # Return parsed body so callers can inspect Fault details
            return err_body

        return response.json()

    # ── Bill Operations ──────────────────────────────────

    async def create_bill(self, invoice: Invoice, qbo_vendor_id: str, qbo_account_id: str) -> Optional[str]:
        """Create a bill in QuickBooks from an approved invoice."""
        lines = []

        # Eagerly load line_items if not already loaded (avoids greenlet error in worker)
        line_items = []
        try:
            if invoice.line_items:
                line_items = list(invoice.line_items)
        except Exception:
            # Lazy-load failed (e.g. worker context) — query them directly
            from sqlalchemy import select as sel
            from app.models.models import InvoiceLineItem
            result = await self.db.execute(
                sel(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
            )
            line_items = list(result.scalars().all())

        expected_total = invoice.total_amount or 0

        if line_items:
            line_sum = 0.0
            for item in line_items:
                amt = item.amount or 0
                line_sum += amt
                lines.append({
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Amount": amt,
                    "Description": item.description or "",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": qbo_account_id},
                    },
                })

            # If line items don't sum to the invoice total, add an adjustment line
            diff = round(expected_total - line_sum, 2)
            if diff > 0:
                lines.append({
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Amount": diff,
                    "Description": "Adjustment to match invoice total",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": qbo_account_id},
                    },
                })
            elif diff < 0:
                logger.warning(
                    f"Line items sum (${line_sum:.2f}) exceeds invoice total "
                    f"(${expected_total:.2f}) for invoice {invoice.id}"
                )
        else:
            # Single line for the total
            lines.append({
                "DetailType": "AccountBasedExpenseLineDetail",
                "Amount": expected_total,
                "Description": f"Invoice {invoice.invoice_number or 'N/A'}",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": qbo_account_id},
                },
            })

        bill_data = {
            "VendorRef": {"value": qbo_vendor_id},
            "Line": lines,
        }

        if invoice.invoice_date:
            bill_data["TxnDate"] = invoice.invoice_date.strftime("%Y-%m-%d")
        if invoice.due_date:
            bill_data["DueDate"] = invoice.due_date.strftime("%Y-%m-%d")
        if invoice.invoice_number:
            bill_data["DocNumber"] = invoice.invoice_number[:21]  # QBO max 21 chars

        result = await self._api_request("POST", "bill", bill_data)
        if result and "Bill" in result:
            return result["Bill"]["Id"]
        logger.error(f"Failed to create QBO bill for invoice {invoice.id}: {result}")
        return None

    async def pay_bill(
        self, qbo_bill_id: str, qbo_vendor_id: str, amount: float,
        bank_account_id: str, pay_type: str = "Check"
    ) -> Optional[str]:
        """Record a bill payment in QuickBooks."""
        payment_data = {
            "VendorRef": {"value": qbo_vendor_id},
            "TotalAmt": amount,
            "PayType": pay_type,
            "Line": [
                {
                    "Amount": amount,
                    "LinkedTxn": [
                        {"TxnId": qbo_bill_id, "TxnType": "Bill"}
                    ],
                }
            ],
        }

        if pay_type == "Check":
            payment_data["CheckPayment"] = {
                "BankAccountRef": {"value": bank_account_id}
            }
        else:
            payment_data["CreditCardPayment"] = {
                "CCAccountRef": {"value": bank_account_id}
            }

        result = await self._api_request("POST", "billpayment", payment_data)
        if result and "BillPayment" in result:
            return result["BillPayment"]["Id"]
        logger.error(f"Failed to create QBO bill payment for bill {qbo_bill_id}: {result}")
        return None

    # ── Sync Operations ──────────────────────────────────

    async def find_or_create_vendor(self, vendor_name: str) -> Optional[str]:
        """Find a vendor in QBO by name, or create one. Returns QBO vendor ID."""
        if not vendor_name:
            return None

        # QBO requires backslash-escaping for apostrophes in query strings
        safe_name = vendor_name.replace("'", "\\'")[:100]

        # Try exact match first
        result = await self._api_request(
            "GET",
            f"query?query=SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 1"
        )
        if result and "QueryResponse" in result:
            vendors = result["QueryResponse"].get("Vendor", [])
            if vendors:
                return str(vendors[0]["Id"])

        # Try LIKE match (partial / case-insensitive)
        result = await self._api_request(
            "GET",
            f"query?query=SELECT * FROM Vendor WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
        )
        if result and "QueryResponse" in result:
            vendors = result["QueryResponse"].get("Vendor", [])
            if vendors:
                return str(vendors[0]["Id"])

        # Not found — create new vendor
        create_result = await self._api_request("POST", "vendor", {
            "DisplayName": vendor_name[:100],
        })
        if create_result and "Vendor" in create_result:
            logger.info(f"Created QBO vendor: {vendor_name} → {create_result['Vendor']['Id']}")
            return str(create_result["Vendor"]["Id"])

        # Handle "name already exists" error — extract the existing vendor ID
        if create_result and isinstance(create_result, dict) and "Fault" in create_result:
            errors = create_result.get("Fault", {}).get("Error", [{}])
            for err in errors:
                detail = err.get("Detail", "")
                # QBO returns "The name supplied already exists. : Id=61"
                if "already exists" in detail.lower() and "Id=" in detail:
                    import re
                    id_match = re.search(r"Id=(\d+)", detail)
                    if id_match:
                        existing_id = id_match.group(1)
                        logger.info(f"Vendor '{vendor_name}' already exists in QBO with Id={existing_id}")
                        return existing_id

        logger.error(f"Failed to find or create QBO vendor: {vendor_name}")
        return None

    async def get_default_expense_account(self) -> Optional[str]:
        """Get the default expense account ID from settings, or find the first Expense account."""
        # Check DB setting first
        from app.models.models import AppSetting
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "qbo_default_expense_account", AppSetting.user_id == self.user_id)
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value

        # Fall back: find the first Expense type account
        accounts = await self.get_accounts("Expense")
        if accounts:
            return str(accounts[0]["Id"])
        return None

    async def get_default_bank_account(self) -> Optional[str]:
        """Get the default bank account ID from settings, or find the first Bank account."""
        from app.models.models import AppSetting
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "qbo_default_bank_account", AppSetting.user_id == self.user_id)
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value

        # Fall back: find the first Bank account
        accounts = await self.get_accounts("Bank")
        if accounts:
            return str(accounts[0]["Id"])
        return None

    async def auto_send_bill(self, invoice: Invoice) -> tuple[Optional[str], Optional[str]]:
        """Automatically create a bill in QBO for an approved invoice.
        
        Finds or creates the vendor, uses the default expense account,
        and creates the bill. Returns (qbo_bill_id, qbo_vendor_id) tuple.
        """
        if not await self.is_connected():
            logger.debug("QBO not connected, skipping auto-send")
            return None, None

        # Find or create vendor
        vendor_id = await self.find_or_create_vendor(invoice.vendor_name)
        if not vendor_id:
            logger.warning(f"Could not resolve QBO vendor for invoice {invoice.id}")
            return None, None

        # Get default expense account
        account_id = await self.get_default_expense_account()
        if not account_id:
            logger.warning("No QBO expense account available, skipping auto-send")
            return None, vendor_id

        bill_id = await self.create_bill(invoice, vendor_id, account_id)
        if bill_id:
            logger.info(f"Auto-sent invoice {invoice.id} to QBO as bill {bill_id}")
        return bill_id, vendor_id

    async def auto_pay_bill(self, invoice: Invoice) -> Optional[str]:
        """Record a bill payment in QBO when an invoice is marked as paid.
        
        Returns the QBO payment ID or None.
        """
        if not await self.is_connected():
            logger.debug("QBO not connected, skipping payment sync")
            return None

        if not invoice.qbo_bill_id:
            logger.debug(f"Invoice {invoice.id} has no QBO bill ID, skipping payment sync")
            return None

        if not invoice.qbo_vendor_id:
            logger.debug(f"Invoice {invoice.id} has no QBO vendor ID, skipping payment sync")
            return None

        bank_account_id = await self.get_default_bank_account()
        if not bank_account_id:
            logger.warning("No QBO bank account available, skipping payment sync")
            return None

        # Read the actual QBO bill to get its real balance (line items may
        # not sum to invoice.total_amount)
        amount = invoice.total_amount or 0.0
        bill_data = await self._api_request(
            "GET",
            f"bill/{invoice.qbo_bill_id}"
        )
        if bill_data and "Bill" in bill_data:
            qbo_balance = bill_data["Bill"].get("Balance")
            if qbo_balance is not None:
                amount = float(qbo_balance)
                if amount == 0:
                    logger.info(f"QBO bill {invoice.qbo_bill_id} already has $0 balance, skipping payment")
                    return None

        payment_id = await self.pay_bill(
            invoice.qbo_bill_id, invoice.qbo_vendor_id, amount, bank_account_id
        )
        if payment_id:
            logger.info(f"Auto-paid QBO bill {invoice.qbo_bill_id}, payment ID: {payment_id}")
        return payment_id

    async def get_vendors(self) -> list[dict]:
        """Fetch all vendors from QuickBooks."""
        result = await self._api_request(
            "GET",
            "query?query=SELECT * FROM Vendor MAXRESULTS 1000"
        )
        if result and "QueryResponse" in result:
            return result["QueryResponse"].get("Vendor", [])
        return []

    async def get_classes(self) -> list[dict]:
        """Fetch all classes (used as jobs/projects) from QuickBooks."""
        result = await self._api_request(
            "GET",
            "query?query=SELECT * FROM Class MAXRESULTS 1000"
        )
        if result and "QueryResponse" in result:
            return result["QueryResponse"].get("Class", [])
        return []

    async def get_accounts(self, account_type: str = "Expense") -> list[dict]:
        """Fetch accounts of a given type from QuickBooks."""
        result = await self._api_request(
            "GET",
            f"query?query=SELECT * FROM Account WHERE AccountType = '{account_type}' MAXRESULTS 1000"
        )
        if result and "QueryResponse" in result:
            return result["QueryResponse"].get("Account", [])
        return []

    async def is_connected(self) -> bool:
        """Check if a valid QBO connection exists."""
        token = await self._get_valid_token()
        return token is not None
