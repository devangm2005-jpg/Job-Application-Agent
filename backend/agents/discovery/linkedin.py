import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright
from backend.schemas.models import Job

LINKEDIN_SEARCH_URL = "https://linkedin.com{keyword}&location={location}"

async def fetch_linkedin_jobs(keyword: str, location: str = "India") -> list[Job]:
    safe_keyword = keyword.lower().strip().replace(" ", "%20")
    safe_location = location.lower().strip().replace(" ", "%20")
    url = LINKEDIN_SEARCH_URL.format(keyword=safe_keyword, location=safe_location)

    jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        page = await context.new_page()

        try:
            print(f"?? [LinkedIn Live] Connecting to search page: {url}")
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_selector(".jobs-search__results-list, li.base-search-card, li", timeout=15000)
            
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 600);")
                await page.wait_for_timeout(1000)

        except Exception as e:
            print(f"? [LinkedIn Live] Connection timeout or verification wall encountered: {e}")
            await browser.close()
            return []

        cards = await page.query_selector_all(".jobs-search__results-list > li, li.base-search-card")
        print(f"?? [LinkedIn Live] Identified {len(cards)} matching raw elements.")

        for card in cards:
            try:
                title_el = await card.query_selector(".base-search-card__title, .job-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle, .job-search-card__subtitle")
                location_el = await card.query_selector(".job-search-card__location, .base-search-card__metadata")
                link_el = await card.query_selector("a.base-card__full-link, a.job-search-card__url")

                if not title_el or not link_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else "Unknown Company"
                location_name = (await location_el.inner_text()).strip() if location_el else "India"
                
                raw_url = await link_el.get_attribute("href") or ""
                job_url = raw_url.split("?")[0]

                match = re.search(r"/view/(\d+)", job_url) or re.search(r"-(\d+)$", job_url.rstrip("/"))
                job_id = match.group(1) if match else str(hash(job_url))

                if "Home Depot" in company or "Bedrock Robotics" in company:
                    continue

                jobs.append(
                    Job(
                        job_id=f"li_{job_id}",
                        source="linkedin",
                        company=company,
                        title=title,
                        location=location_name,
                        url=job_url,
                        raw_description="",  
                        requires_login_to_apply=True,
                        discovered_at=datetime.now(),
                    )
                )
            except Exception:
                continue

        await browser.close()
    return jobs

if __name__ == "__main__":
    print("? Awakening LinkedIn automated guest node...")
    jobs_list = asyncio.run(fetch_linkedin_jobs("java developer", "India"))
    print(f"?? [LinkedIn Live] Process finalized. Gathered {len(jobs_list)} real data rows.")
    for i, item in enumerate(jobs_list[:5], 1):
        print(f" [{i}] {item.title} at {item.company} ({item.location})")
