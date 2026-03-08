"""OCR / AI invoice extraction pipeline.

Supports pluggable providers:
  - Azure Document Intelligence (prebuilt-invoice)
  - AWS Textract (AnalyzeExpense)
  - OpenAI GPT-4o vision (LLM fallback)
  - None (manual entry)
"""

from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.schemas.schemas import InvoiceLineItemSchema

logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractedInvoiceData:
    """Normalized extraction result from any OCR provider."""

    def __init__(self):
        self.vendor_name: Optional[str] = None
        self.vendor_address: Optional[str] = None
        self.project_address: Optional[str] = None
        self.invoice_number: Optional[str] = None
        self.invoice_date: Optional[str] = None  # ISO format string
        self.due_date: Optional[str] = None
        self.total_amount: Optional[float] = None
        self.subtotal: Optional[float] = None
        self.tax_amount: Optional[float] = None
        self.line_items: list[dict] = []
        self.confidence_score: float = 0.0
        self.raw_response: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "vendor_name": self.vendor_name,
            "vendor_address": self.vendor_address,
            "project_address": self.project_address,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "total_amount": self.total_amount,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "line_items": self.line_items,
            "confidence_score": self.confidence_score,
        }


class OCRProvider(ABC):
    """Abstract base for OCR providers."""

    @abstractmethod
    async def extract(self, file_path: str) -> ExtractedInvoiceData:
        ...


class NoOCRProvider(OCRProvider):
    """Placeholder when no OCR is configured — returns empty extraction."""

    async def extract(self, file_path: str) -> ExtractedInvoiceData:
        logger.warning("No OCR provider configured; returning empty extraction")
        return ExtractedInvoiceData()


class AzureDocumentIntelligenceProvider(OCRProvider):
    """Azure Document Intelligence prebuilt-invoice model."""

    async def extract(self, file_path: str) -> ExtractedInvoiceData:
        try:
            from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError:
            logger.error("azure-ai-documentintelligence not installed")
            return ExtractedInvoiceData()

        client = DocumentIntelligenceClient(
            endpoint=settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(settings.azure_document_intelligence_key),
        )

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        poller = await client.begin_analyze_document(
            model_id="prebuilt-invoice",
            body=file_bytes,
            content_type="application/octet-stream",
        )
        result = await poller.result()
        await client.close()

        data = ExtractedInvoiceData()
        if result.documents:
            doc = result.documents[0]
            fields = doc.fields or {}
            data.vendor_name = self._get_field_value(fields, "VendorName")
            data.vendor_address = self._get_field_value(fields, "VendorAddress")
            data.invoice_number = self._get_field_value(fields, "InvoiceId")
            data.invoice_date = self._get_field_value(fields, "InvoiceDate")
            data.due_date = self._get_field_value(fields, "DueDate")
            data.total_amount = self._get_field_value(fields, "InvoiceTotal")
            data.subtotal = self._get_field_value(fields, "SubTotal")
            data.tax_amount = self._get_field_value(fields, "TotalTax")
            data.confidence_score = doc.confidence or 0.0

            # Line items
            items_field = fields.get("Items")
            if items_field and items_field.value:
                for item in items_field.value:
                    item_fields = item.value or {}
                    data.line_items.append({
                        "description": self._get_field_value(item_fields, "Description"),
                        "quantity": self._get_field_value(item_fields, "Quantity"),
                        "unit_price": self._get_field_value(item_fields, "UnitPrice"),
                        "amount": self._get_field_value(item_fields, "Amount"),
                        "product_code": self._get_field_value(item_fields, "ProductCode"),
                    })

        data.raw_response = {"document_count": len(result.documents or [])}
        return data

    @staticmethod
    def _get_field_value(fields: dict, key: str):
        field = fields.get(key)
        if field and field.value is not None:
            return field.value
        if field and field.content:
            return field.content
        return None


class AWSTextractProvider(OCRProvider):
    """AWS Textract AnalyzeExpense."""

    async def extract(self, file_path: str) -> ExtractedInvoiceData:
        try:
            import boto3
        except ImportError:
            logger.error("boto3 not installed")
            return ExtractedInvoiceData()

        client = boto3.client(
            "textract",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        response = client.analyze_expense(
            Document={"Bytes": file_bytes}
        )

        data = ExtractedInvoiceData()
        for doc in response.get("ExpenseDocuments", []):
            for field in doc.get("SummaryFields", []):
                field_type = field.get("Type", {}).get("Text", "")
                value = field.get("ValueDetection", {}).get("Text", "")
                confidence = field.get("ValueDetection", {}).get("Confidence", 0) / 100

                if "VENDOR" in field_type.upper() and "NAME" in field_type.upper():
                    data.vendor_name = value
                elif "INVOICE" in field_type.upper() and "ID" in field_type.upper():
                    data.invoice_number = value
                elif "INVOICE" in field_type.upper() and "DATE" in field_type.upper():
                    data.invoice_date = value
                elif "DUE" in field_type.upper() and "DATE" in field_type.upper():
                    data.due_date = value
                elif "TOTAL" == field_type.upper():
                    try:
                        data.total_amount = float(value.replace("$", "").replace(",", ""))
                    except ValueError:
                        pass
                elif "SUBTOTAL" in field_type.upper():
                    try:
                        data.subtotal = float(value.replace("$", "").replace(",", ""))
                    except ValueError:
                        pass
                elif "TAX" in field_type.upper():
                    try:
                        data.tax_amount = float(value.replace("$", "").replace(",", ""))
                    except ValueError:
                        pass

                data.confidence_score = max(data.confidence_score, confidence)

            # Line items from tables
            for group in doc.get("LineItemGroups", []):
                for line in group.get("LineItems", []):
                    item = {}
                    for expense_field in line.get("LineItemExpenseFields", []):
                        ft = expense_field.get("Type", {}).get("Text", "")
                        fv = expense_field.get("ValueDetection", {}).get("Text", "")
                        if "ITEM" in ft.upper() or "DESCRIPTION" in ft.upper():
                            item["description"] = fv
                        elif "QUANTITY" in ft.upper():
                            try:
                                item["quantity"] = float(fv)
                            except ValueError:
                                pass
                        elif "UNIT_PRICE" in ft.upper() or "PRICE" in ft.upper():
                            try:
                                item["unit_price"] = float(fv.replace("$", "").replace(",", ""))
                            except ValueError:
                                pass
                        elif "EXPENSE_ROW" in ft.upper() or "AMOUNT" in ft.upper():
                            try:
                                item["amount"] = float(fv.replace("$", "").replace(",", ""))
                            except ValueError:
                                pass
                    if item:
                        data.line_items.append(item)

        data.raw_response = {"document_count": len(response.get("ExpenseDocuments", []))}
        return data


class OpenAIVisionProvider(OCRProvider):
    """OpenAI GPT-4o vision for invoice extraction (LLM fallback)."""

    EXTRACTION_PROMPT = """You are an invoice data extraction system. Analyze this invoice image and extract the following fields as JSON:

{
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "project_address": "string or null (the job site / project / ship-to address if different from vendor)",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "subtotal": number or null,
  "tax_amount": number or null,
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null,
      "product_code": "string or null"
    }
  ],
  "confidence_score": number between 0 and 1
}

IMPORTANT for "total_amount":
- This MUST be the amount currently being billed / requested for payment.
- For AIA G702/G703 forms (Application and Certificate for Payment), use the "CURRENT PAYMENT DUE" (line 8) — NOT the original contract sum, total completed to date, or total earned less retainage.
- For progress billing, use the amount due THIS period, not cumulative totals.
- For standard invoices, use the invoice total or balance due.

IMPORTANT for "project_address":
- Look for fields labeled: Project, Job Site, Ship To, Service Address, Location, Property.
- For AIA forms, this is the "PROJECT" field at the top.
- This is the physical location where work was performed, NOT the vendor's office address.

Return ONLY valid JSON. No markdown, no explanation. Set confidence_score based on how clearly you could read each field."""

    SPREADSHEET_PROMPT = """You are an invoice data extraction system. Analyze this invoice/bill spreadsheet data and extract the following fields as JSON:

{
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "project_address": "string or null (the job site / project address if present)",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "subtotal": number or null,
  "tax_amount": number or null,
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null,
      "product_code": "string or null"
    }
  ],
  "confidence_score": number between 0 and 1
}

Return ONLY valid JSON. No markdown, no explanation. Set confidence_score based on how clearly you could identify each field from the spreadsheet data.

Here is the spreadsheet content:
"""

    EMAIL_BODY_PROMPT = """You are an invoice data extraction system. Analyze this email body text and determine if it contains an invoice, bill, payment request, or statement of charges. Extract the following fields as JSON:

{
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "project_address": "string or null (the job site / project address if present)",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "subtotal": number or null,
  "tax_amount": number or null,
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null,
      "product_code": "string or null"
    }
  ],
  "confidence_score": number between 0 and 1,
  "is_invoice": true or false
}

IMPORTANT:
- Set "is_invoice" to true ONLY if the email body actually contains invoice / bill / payment request data (amounts, vendor, etc.)
- Set "is_invoice" to false if this is just a regular email, newsletter, notification, or does not contain billing information.
- If "is_invoice" is false, set confidence_score to 0.0 and leave all other fields null.
- For vendor_name, use the company/person requesting payment (may come from the email signature or body).

Return ONLY valid JSON. No markdown, no explanation.

Here is the email body text:
"""

    async def _get_api_key(self) -> str:
        """Get OpenAI API key from DB settings first, then fall back to .env."""
        try:
            from app.core.database import async_session_factory
            from app.core.security import decrypt_value
            from app.models.models import AppSetting
            from sqlalchemy import select

            async with async_session_factory() as db:
                result = await db.execute(
                    select(AppSetting).where(AppSetting.key == "openai_api_key")
                )
                setting = result.scalar_one_or_none()
                if setting:
                    key = decrypt_value(setting.value) if setting.is_encrypted else setting.value
                    if key:
                        return key
        except Exception as e:
            logger.debug(f"Could not read API key from DB: {e}")

        # Fall back to .env / config
        return settings.openai_api_key or ""

    def _convert_to_images(self, file_path: str) -> list[tuple[str, str]]:
        """Convert PDF/TIFF/BMP files to a list of (base64_png, mime) tuples.

        - PDF: renders each page as PNG via PyMuPDF (capped at 10 pages)
        - TIFF/BMP: converts to PNG via Pillow
        """
        ext = Path(file_path).suffix.lower()
        results: list[tuple[str, str]] = []

        if ext == ".pdf":
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(file_path)
                max_pages = min(len(doc), 10)
                for page_num in range(max_pages):
                    page = doc[page_num]
                    # Render at 2x resolution for better OCR quality
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    png_bytes = pix.tobytes("png")
                    b64 = base64.b64encode(png_bytes).decode("utf-8")
                    results.append((b64, "image/png"))
                doc.close()
                logger.info(f"Converted PDF to {len(results)} page image(s): {file_path}")
            except Exception as e:
                logger.error(f"Failed to convert PDF to images: {e}")
                # Fall back to sending raw PDF base64 — may work with newer GPT-4o
                with open(file_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                results.append((b64, "application/pdf"))

        elif ext in (".tiff", ".tif", ".bmp"):
            try:
                from PIL import Image
                import io as _io

                img = Image.open(file_path)
                # Handle multi-frame TIFF
                frames = []
                try:
                    for i in range(min(img.n_frames, 10)):
                        img.seek(i)
                        frames.append(img.copy())
                except (EOFError, AttributeError):
                    frames = [img]

                for frame in frames:
                    if frame.mode != "RGB":
                        frame = frame.convert("RGB")
                    buf = _io.BytesIO()
                    frame.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    results.append((b64, "image/png"))
                logger.info(f"Converted {ext} to {len(results)} PNG image(s): {file_path}")
            except Exception as e:
                logger.error(f"Failed to convert {ext} to PNG: {e}")

        return results

    def _spreadsheet_to_markdown(self, file_path: str) -> str:
        """Read an Excel or CSV file and convert to a Markdown table string."""
        import csv as csv_mod
        import io as _io
        ext = Path(file_path).suffix.lower()

        rows: list[list[str]] = []

        if ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    rows.append([str(cell) if cell is not None else "" for cell in row])
                wb.close()
            except Exception as e:
                logger.error(f"Failed to read Excel file: {e}")
                return ""
        else:
            # CSV
            try:
                with open(file_path, "rb") as f:
                    raw = f.read()
                text = None
                for enc in ("utf-8-sig", "cp1252", "latin-1"):
                    try:
                        text = raw.decode(enc)
                        break
                    except (UnicodeDecodeError, ValueError):
                        continue
                if text is None:
                    text = raw.decode("latin-1")
                reader = csv_mod.reader(_io.StringIO(text))
                rows = [row for row in reader]
            except Exception as e:
                logger.error(f"Failed to read CSV file: {e}")
                return ""

        if not rows:
            return ""

        # Build markdown table (cap at 200 rows to stay within token limits)
        capped = rows[:200]
        lines = []
        # Header
        lines.append("| " + " | ".join(capped[0]) + " |")
        lines.append("| " + " | ".join(["---"] * len(capped[0])) + " |")
        # Data rows
        for row in capped[1:]:
            # Pad or trim to header width
            padded = row + [""] * (len(capped[0]) - len(row))
            lines.append("| " + " | ".join(padded[:len(capped[0])]) + " |")

        return "\n".join(lines)

    async def _extract_from_spreadsheet(self, file_path: str) -> ExtractedInvoiceData:
        """Extract invoice data from a spreadsheet by converting to text and using GPT-4o."""
        from openai import AsyncOpenAI

        api_key = await self._get_api_key()
        if not api_key:
            raise ValueError("OpenAI API key not configured. Go to Settings > API Keys to add one.")
        client = AsyncOpenAI(api_key=api_key)

        md_table = self._spreadsheet_to_markdown(file_path)
        if not md_table:
            logger.error(f"Could not read spreadsheet: {file_path}")
            return ExtractedInvoiceData()

        logger.info(f"Extracting invoice from spreadsheet ({len(md_table)} chars): {file_path}")

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": self.SPREADSHEET_PROMPT + md_table,
                }
            ],
            max_tokens=2000,
            temperature=0,
        )

        return self._parse_response(response)

    async def extract_from_text(self, body_text: str) -> ExtractedInvoiceData:
        """Extract invoice data from an email body text using GPT-4o."""
        from openai import AsyncOpenAI

        api_key = await self._get_api_key()
        if not api_key:
            raise ValueError("OpenAI API key not configured. Go to Settings > API Keys to add one.")
        client = AsyncOpenAI(api_key=api_key)

        # Truncate very long bodies to stay within token limits
        text = body_text[:8000]
        logger.info(f"Extracting invoice from email body text ({len(text)} chars)")

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": self.EMAIL_BODY_PROMPT + text,
                }
            ],
            max_tokens=2000,
            temperature=0,
        )

        data = self._parse_response(response)

        # Check if GPT determined this is actually an invoice
        raw = data.raw_response or {}
        if not raw.get("is_invoice", False):
            logger.info("Email body text is not an invoice, returning empty result")
            data.confidence_score = 0.0
            data.vendor_name = None
            data.invoice_number = None
            data.total_amount = None

        return data

    def _parse_response(self, response) -> ExtractedInvoiceData:
        """Parse an OpenAI chat completion response into ExtractedInvoiceData."""
        data = ExtractedInvoiceData()
        try:
            content = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]

            parsed = json.loads(content)
            data.vendor_name = parsed.get("vendor_name")
            data.vendor_address = parsed.get("vendor_address")
            data.project_address = parsed.get("project_address")
            data.invoice_number = parsed.get("invoice_number")
            data.invoice_date = parsed.get("invoice_date")
            data.due_date = parsed.get("due_date")
            data.total_amount = parsed.get("total_amount")
            data.subtotal = parsed.get("subtotal")
            data.tax_amount = parsed.get("tax_amount")
            data.line_items = parsed.get("line_items", [])
            data.confidence_score = parsed.get("confidence_score", 0.5)
            data.raw_response = parsed
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            data.confidence_score = 0.0
        return data

    async def extract(self, file_path: str) -> ExtractedInvoiceData:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("openai not installed")
            return ExtractedInvoiceData()

        ext = Path(file_path).suffix.lower()

        # ── Spreadsheet path: convert to text, no vision needed ──
        if ext in (".xlsx", ".xls", ".csv"):
            return await self._extract_from_spreadsheet(file_path)

        api_key = await self._get_api_key()
        if not api_key:
            raise ValueError("OpenAI API key not configured. Go to Settings > API Keys to add one.")
        client = AsyncOpenAI(api_key=api_key)

        # ── Image conversion path: PDF, TIFF, BMP → PNG ──
        if ext in (".pdf", ".tiff", ".tif", ".bmp"):
            image_pairs = self._convert_to_images(file_path)
            if not image_pairs:
                raise ValueError(f"Failed to convert {ext} file to images for OCR")

            # Build multi-image content array
            content_parts = [{"type": "text", "text": self.EXTRACTION_PROMPT}]
            for b64, mime in image_pairs:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": "high",
                    },
                })

            logger.info(f"Sending {len(image_pairs)} image(s) to OpenAI for {file_path}")
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content_parts}],
                max_tokens=2000,
                temperature=0,
            )
            return self._parse_response(response)

        # ── Direct image path: PNG, JPG, JPEG ──
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        b64 = base64.b64encode(file_bytes).decode("utf-8")
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }.get(ext, "image/png")

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=2000,
            temperature=0,
        )
        return self._parse_response(response)


async def get_ocr_provider_async() -> OCRProvider:
    """Async factory — reads provider from DB settings, falls back to .env."""
    from app.core.database import async_session_factory
    from sqlalchemy import select as sa_select
    from app.models.models import AppSetting

    provider_name = settings.ocr_provider
    try:
        async with async_session_factory() as db:
            r = await db.execute(
                sa_select(AppSetting).where(AppSetting.key == "ocr_provider")
            )
            s = r.scalar_one_or_none()
            if s and s.value:
                provider_name = s.value
    except Exception:
        pass

    provider_map = {
        "azure": AzureDocumentIntelligenceProvider,
        "aws": AWSTextractProvider,
        "openai": OpenAIVisionProvider,
        "none": NoOCRProvider,
    }
    provider_cls = provider_map.get(provider_name, NoOCRProvider)
    return provider_cls()


def get_ocr_provider() -> OCRProvider:
    """Sync factory — uses .env config only (use get_ocr_provider_async when possible)."""
    provider_map = {
        "azure": AzureDocumentIntelligenceProvider,
        "aws": AWSTextractProvider,
        "openai": OpenAIVisionProvider,
        "none": NoOCRProvider,
    }
    provider_cls = provider_map.get(settings.ocr_provider, NoOCRProvider)
    return provider_cls()
