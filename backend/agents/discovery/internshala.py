import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from backend.schemas.models import Job

INTERNSHALA_SEARCH_URL = "https://internshala.com/internships/{keyword}-internship"

HEADERS =  {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

async def fetch_internshala_jobs(keyword: str) -> list[Job]:
    formatted_keyword = keyword.lower().strip().replace(" ", "%20")
    url = INTERNSHALA_SEARCH_URL.format(keyword=formatted_keyword)

    async with httpx.AsyncClient(timeout=15,headers=HEADERS,follow_redirects=True) as client:
        try:
            response = await client.get(url)
            if response.status_code == 403:
                print(f"⚠️ [Internshala] Bot detection blocked the request (403) for '{keyword}'.")
                return []
            response.raise_for_status()
        except Exception as e:
            print(f"❌ [Internshala] fetch failed for '{keyword}': {e}")
            return []
        
    
    soup = BeautifulSoup(response.text, "html.parser")
    # NOTE: unverified against live DOM — Internshala's markup changes over time.
    # If this returns 0 results, open the URL in a browser, inspect a listing
    # card in devtools, and update these three selectors first.
    listings = soup.select(".internship_meta_container, .individual_internship")

    jobs = []

    for listing in listings:
        title_tag = listing.select_one(".profile a, .job-internship-name a")
        company_tag = listing.select_one(".company_name a, .company-name")
        location_tag = listing.select_one(".location_link, #location_names")

        if not title_tag:
            continue

        relative_url = title_tag.get("href","")
        job_url = f"https://internshala.com{relative_url}"
        job_id = relative_url.split("/")[-1] if "/" in relative_url else "unknown"

        company_name = company_tag.get_text(strip=True) if company_tag else "Unknown"
        title_name = title_tag.get_text(strip=True)
        location_name = location_tag.get_text(strip=True) if location_tag else "Remote / WFH"

        jobs.append(
            Job(
                job_id = f"is_{job_id}",
                source = "internshala",
                company=company_name,
                title=title_name,
                location=location_name,
                url = job_url,
                raw_description="",
                requires_login_to_apply=True,
                discovered_at=datetime.now(),
            )
        )

    return jobs

if __name__ == "__main__":
    jobs_list = asyncio.run(fetch_internshala_jobs("python"))
    print(f"🎉 Fetched {len(jobs_list)} entries from Internshala.")
    for i, item in enumerate(jobs_list[:3], 1):
        print(f" [{i}] {item.title} -> {item.company} ({item.location})")