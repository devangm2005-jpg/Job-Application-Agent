import asyncio
import httpx
from datetime import datetime
from backend.schemas.models import Job

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true"

async def fetch_ashby_jobs(company_slug:str) -> list[Job]:
    url = ASHBY_API.format(company=company_slug)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            print(f"⚠️ [Ashby] '{company_slug}' returned {e.response.status_code}")
            return []
        except Exception as e:
            print(f"❌ Connection error fetching Ashby jobs for {company_slug}: {e}")
            return []
        

    jobs = []

    for item in data.get("jobs",[]):
        location = item.get("location","Unknown")
        description = item.get("descriptionPlain") or item.get("descriptionHtml","")

        job_url = item.get("JobUrl") or item.get("applyUrl","")

        jobs.append(
            Job(
                job_id=f"ab_{item['id']}",
                source="ashby",
                company=company_slug,
                title=item['title'],
                location=location,
                url=job_url,
                raw_description=description,
                requires_login_to_apply=False,
                discovered_at=datetime.now(),
            )
        )

    return jobs

# Execution Block to immediately verify your migrated companies
if __name__ == "__main__":
    # Testing with Figma or Vercel, which actively use Ashby
    jobs_list = asyncio.run(fetch_ashby_jobs("linear"))
    print(f"🎉 Successfully fetched {len(jobs_list)} jobs from Ashby!")

    if jobs_list:
        print(f"📋 First Job Found: {jobs_list[0].title} in {jobs_list[0].location}")