import asyncio
import httpx
from backend.config.companies import COMPANIES

CHECK_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


async def verify_one(client: httpx.AsyncClient, source: str, slug: str) -> tuple[str, str, bool, int]:
    url = CHECK_URLS[source].format(slug=slug)
    try:
        response = await client.get(url, timeout=10.0)
        return (source, slug, response.status_code == 200, response.status_code)
    except Exception:
        return (source, slug, False, 0)


async def verify_all() -> None:
    async with httpx.AsyncClient() as client:
        tasks = [
            verify_one(client, source, slug)
            for source, slugs in COMPANIES.items()
            for slug in slugs
        ]
        results = await asyncio.gather(*tasks)

    for source, slug, ok, status in results:
        icon = "✅" if ok else "❌"
        print(f"{icon} [{source}] {slug} — HTTP {status}")


if __name__ == "__main__":
    asyncio.run(verify_all())