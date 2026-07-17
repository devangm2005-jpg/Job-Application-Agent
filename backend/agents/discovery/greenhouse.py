import asyncio
import httpx
from datetime import datetime
from backend.schemas.models import Job

GREENHOUSE_LIST_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
GREENHOUSE_DETAIL_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"

async def fetch_job_description(client: httpx.AsyncClient, company: str, job_id: int) -> str:
    """Helper to fetch a single job description concurrently."""
    try:
        url = GREENHOUSE_DETAIL_API.format(company=company, job_id=job_id)
        response = await client.get(url, timeout=5.0)
        if response.status_code == 200:
            return response.json().get("content", "")
    except Exception:
        pass
    return ""

async def fetch_greenhouse_jobs(company_board_token: str) -> list[Job]:
    list_url = GREENHOUSE_LIST_API.format(company=company_board_token)
    
    # Use a single client session for connection pooling
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(list_url)
        response.raise_for_status()
        data = response.json()
        
        raw_jobs = data.get("jobs", [])
        if not raw_jobs:
            return []

        # Kick off all description requests concurrently
        tasks = [
            fetch_job_description(client, company_board_token, item["id"])
            for item in raw_jobs
        ]
        descriptions = await asyncio.gather(*tasks)

        # Build your Job objects
        jobs = []
        for item, description in zip(raw_jobs, descriptions):
            jobs.append(
                Job(
                    job_id=f"gh_{item['id']}",
                    source="greenhouse",
                    company=company_board_token,
                    title=item["title"],
                    location=item.get("location", {}).get("name", "Unknown"),
                    url=item["absolute_url"],
                    raw_description=description,
                    requires_login_to_apply=False,
                    discovered_at=datetime.now(),
                )
            )
        return jobs

# Run the async loop
# if __name__ == "__main__":
#     jobs_list = asyncio.run(fetch_greenhouse_jobs("stripe"))
#     print(f"Successfully fetched {jobs_list[0]} jobs.")
