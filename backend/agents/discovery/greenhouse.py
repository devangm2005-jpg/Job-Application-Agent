import asyncio
import httpx
from datetime import datetime
from backend.schemas.models import Job

GREENHOUSE_LIST_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            print(f"📡 [Greenhouse] Connecting to real-time gateway for: '{company_board_token}'")
            response = await client.get(list_url)
            
            # FIX: Intercept status errors before attempting to unpack empty responses
            response.raise_for_status()
            data = response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"⚠️ [Greenhouse] Board '{company_board_token}' returned 404. Company does not use Greenhouse.")
                return []
            print(f"❌ [Greenhouse] HTTP Error {e.response.status_code} for '{company_board_token}': {e}")
            return []
        except Exception as e:
            print(f"❌ [Greenhouse] Network link failure for '{company_board_token}': {e}")
            return []
        
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
        for item in raw_jobs:
            # FIX: Grabbing description natively out of inline payloads instantly
            description = item.get("content", "")
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
if __name__ == "__main__":
    jobs_list = asyncio.run(fetch_greenhouse_jobs("Calendly"))
    # print(f"Successfully fetched {jobs_list[0].title} jobs.")
    print(f"Successfully fetched {len(jobs_list)} jobs.")
