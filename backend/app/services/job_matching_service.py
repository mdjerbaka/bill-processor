"""Job matching engine — matches extracted invoices to jobs.

Strategy:
  1. Exact vendor name match in VendorJobMapping → auto-assign
  2. Fuzzy vendor name match → suggest with high confidence
  3. AI embedding similarity (line items vs job descriptions) → suggest
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Invoice,
    InvoiceStatus,
    Job,
    VendorJobMapping,
)
from app.schemas.schemas import JobMatchSuggestion

logger = logging.getLogger(__name__)


class JobMatchingService:
    """Matches invoices to jobs using rules and AI."""

    def __init__(self, db: AsyncSession, user_id: int = None):
        self.db = db
        self.user_id = user_id

    async def match_invoice(self, invoice: Invoice) -> list[JobMatchSuggestion]:
        """Try to match an invoice to a job. Returns ranked suggestions."""
        if not invoice.vendor_name:
            return []

        suggestions: list[JobMatchSuggestion] = []
        vendor = invoice.vendor_name.strip().lower()

        # Statuses that should never be overwritten by matching
        _finalized = (InvoiceStatus.APPROVED, InvoiceStatus.PAID, InvoiceStatus.SENT_TO_QB)

        # ── 1. Exact / pattern match from VendorJobMapping ──
        auto_match = await self._check_vendor_mappings(vendor)
        if auto_match:
            suggestions.extend(auto_match)
            # If there's exactly one auto-assign match, apply it
            auto_assigns = [s for s in auto_match if s.confidence >= 0.95]
            if len(auto_assigns) == 1 and invoice.status not in _finalized:
                invoice.job_id = auto_assigns[0].job_id
                invoice.match_method = "auto"
                invoice.status = InvoiceStatus.AUTO_MATCHED
                # Increment match count
                await self._increment_match_count(vendor, auto_assigns[0].job_id)
                await self.db.flush()
                return suggestions

        # ── 2. Address-based matching ──
        address_matches = await self._address_match(invoice)
        if address_matches:
            suggestions.extend(address_matches)
            # If exactly one high-confidence address match and no vendor mapping auto-assigned yet
            top_address = [s for s in address_matches if s.confidence >= 0.90]
            if len(top_address) == 1 and invoice.status not in _finalized and not invoice.job_id:
                invoice.job_id = top_address[0].job_id
                invoice.match_method = "address"
                invoice.status = InvoiceStatus.AUTO_MATCHED
                await self.db.flush()
                return suggestions

        # ── 3. Job name mentioned in invoice ──
        name_matches = await self._job_name_match(invoice)
        if name_matches:
            suggestions.extend(name_matches)
            top_name = [s for s in name_matches if s.confidence >= 0.90]
            if len(top_name) == 1 and invoice.status not in _finalized and not invoice.job_id:
                invoice.job_id = top_name[0].job_id
                invoice.match_method = "name"
                invoice.status = InvoiceStatus.AUTO_MATCHED
                await self.db.flush()
                return suggestions

        # ── 4. Fuzzy vendor name match against past invoices ──
        fuzzy_matches = await self._fuzzy_vendor_match(vendor)
        if fuzzy_matches:
            suggestions.extend(fuzzy_matches)

        # ── 5. If still no strong match, mark for review ──
        # Only change status for new/unprocessed invoices, not finalized ones
        if invoice.status not in _finalized:
            if not suggestions or all(s.confidence < 0.7 for s in suggestions):
                invoice.status = InvoiceStatus.NEEDS_REVIEW
            elif suggestions:
                invoice.status = InvoiceStatus.NEEDS_REVIEW  # Still needs confirmation
            await self.db.flush()

        # Deduplicate by job_id, keep highest confidence
        seen_jobs = {}
        for s in suggestions:
            if s.job_id not in seen_jobs or s.confidence > seen_jobs[s.job_id].confidence:
                seen_jobs[s.job_id] = s
        suggestions = sorted(seen_jobs.values(), key=lambda s: s.confidence, reverse=True)
        return suggestions[:5]  # Top 5

    async def _check_vendor_mappings(self, vendor_name: str) -> list[JobMatchSuggestion]:
        """Check the VendorJobMapping table for matches."""
        result = await self.db.execute(
            select(VendorJobMapping, Job)
            .join(Job, VendorJobMapping.job_id == Job.id)
            .where(Job.is_active == True, Job.user_id == self.user_id)
        )
        rows = result.all()

        suggestions = []
        for mapping, job in rows:
            pattern = mapping.vendor_name_pattern.strip().lower()
            # Check exact match or pattern match
            if pattern == vendor_name or pattern in vendor_name or vendor_name in pattern:
                confidence = 0.98 if mapping.auto_assign else 0.85
                suggestions.append(
                    JobMatchSuggestion(
                        job_id=job.id,
                        job_name=job.name,
                        confidence=confidence,
                        reason=f"Vendor rule: '{mapping.vendor_name_pattern}' → {job.name}",
                    )
                )
            # Regex pattern match
            elif self._is_regex_match(pattern, vendor_name):
                suggestions.append(
                    JobMatchSuggestion(
                        job_id=job.id,
                        job_name=job.name,
                        confidence=0.80,
                        reason=f"Pattern match: '{mapping.vendor_name_pattern}'",
                    )
                )

        return suggestions

    async def _address_match(self, invoice: Invoice) -> list[JobMatchSuggestion]:
        """Match invoice to jobs by comparing addresses in extracted data."""
        # Gather all address-like text from the invoice
        address_texts = []
        if invoice.vendor_address:
            address_texts.append(invoice.vendor_address.lower())
        # Check extracted_data for any address references
        if invoice.extracted_data and isinstance(invoice.extracted_data, dict):
            for key in ("vendor_address", "job_address", "project_address", "service_address", "site_address"):
                val = invoice.extracted_data.get(key)
                if val:
                    address_texts.append(str(val).lower())

        if not address_texts:
            return []

        # Load all active jobs that have an address
        result = await self.db.execute(
            select(Job).where(Job.is_active == True, Job.user_id == self.user_id, Job.address.is_not(None), Job.address != "")
        )
        jobs = result.scalars().all()

        suggestions = []
        for job in jobs:
            if not job.address:
                continue
            # Extract street portion (first part before first comma)
            job_street = job.address.split(",")[0].strip().lower()
            if len(job_street) < 5:
                continue
            # Normalize common abbreviations
            job_street_norm = self._normalize_address(job_street)
            for addr_text in address_texts:
                addr_norm = self._normalize_address(addr_text)
                if job_street_norm in addr_norm or addr_norm in job_street_norm:
                    suggestions.append(
                        JobMatchSuggestion(
                            job_id=job.id,
                            job_name=job.name,
                            confidence=0.92,
                            reason=f"Address match: '{job.address.split(',')[0]}' found in invoice",
                        )
                    )
                    break

        return suggestions

    async def _job_name_match(self, invoice: Invoice) -> list[JobMatchSuggestion]:
        """Check if any job name or key part of it appears in the extracted invoice text."""
        # Build a searchable text block from the invoice
        search_text = " ".join(filter(None, [
            invoice.vendor_name,
            invoice.vendor_address,
            str(invoice.extracted_data) if invoice.extracted_data else None,
        ])).lower()

        if not search_text or len(search_text) < 10:
            return []

        # Load all active jobs
        result = await self.db.execute(
            select(Job).where(Job.is_active == True, Job.user_id == self.user_id)
        )
        jobs = result.scalars().all()

        suggestions = []
        for job in jobs:
            # Extract meaningful tokens from job name (skip generic words)
            name_lower = job.name.lower()
            # Try matching on the street address portion of the job name (e.g. "83 Northside Road")
            # Many Buildertrend job names include the address
            address_part = job.address.split(",")[0].strip().lower() if job.address else ""
            if address_part and len(address_part) > 8 and address_part in search_text:
                suggestions.append(
                    JobMatchSuggestion(
                        job_id=job.id,
                        job_name=job.name,
                        confidence=0.88,
                        reason=f"Job address '{address_part}' mentioned in invoice data",
                    )
                )
                continue

            # Try matching distinct words from job name (skip very short or common words)
            skip_words = {"job", "the", "and", "for", "inc", "llc", "co", "corp", "st", "rd", "ave", "dr", "ln"}
            tokens = [w for w in re.split(r'[\s,/\-]+', name_lower) if len(w) > 3 and w not in skip_words]
            if len(tokens) >= 2:
                # Check if majority of significant tokens appear in the text
                found = sum(1 for t in tokens if t in search_text)
                ratio = found / len(tokens) if tokens else 0
                if ratio >= 0.6 and found >= 2:
                    suggestions.append(
                        JobMatchSuggestion(
                            job_id=job.id,
                            job_name=job.name,
                            confidence=min(0.5 + ratio * 0.4, 0.85),
                            reason=f"Job name tokens matched ({found}/{len(tokens)}) in invoice data",
                        )
                    )

        return suggestions

    @staticmethod
    def _normalize_address(addr: str) -> str:
        """Normalize an address string for comparison."""
        replacements = {
            " street": " st", " road": " rd", " avenue": " ave",
            " drive": " dr", " lane": " ln", " boulevard": " blvd",
            " circle": " cir", " court": " ct", " place": " pl",
            " terrace": " ter", " highway": " hwy",
        }
        addr = addr.lower().strip()
        for full, abbrev in replacements.items():
            addr = addr.replace(full, abbrev)
        # Remove extra whitespace
        addr = re.sub(r'\s+', ' ', addr)
        return addr

    async def _fuzzy_vendor_match(self, vendor_name: str) -> list[JobMatchSuggestion]:
        """Look at historical invoice-to-job assignments for similar vendor names."""
        # Find past invoices with this vendor (or similar) that were assigned to jobs
        result = await self.db.execute(
            select(Invoice.job_id, Job.name, func.count(Invoice.id).label("cnt"))
            .join(Job, Invoice.job_id == Job.id)
            .where(
                Invoice.vendor_name.ilike(f"%{vendor_name}%"),
                Invoice.job_id.is_not(None),
                Invoice.status.in_([
                    InvoiceStatus.APPROVED,
                    InvoiceStatus.SENT_TO_QB,
                    InvoiceStatus.PAID,
                ]),
            )
            .group_by(Invoice.job_id, Job.name)
            .order_by(func.count(Invoice.id).desc())
            .limit(5)
        )
        rows = result.all()

        suggestions = []
        for job_id, job_name, count in rows:
            # Higher count = higher confidence
            confidence = min(0.5 + (count * 0.1), 0.85)
            suggestions.append(
                JobMatchSuggestion(
                    job_id=job_id,
                    job_name=job_name,
                    confidence=confidence,
                    reason=f"Historical: {count} past invoice(s) from this vendor → {job_name}",
                )
            )

        return suggestions

    async def _increment_match_count(self, vendor_name: str, job_id: int) -> None:
        """Increment the match count for a vendor-job mapping."""
        result = await self.db.execute(
            select(VendorJobMapping).where(
                func.lower(VendorJobMapping.vendor_name_pattern) == vendor_name,
                VendorJobMapping.job_id == job_id,
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping:
            mapping.match_count += 1

    async def learn_from_assignment(
        self, vendor_name: str, job_id: int, auto_assign: bool = False
    ) -> None:
        """When a user manually assigns a vendor to a job, save the mapping."""
        if not vendor_name:
            return

        vendor_lower = vendor_name.strip().lower()

        # Check if mapping already exists
        result = await self.db.execute(
            select(VendorJobMapping).where(
                func.lower(VendorJobMapping.vendor_name_pattern) == vendor_lower,
                VendorJobMapping.job_id == job_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.match_count += 1
            if auto_assign and not existing.auto_assign:
                existing.auto_assign = True
        else:
            new_mapping = VendorJobMapping(
                vendor_name_pattern=vendor_name.strip(),
                job_id=job_id,
                auto_assign=auto_assign,
                match_count=1,
            )
            self.db.add(new_mapping)

        await self.db.flush()

    @staticmethod
    def _is_regex_match(pattern: str, text: str) -> bool:
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False
