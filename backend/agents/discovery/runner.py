import asyncio
from backend.config.companies import COMPANIES
from backend.agents.discovery.greenhouse import fetch_greenhouse_jobs
from backend.agents.discovery.lever import fetch_lever_jobs
from backend.agents.discovery.ashby import fetch_ashby_jobs
from backend.agents.discovery.storage import save_jobs
from backend.schemas.models import Job

FETCHERS = {
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
    "ashby": fetch_ashby_jobs,
}


async def discover_all() -> list[Job]:
    tasks = []
    task_metadata = []

    print(f"📦 Probing {len(COMPANIES)} companies across {len(FETCHERS)} ATS platforms "
          f"({len(COMPANIES) * len(FETCHERS)} total requests)...")

    for slug in COMPANIES:
        for platform_name, fetch_fn in FETCHERS.items():
            tasks.append(fetch_fn(slug))
            task_metadata.append({"company": slug, "platform": platform_name})

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: list[Job] = []
    print("\n👑 --- VERIFIED LIVE JOBS DETECTED --- 👑")

    for meta, result in zip(task_metadata, results):
        if isinstance(result, Exception) or not result:
            continue
        print(f"✅ [SUCCESS] '{meta['company']}' hosting {len(result)} jobs on {meta['platform'].upper()}")
        all_jobs.extend(result)

    print("----------------------------------------\n")
    return all_jobs


async def run_discovery() -> None:
    print("🔎 Starting flexible multi-platform discovery runner...")
    jobs = await discover_all()

    if not jobs:
        print("⚠️ No active listings discovered this run.")
        return

    print(f"🏁 {len(jobs)} active jobs discovered across valid portals.")
    new_count = await save_jobs(jobs)
    print(f"✅ Database sync complete: {new_count} new job listings saved.")


if __name__ == "__main__":
    asyncio.run(run_discovery())