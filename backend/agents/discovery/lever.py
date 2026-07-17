import asyncio
import httpx
from datetime import datetime
from backend.schemas.models import Job

LEVER_API = "https://api.lever.co/v0/postings/{company}?mode=json"

async def fetch_lever_jobs(company_slug:str) -> list[Job]:
    url = LEVER_API.format(company=company_slug)

    #Use the async client session
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"⚠️ [Lever] Company slug '{company_slug}' returned 404. It has likely migrated.")
                return []
            raise e # Re-raise for 500, 403, etc.
        except Exception as e:
            print(f"❌ Connection error fetching Lever jobs for {company_slug}: {e}")
            return []

    jobs = []
    for item in data:
        location = item.get("categories",{}).get("location","Unknown")

        # Lever splits descriptions into a main text block and markdown-like lists
        description_parts = [
            item.get("descriptionPlain",""),
            *[l.get("content","") for l in item.get("lists",[])],
        ]

        jobs.append(
            Job(
                job_id=f"lv_{item['id']}",
                source="lever",
                company=company_slug,
                title=item["text"],
                location=location,
                url=item["hostedUrl"],
                raw_description="\n\n".join(filter(None,description_parts)),
                requires_login_to_apply=False,
                discovered_at=datetime.now()
            )
        )
    return jobs

# if __name__ == "__main__":
#     jobs_list = asyncio.run(fetch_lever_jobs("palantir"))
#     print(f"Successfully fetched {len(jobs_list)} jobs from Lever.")

#     if jobs_list:
#         print(f"Sample Job Title: {jobs_list[0].title}")