"""Job management routes."""

from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import Job, JobSource, User, VendorJobMapping
from app.schemas.schemas import (
    JobCreate,
    JobListResponse,
    JobSchema,
    VendorJobMappingCreate,
    VendorJobMappingSchema,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all jobs."""
    query = select(Job).where(Job.is_junked == False)
    if active_only:
        query = query.where(Job.is_active == True)
    query = query.order_by(Job.name.asc())

    result = await db.execute(query)
    jobs = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Job.id)).where(Job.is_junked == False).where(Job.is_active == True) if active_only
        else select(func.count(Job.id)).where(Job.is_junked == False)
    )
    total = count_result.scalar()

    return JobListResponse(
        items=[JobSchema.model_validate(j) for j in jobs],
        total=total,
    )


@router.post("", response_model=JobSchema)
async def create_job(
    req: JobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new job."""
    job = Job(
        name=req.name,
        code=req.code,
        description=req.description,
        address=req.address,
        source=JobSource.MANUAL,
    )
    db.add(job)
    await db.flush()
    return JobSchema.model_validate(job)


# ── Static path routes MUST come before /{job_id} to avoid FastAPI matching them as path params ──

@router.delete("/imported")
async def delete_imported_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete all jobs imported from CSV/XLSX (preserves manually created jobs)."""
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        select(Job).where(Job.source == JobSource.BUILDERTREND_CSV)
    )
    jobs = result.scalars().all()
    job_ids = [j.id for j in jobs]
    count = len(job_ids)

    if job_ids:
        # Delete vendor mappings that reference these jobs first (FK constraint)
        await db.execute(
            sa_delete(VendorJobMapping).where(VendorJobMapping.job_id.in_(job_ids))
        )
        # Now delete the jobs
        await db.execute(
            sa_delete(Job).where(Job.id.in_(job_ids))
        )
    await db.flush()
    return {"deleted": count}


@router.post("/import-csv")
async def import_jobs_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import jobs from a CSV or XLSX file (Buildertrend export)."""
    filename = (file.filename or "").lower()
    content = await file.read()

    if filename.endswith((".xlsx", ".xls")):
        # Parse Excel
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        # Find the real header row — skip title/blank rows until we find one
        # that contains known column names like "Job Name", "Name", "Project Name"
        known_headers = {"job name", "project name", "name", "job code", "street address", "city", "state"}
        header = None
        for raw_row in rows_iter:
            candidate = [str(c or "").strip() for c in raw_row]
            candidate_lower = {c.lower() for c in candidate if c}
            if candidate_lower & known_headers:
                header = candidate
                break
        if not header:
            wb.close()
            raise HTTPException(status_code=400, detail="Could not find a header row with recognized column names (e.g. 'Job Name')")

        data_rows = []
        for row in rows_iter:
            data_rows.append({header[i]: str(row[i] or "").strip() for i in range(len(header)) if i < len(row)})
        wb.close()
    else:
        # Parse CSV with encoding fallback
        text = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except (UnicodeDecodeError, ValueError):
                continue
        if text is None:
            text = content.decode("latin-1")  # latin-1 never fails
        reader = csv.DictReader(io.StringIO(text))
        data_rows = list(reader)

    imported = 0
    skipped = 0

    for row in data_rows:
        # Try common column names for job name
        name = (
            row.get("Job Name")
            or row.get("Project Name")
            or row.get("Name")
            or row.get("name")
            or ""
        ).strip()
        code = (
            row.get("Job Code")
            or row.get("Code")
            or row.get("Project Code")
            or row.get("code")
            or ""
        ).strip()

        if not name:
            skipped += 1
            continue

        # Build full address from Buildertrend columns
        street = (row.get("Street Address") or row.get("Address") or "").strip()
        city = (row.get("City") or "").strip()
        state = (row.get("State") or "").strip()
        zipcode = (row.get("Zip") or row.get("Zip Code") or "").strip()
        address_parts = [p for p in [street, city, state, zipcode] if p]
        address = ", ".join(address_parts) if address_parts else None

        # Build description from client / PM info
        desc_parts = []
        pm = (row.get("Project Manager") or "").strip()
        clients = (row.get("Clients") or "").strip()
        client_phone = (row.get("Client Phone") or "").strip()
        client_email = (row.get("Client Email") or "").strip()
        if pm:
            desc_parts.append(f"PM: {pm}")
        if clients:
            desc_parts.append(f"Client: {clients}")
        if client_phone:
            desc_parts.append(f"Phone: {client_phone}")
        if client_email:
            desc_parts.append(f"Email: {client_email}")
        description = " | ".join(desc_parts) if desc_parts else None

        # Check for duplicate by name
        existing = await db.execute(
            select(Job).where(func.lower(Job.name) == name.lower())
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        job = Job(
            name=name,
            code=code or None,
            address=address,
            description=description,
            source=JobSource.BUILDERTREND_CSV,
        )
        db.add(job)
        imported += 1

    await db.flush()
    return {"imported": imported, "skipped": skipped}


@router.put("/{job_id}", response_model=JobSchema)
async def update_job(
    job_id: int,
    req: JobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.name = req.name
    job.code = req.code
    job.description = req.description
    job.address = req.address
    await db.flush()
    return JobSchema.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a job to the junk bin."""
    from datetime import datetime, timezone
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_junked = True
    job.junked_at = datetime.now(timezone.utc)
    await db.flush()
    return {"detail": "Job sent to junk"}


@router.post("/{job_id}/restore")
async def restore_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Restore a job from the junk bin."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_junked = False
    job.junked_at = None
    await db.flush()
    return {"detail": "Job restored"}


# ── Vendor → Job Mappings ────────────────────────────────

@router.get("/vendor-mappings", response_model=list[VendorJobMappingSchema])
async def list_vendor_mappings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all vendor-to-job mappings."""
    result = await db.execute(
        select(VendorJobMapping, Job)
        .join(Job, VendorJobMapping.job_id == Job.id)
        .order_by(VendorJobMapping.vendor_name_pattern.asc())
    )
    rows = result.all()
    return [
        VendorJobMappingSchema(
            id=m.id,
            vendor_name_pattern=m.vendor_name_pattern,
            job_id=m.job_id,
            job_name=j.name,
            auto_assign=m.auto_assign,
            match_count=m.match_count,
            created_at=m.created_at,
        )
        for m, j in rows
    ]


@router.post("/vendor-mappings", response_model=VendorJobMappingSchema)
async def create_vendor_mapping(
    req: VendorJobMappingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new vendor-to-job mapping rule."""
    # Verify job exists
    result = await db.execute(select(Job).where(Job.id == req.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    mapping = VendorJobMapping(
        vendor_name_pattern=req.vendor_name_pattern,
        job_id=req.job_id,
        auto_assign=req.auto_assign,
    )
    db.add(mapping)
    await db.flush()

    return VendorJobMappingSchema(
        id=mapping.id,
        vendor_name_pattern=mapping.vendor_name_pattern,
        job_id=mapping.job_id,
        job_name=job.name,
        auto_assign=mapping.auto_assign,
        match_count=mapping.match_count,
        created_at=mapping.created_at,
    )


@router.delete("/vendor-mappings/{mapping_id}")
async def delete_vendor_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a vendor-to-job mapping rule."""
    result = await db.execute(
        select(VendorJobMapping).where(VendorJobMapping.id == mapping_id)
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    await db.delete(mapping)
    await db.flush()
    return {"detail": "Mapping deleted"}
