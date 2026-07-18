import asyncio
from pathlib import Path
from datetime import datetime
import aiosqlite
from backend.schemas.models import Job

# Enforce clean structural subdirectory organization rules
DB_PATH = Path("backend/data/applications.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT NOT NULL,
    raw_description TEXT,
    requires_login_to_apply INTEGER NOT NULL,
    discovered_at TEXT NOT NULL
);
"""


async def init_db() -> None:
    """Ensures directories exist and sets up the schema asynchronously."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(SCHEMA)
        await conn.commit()


async def save_jobs(jobs: list[Job]) -> int:
    """Insert new jobs asynchronously, skipping existing ones. Returns inserted row count."""
    await init_db()
    if not jobs:
        return 0

    inserted = 0
    # Establish a non-blocking asynchronous connection to SQLite
    async with aiosqlite.connect(DB_PATH) as conn:
        for job in jobs:
            async with conn.execute(
                "INSERT OR IGNORE INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.job_id,
                    job.source,
                    job.company,
                    job.title,
                    job.location,
                    job.url,
                    job.raw_description,
                    int(job.requires_login_to_apply),
                    job.discovered_at.isoformat(),
                ),
            ) as cursor:
                inserted += cursor.rowcount
        await conn.commit()
    return inserted


async def get_all_jobs() -> list[dict]:
    """Retrieve all jobs ordered by discovery timestamp without blocking the loop."""
    await init_db()
    async with aiosqlite.connect(DB_PATH) as conn:
        # Enforce dict row mapping factory styles natively
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM jobs ORDER BY discovered_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Test Suite execution block
if __name__ == "__main__":
    async def test_storage():
        print("⏳ Testing async storage layers...")
        mock_job = Job(
            job_id="gh_test_123",
            source="greenhouse",
            company="stripe",
            title="Async Database Engineer",
            location="Bangalore, India",
            url="https://stripe.com",
            raw_description="Build async applications.",
            requires_login_to_apply=False,
            discovered_at=datetime.now()
        )
        
        new_rows = await save_jobs([mock_job])
        print(f"🏁 Rows added: {new_rows} (Should be 0 if run a second time due to de-duplication)")
        
        all_records = await get_all_jobs()
        print(f"📋 Total items inside DB: {len(all_records)}")

    asyncio.run(test_storage())
