"""Email ingestion service — polls IMAP inbox for new invoices."""

from __future__ import annotations

import email
import logging
import os
import uuid
from email.header import decode_header
from pathlib import Path
from typing import Optional

from imapclient import IMAPClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_value
from app.models.models import AppSetting, Attachment, Email, EmailStatus

logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(__file__).resolve().parent.parent.parent / "data" / "attachments"))
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".xlsx", ".xls", ".csv"}


class EmailService:
    """Handles IMAP connection and email ingestion."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def get_email_config(self) -> Optional[dict]:
        """Load email configuration from app_settings."""
        keys = ["imap_host", "imap_port", "imap_username", "imap_password", "imap_use_ssl"]
        config = {}
        for key in keys:
            result = await self.db.execute(
                select(AppSetting).where(AppSetting.key == key, AppSetting.user_id == self.user_id)
            )
            setting = result.scalar_one_or_none()
            if setting is None:
                return None
            try:
                value = decrypt_value(setting.value) if setting.is_encrypted else setting.value
            except (ValueError, Exception):
                if key == "imap_password":
                    # Password can't be decrypted — return config with empty password
                    # so the UI can still show the other saved fields
                    value = ""
                else:
                    return None
            config[key] = value
        return config

    async def test_connection(self) -> tuple[bool, str]:
        """Test the IMAP connection with stored credentials."""
        try:
            config = await self.get_email_config()
        except (ValueError, Exception) as e:
            return False, f"Decryption error — please re-save your email settings: {e}"
        if not config:
            return False, "Email not configured"
        try:
            client = IMAPClient(
                config["imap_host"],
                port=int(config["imap_port"]),
                ssl=config["imap_use_ssl"] == "true",
            )
            client.login(config["imap_username"], config["imap_password"])
            client.select_folder("INBOX")
            client.logout()
            return True, "Connection successful"
        except Exception as e:
            logger.error(f"IMAP connection test failed: {e}")
            return False, str(e)

    async def poll_inbox(self) -> list[int]:
        """Poll the IMAP inbox for unseen messages and ingest them."""
        config = await self.get_email_config()
        if not config:
            logger.warning("Email not configured, skipping poll")
            return []

        created_ids = []
        try:
            client = IMAPClient(
                config["imap_host"],
                port=int(config["imap_port"]),
                ssl=config["imap_use_ssl"] == "true",
            )
            client.login(config["imap_username"], config["imap_password"])
            client.select_folder("INBOX")

            # Only process emails from the last 2 days to avoid old backlog
            from datetime import datetime, timedelta
            since_date = (datetime.now() - timedelta(days=2)).date()
            message_ids = client.search(["UNSEEN", "SINCE", since_date])
            if not message_ids:
                client.logout()
                return []

            # Limit to 20 emails per poll to avoid timeouts
            MAX_PER_POLL = 20
            if len(message_ids) > MAX_PER_POLL:
                logger.info(f"Found {len(message_ids)} unseen recent messages, processing last {MAX_PER_POLL}")
                message_ids = message_ids[-MAX_PER_POLL:]
            else:
                logger.info(f"Found {len(message_ids)} unseen recent messages")

            for uid in message_ids:
                try:
                    raw_messages = client.fetch([uid], ["RFC822"])
                    raw_email = raw_messages[uid][b"RFC822"]
                    msg = email.message_from_bytes(raw_email)

                    # Check for supported attachments
                    has_attachment = False
                    if msg.is_multipart():
                        for part in msg.walk():
                            disposition = part.get_content_disposition()
                            filename = part.get_filename()
                            if filename and disposition in ("attachment", "inline"):
                                ext = os.path.splitext(filename)[1].lower()
                                if ext in SUPPORTED_EXTENSIONS:
                                    has_attachment = True
                                    break

                    # Also check for substantial body text (body-only invoices)
                    has_body = False
                    if not has_attachment:
                        body = self._extract_body_text(msg)
                        if body and len(body.strip()) > 50:
                            has_body = True

                    if not has_attachment and not has_body:
                        # Skip emails without attachments or meaningful body
                        client.add_flags([uid], [b"\\Seen"])
                        continue

                    email_id = await self._ingest_email(msg)
                    if email_id:
                        created_ids.append(email_id)
                    # Mark as seen whether ingested or skipped (duplicate)
                    client.add_flags([uid], [b"\\Seen"])
                except Exception as e:
                    logger.error(f"Failed to process message {uid}: {e}")
                    # Rollback so the session is usable for the next message
                    await self.db.rollback()
                    # Still mark as seen to avoid reprocessing bad messages
                    try:
                        client.add_flags([uid], [b"\\Seen"])
                    except Exception:
                        pass

            client.logout()
        except Exception as e:
            logger.error(f"IMAP poll failed: {e}")

        return created_ids

    async def _ingest_email(self, msg: email.message.Message) -> Optional[int]:
        """Parse an email message and store it with attachments."""
        # Extract headers
        message_id = msg.get("Message-ID", "")
        from_addr = self._decode_header(msg.get("From", ""))
        subject = self._decode_header(msg.get("Subject", ""))

        # Check for duplicate
        existing = await self.db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Skipping duplicate message: {message_id}")
            return None

        # Extract body text
        body_text = self._extract_body_text(msg)

        try:
            # Create email record
            email_record = Email(
                message_id=message_id,
                from_address=from_addr,
                subject=subject,
                body_text=body_text,
                status=EmailStatus.PENDING,
                user_id=self.user_id,
            )
            self.db.add(email_record)
            await self.db.flush()

            # Extract and save attachments
            if msg.is_multipart():
                for part in msg.walk():
                    disposition = part.get_content_disposition()
                    if disposition == "attachment" or (
                        disposition == "inline"
                        and part.get_content_type().startswith("image/")
                    ):
                        await self._save_attachment(part, email_record.id)

            await self.db.commit()
            logger.info(f"Ingested email {email_record.id}: {subject}")
            return email_record.id

        except Exception as e:
            await self.db.rollback()
            # If it's a duplicate key error, that's fine — just skip
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.debug(f"Duplicate email skipped: {message_id}")
                return None
            logger.error(f"Failed to ingest email '{subject}': {e}")
            raise

    async def _save_attachment(
        self, part: email.message.Message, email_id: int
    ) -> Optional[int]:
        """Save an email attachment to disk and database."""
        filename = part.get_filename()
        if not filename:
            return None

        filename = self._decode_header(filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            logger.debug(f"Skipping unsupported attachment: {filename}")
            return None

        payload = part.get_payload(decode=True)
        if not payload:
            return None

        # Save to disk
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / unique_name

        with open(file_path, "wb") as f:
            f.write(payload)

        # Save record
        attachment = Attachment(
            email_id=email_id,
            filename=filename,
            content_type=part.get_content_type(),
            file_path=str(file_path),
            file_size=len(payload),
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment.id

    @staticmethod
    def _extract_body_text(msg: email.message.Message) -> str:
        """Extract plain-text body from an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
        return ""

    @staticmethod
    def _decode_header(value: str) -> str:
        """Decode an email header value."""
        if not value:
            return ""
        parts = decode_header(value)
        decoded = []
        for data, charset in parts:
            if isinstance(data, bytes):
                decoded.append(data.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(data)
        return " ".join(decoded)
