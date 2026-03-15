"""Microsoft Graph API email service — reads emails via OAuth2.

Replaces IMAP for Microsoft 365 / Outlook accounts, which no longer
support basic authentication.
"""

from __future__ import annotations

import base64
import email
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.models import (
    AppSetting,
    Attachment,
    Email,
    EmailStatus,
    MSGraphToken,
)

logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_DIR = Path(
    os.environ.get(
        "UPLOAD_DIR",
        Path(__file__).resolve().parent.parent.parent / "data" / "attachments",
    )
)
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".xlsx", ".xls", ".csv"}

# Microsoft identity platform endpoints
MS_AUTHORITY = "https://login.microsoftonline.com"
MS_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MS_SCOPES = ["Mail.Read", "User.Read", "offline_access"]


class MicrosoftGraphService:
    """Handles Microsoft 365 OAuth and email retrieval via Graph API."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── OAuth2 Flow ──────────────────────────────────────

    def get_auth_url(self, state: str = "ms_connect") -> str:
        """Generate the Microsoft OAuth2 authorization URL."""
        tenant = settings.ms_tenant_id or "common"
        params = {
            "client_id": settings.ms_client_id,
            "response_type": "code",
            "redirect_uri": settings.ms_redirect_uri,
            "response_mode": "query",
            "scope": " ".join(MS_SCOPES),
            "state": state,
        }
        return f"{MS_AUTHORITY}/{tenant}/oauth2/v2.0/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> bool:
        """Exchange authorization code for access + refresh tokens."""
        tenant = settings.ms_tenant_id or "common"
        token_url = f"{MS_AUTHORITY}/{tenant}/oauth2/v2.0/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "client_id": settings.ms_client_id,
                    "client_secret": settings.ms_client_secret,
                    "code": code,
                    "redirect_uri": settings.ms_redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": " ".join(MS_SCOPES),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != 200:
            logger.error(f"MS token exchange failed: {response.text}")
            return False

        data = response.json()
        await self._save_tokens(data)
        return True

    async def _refresh_tokens(self, token: MSGraphToken) -> bool:
        """Refresh the access token using the refresh token."""
        refresh_token = decrypt_value(token.refresh_token)
        tenant = settings.ms_tenant_id or "common"
        token_url = f"{MS_AUTHORITY}/{tenant}/oauth2/v2.0/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "client_id": settings.ms_client_id,
                    "client_secret": settings.ms_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": " ".join(MS_SCOPES),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != 200:
            logger.error(f"MS token refresh failed: {response.text}")
            return False

        data = response.json()
        await self._save_tokens(data)
        return True

    async def _save_tokens(self, data: dict) -> None:
        """Save or update MS Graph tokens in the database."""
        result = await self.db.execute(select(MSGraphToken).limit(1))
        token = result.scalar_one_or_none()

        access_encrypted = encrypt_value(data["access_token"])
        refresh_encrypted = encrypt_value(data.get("refresh_token", ""))
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=data.get("expires_in", 3600)
        )

        if token:
            token.access_token = access_encrypted
            if data.get("refresh_token"):
                token.refresh_token = refresh_encrypted
            token.expires_at = expires_at
        else:
            token = MSGraphToken(
                access_token=access_encrypted,
                refresh_token=refresh_encrypted,
                expires_at=expires_at,
            )
            self.db.add(token)

        await self.db.flush()

        # Fetch and store the user's email address
        try:
            access = data["access_token"]
            async with httpx.AsyncClient() as client:
                me = await client.get(
                    f"{MS_GRAPH_BASE}/me",
                    headers={"Authorization": f"Bearer {access}"},
                )
            if me.status_code == 200:
                me_data = me.json()
                token.email_address = me_data.get("mail") or me_data.get(
                    "userPrincipalName", ""
                )
                await self.db.flush()
        except Exception as e:
            logger.warning(f"Could not fetch MS user profile: {e}")

    async def _get_valid_token(self) -> Optional[str]:
        """Return a valid access token, refreshing if needed."""
        result = await self.db.execute(select(MSGraphToken).limit(1))
        token = result.scalar_one_or_none()
        if not token:
            return None

        # Refresh if expired (with 5 min buffer)
        if token.expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
            ok = await self._refresh_tokens(token)
            if not ok:
                return None
            # Re-fetch after refresh
            result = await self.db.execute(select(MSGraphToken).limit(1))
            token = result.scalar_one_or_none()
            if not token:
                return None

        return decrypt_value(token.access_token)

    # ── Status ───────────────────────────────────────────

    async def is_connected(self) -> bool:
        """Check if we have a valid MS Graph connection."""
        access = await self._get_valid_token()
        return access is not None

    async def get_connection_info(self) -> dict:
        """Return connection status and email address."""
        result = await self.db.execute(select(MSGraphToken).limit(1))
        token = result.scalar_one_or_none()
        if not token:
            return {"connected": False, "email": ""}
        access = await self._get_valid_token()
        return {
            "connected": access is not None,
            "email": token.email_address or "",
        }

    async def disconnect(self) -> None:
        """Remove stored MS Graph tokens."""
        result = await self.db.execute(select(MSGraphToken).limit(1))
        token = result.scalar_one_or_none()
        if token:
            await self.db.delete(token)
            await self.db.flush()

    async def test_connection(self) -> tuple[bool, str]:
        """Test MS Graph connection by calling /me/mailFolders/inbox."""
        access = await self._get_valid_token()
        if not access:
            return False, "Not connected to Microsoft 365"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{MS_GRAPH_BASE}/me/mailFolders/inbox",
                    headers={"Authorization": f"Bearer {access}"},
                )
            if resp.status_code == 200:
                data = resp.json()
                count = data.get("totalItemCount", "?")
                return True, f"Connected — inbox has {count} messages"
            else:
                return False, f"Graph API error: {resp.status_code} {resp.text[:200]}"
        except Exception as e:
            return False, str(e)

    # ── Email Polling ────────────────────────────────────

    async def poll_inbox(self) -> list[int]:
        """Poll Microsoft 365 inbox for unread messages with attachments."""
        access = await self._get_valid_token()
        if not access:
            logger.warning("MS Graph not connected, skipping poll")
            return []

        created_ids = []
        try:
            headers = {"Authorization": f"Bearer {access}"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Get recent unread messages that have attachments
                since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                params = {
                    "$filter": f"isRead eq false and hasAttachments eq true and receivedDateTime ge {since}",
                    "$select": "id,subject,from,receivedDateTime,body,internetMessageId",
                    "$top": "20",
                    "$orderby": "receivedDateTime desc",
                }
                resp = await client.get(
                    f"{MS_GRAPH_BASE}/me/messages",
                    headers=headers,
                    params=params,
                )

                if resp.status_code != 200:
                    logger.error(f"MS Graph messages fetch failed: {resp.status_code} {resp.text[:300]}")
                    return []

                messages = resp.json().get("value", [])
                if not messages:
                    logger.info("No unread messages with attachments in MS 365 inbox")
                    return []

                logger.info(f"Found {len(messages)} unread messages with attachments")

                for msg in messages:
                    try:
                        email_id = await self._ingest_graph_message(
                            client, headers, msg
                        )
                        if email_id:
                            created_ids.append(email_id)

                        # Mark as read
                        await client.patch(
                            f"{MS_GRAPH_BASE}/me/messages/{msg['id']}",
                            headers={**headers, "Content-Type": "application/json"},
                            json={"isRead": True},
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process MS Graph message {msg.get('id')}: {e}"
                        )
                        await self.db.rollback()
                        # Still mark as read to avoid reprocessing
                        try:
                            await client.patch(
                                f"{MS_GRAPH_BASE}/me/messages/{msg['id']}",
                                headers={
                                    **headers,
                                    "Content-Type": "application/json",
                                },
                                json={"isRead": True},
                            )
                        except Exception:
                            pass

        except Exception as e:
            logger.error(f"MS Graph poll failed: {e}")

        return created_ids

    async def _ingest_graph_message(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        msg: dict,
    ) -> Optional[int]:
        """Ingest a single Graph API message and its attachments."""
        message_id = msg.get("internetMessageId", msg["id"])
        from_data = msg.get("from", {}).get("emailAddress", {})
        from_addr = f"{from_data.get('name', '')} <{from_data.get('address', '')}>"
        subject = msg.get("subject", "")
        body_text = msg.get("body", {}).get("content", "")

        # Check for duplicate
        existing = await self.db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Skipping duplicate MS Graph message: {message_id}")
            return None

        # Fetch attachments
        att_resp = await client.get(
            f"{MS_GRAPH_BASE}/me/messages/{msg['id']}/attachments",
            headers=headers,
        )
        if att_resp.status_code != 200:
            logger.error(f"Failed to fetch attachments: {att_resp.status_code}")
            return None

        attachments = att_resp.json().get("value", [])

        # Filter for supported file types
        valid_attachments = []
        for att in attachments:
            if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            name = att.get("name", "")
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                valid_attachments.append(att)

        if not valid_attachments:
            # No invoice-like attachments, skip
            return None

        try:
            email_record = Email(
                message_id=message_id,
                from_address=from_addr,
                subject=subject,
                body_text=body_text[:5000] if body_text else "",
                status=EmailStatus.PENDING,
            )
            self.db.add(email_record)
            await self.db.flush()

            for att in valid_attachments:
                await self._save_graph_attachment(att, email_record.id)

            await self.db.commit()
            logger.info(f"Ingested MS Graph email {email_record.id}: {subject}")
            return email_record.id

        except Exception as e:
            await self.db.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.debug(f"Duplicate email skipped: {message_id}")
                return None
            logger.error(f"Failed to ingest MS Graph email '{subject}': {e}")
            raise

    async def _save_graph_attachment(
        self, att: dict, email_id: int
    ) -> Optional[int]:
        """Save a Graph API file attachment to disk and database."""
        filename = att.get("name", "unknown")
        ext = os.path.splitext(filename)[1].lower()
        content_bytes = base64.b64decode(att.get("contentBytes", ""))
        if not content_bytes:
            return None

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / unique_name

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        attachment = Attachment(
            email_id=email_id,
            filename=filename,
            content_type=att.get("contentType", "application/octet-stream"),
            file_path=str(file_path),
            file_size=len(content_bytes),
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment.id

    # ── Send Mail ────────────────────────────────────────

    async def send_mail(
        self, subject: str, body_html: str, to_email: Optional[str] = None
    ) -> bool:
        """Send an email via Microsoft Graph API.

        If to_email is not provided, sends to the connected user's own email
        (useful for self-notifications).
        """
        access = await self._get_valid_token()
        if not access:
            logger.warning("MS Graph not connected, cannot send mail")
            return False

        # Resolve recipient
        if not to_email:
            result = await self.db.execute(select(MSGraphToken).limit(1))
            token = result.scalar_one_or_none()
            to_email = token.email_address if token else None
            if not to_email:
                logger.error("No recipient email and no connected email address")
                return False

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html,
                },
                "toRecipients": [
                    {"emailAddress": {"address": to_email}}
                ],
            },
            "saveToSentItems": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{MS_GRAPH_BASE}/me/sendMail",
                    headers={
                        "Authorization": f"Bearer {access}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code == 202:
                logger.info(f"Email sent successfully to {to_email}: {subject}")
                return True
            else:
                logger.error(f"Send mail failed: {resp.status_code} {resp.text[:300]}")
                return False
        except Exception as e:
            logger.error(f"Send mail exception: {e}")
            return False
