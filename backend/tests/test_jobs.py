"""Jobs endpoint tests."""

from __future__ import annotations

import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Job, JobSource, VendorJobMapping


async def _create_job(db: AsyncSession, name="Job A", code="J-001") -> Job:
    job = Job(name=name, code=code, source=JobSource.MANUAL, is_active=True)
    db.add(job)
    await db.flush()
    return job


# ── CRUD ─────────────────────────────────────────────────────────

class TestJobCRUD:

    async def test_create_job(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/jobs",
            json={"name": "New Job", "code": "N-001", "address": "123 Main St"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Job"
        assert data["address"] == "123 Main St"

    async def test_list_jobs(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_job(db_session)
        await db_session.commit()
        resp = await client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_jobs_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_update_job(
        self, client: AsyncClient, auth_headers, db_session
    ):
        job = await _create_job(db_session)
        await db_session.commit()
        resp = await client.put(
            f"/api/v1/jobs/{job.id}",
            json={"name": "Updated", "code": "U-001", "address": "456 Oak"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    async def test_update_job_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/jobs/9999",
            json={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_delete_soft_deactivates(
        self, client: AsyncClient, auth_headers, db_session
    ):
        job = await _create_job(db_session)
        await db_session.commit()
        resp = await client.delete(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        assert resp.status_code == 200

        # Should not appear in active-only list
        resp2 = await client.get(
            "/api/v1/jobs", params={"active_only": True}, headers=auth_headers
        )
        assert all(j["id"] != job.id for j in resp2.json()["items"])

    async def test_delete_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.delete("/api/v1/jobs/9999", headers=auth_headers)
        assert resp.status_code == 404


# ── CSV Import ───────────────────────────────────────────────────

class TestJobCSVImport:

    async def test_import_valid_csv(self, client: AsyncClient, auth_headers):
        csv_content = b"Job Name,Job Code\nHouse Reno,HR-01\nKitchen,KT-02\n"
        resp = await client.post(
            "/api/v1/jobs/import-csv",
            files={"file": ("jobs.csv", csv_content, "text/csv")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2

    async def test_import_skips_duplicates(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_job(db_session, name="House Reno")
        await db_session.commit()
        csv_content = b"Job Name,Code\nHouse Reno,HR-01\nNew Job,NJ-01\n"
        resp = await client.post(
            "/api/v1/jobs/import-csv",
            files={"file": ("jobs.csv", csv_content, "text/csv")},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1


# ── Vendor Mappings ──────────────────────────────────────────────

class TestVendorMappings:

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/jobs/vendor-mappings", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_mapping(
        self, client: AsyncClient, auth_headers, db_session
    ):
        job = await _create_job(db_session)
        await db_session.commit()
        resp = await client.post(
            "/api/v1/jobs/vendor-mappings",
            json={"vendor_name_pattern": "Acme*", "job_id": job.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["vendor_name_pattern"] == "Acme*"

    async def test_create_mapping_invalid_job(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/jobs/vendor-mappings",
            json={"vendor_name_pattern": "X", "job_id": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_delete_mapping(
        self, client: AsyncClient, auth_headers, db_session
    ):
        job = await _create_job(db_session)
        mapping = VendorJobMapping(
            vendor_name_pattern="Acme", job_id=job.id, auto_assign=False, match_count=0,
        )
        db_session.add(mapping)
        await db_session.flush()
        await db_session.commit()
        resp = await client.delete(
            f"/api/v1/jobs/vendor-mappings/{mapping.id}", headers=auth_headers
        )
        assert resp.status_code == 200

    async def test_delete_mapping_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.delete(
            "/api/v1/jobs/vendor-mappings/9999", headers=auth_headers
        )
        assert resp.status_code == 404
