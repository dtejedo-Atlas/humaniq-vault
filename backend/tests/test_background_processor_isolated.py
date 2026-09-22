"""Isolated tests for BackgroundProcessor persistence and completion semantics."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from background_processor import BackgroundProcessor  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture
async def isolated_db():
    load_dotenv(BACKEND_DIR / ".env")
    mongo_url = os.environ.get("MONGO_URL")
    assert mongo_url, "MONGO_URL no configurada"
    db_name = f"test_bg_processor_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    try:
        yield db
    finally:
        await client.drop_database(db_name)
        client.close()


async def test_processing_persists_across_instances_and_reports_failures(isolated_db):
    processor = BackgroundProcessor(max_concurrent=2)
    processor.db = isolated_db
    await processor.initialize()

    async def controlled_process(job, file_data, file_metadata):
        await asyncio.sleep(0.05)
        if "fail" in file_metadata.get("file_name", ""):
            return {
                "status": "failed",
                "errors": [{"type": "forced", "stage": "ai_parsing", "message": "forced failure"}],
                "warnings": [],
            }
        return {
            "status": "success",
            "candidate_id": f"cand-{job.job_id[:6]}",
            "extracted_name": "Synthetic User",
            "errors": [],
            "warnings": [],
        }

    await processor.start_workers(controlled_process)
    batch = await processor.create_batch("user-1", 3)
    await processor.add_job(batch.batch_id, "ok-1.pdf", b"ok1", "application/pdf", "user-1")
    await processor.add_job(batch.batch_id, "fail-1.pdf", b"bad", "application/pdf", "user-1")

    # Before finalize_batch, submission_complete=False must keep is_complete false.
    await processor.queue.join()
    status_before_finalize = await processor.get_batch_status(batch.batch_id)
    assert status_before_finalize["is_complete"] is False

    submitted = [
        {"file_name": "ok-1.pdf", "status": "queued"},
        {"file_name": "fail-1.pdf", "status": "queued"},
        {"file_name": "reject-1.doc", "status": "rejected", "reason": "Formato no soportado"},
    ]
    await processor.finalize_batch(batch.batch_id, submitted)
    status_after_finalize = await processor.get_batch_status(batch.batch_id)

    assert status_after_finalize["is_complete"] is True
    assert status_after_finalize["stats"]["completed"] == 1
    assert status_after_finalize["stats"]["failed"] == 1
    assert status_after_finalize["stats"]["rejected"] == 1
    assert len(status_after_finalize["rejected_files"]) == 1
    failed_jobs = [j for j in status_after_finalize["jobs"] if j.get("status") == "failed"]
    assert failed_jobs and failed_jobs[0].get("errors")

    # Separate processor instance must read persisted completion state.
    processor_2 = BackgroundProcessor(max_concurrent=1)
    processor_2.db = isolated_db
    await processor_2.initialize()
    status_from_second_instance = await processor_2.get_batch_status(batch.batch_id)
    assert status_from_second_instance["is_complete"] is True
    assert status_from_second_instance["stats"]["completed"] == 1
    assert status_from_second_instance["stats"]["failed"] == 1

    processor.workers_running = False
    processor_2.workers_running = False
