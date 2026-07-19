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
            for slug in COMPANIES
            for source in CHECK_URLS
        ]
        results = await asyncio.gather(*tasks)

    print("\n✅ CONFIRMED LIVE:")
    confirmed = {}
    for source, slug, ok, status in results:
        if ok:
            confirmed[slug] = source
            print(f"  [{source}] {slug}")

    print(f"\n📊 {len(confirmed)}/{len(COMPANIES)} companies resolved to a real ATS.")
    print("\nCopy-pasteable dict for companies.py:")
    print("COMPANIES = {")
    by_platform: dict[str, list[str]] = {}
    for slug, source in confirmed.items():
        by_platform.setdefault(source, []).append(slug)
    for source, slugs in by_platform.items():
        print(f'    "{source}": {slugs},')
    print("}")


if __name__ == "__main__":
    asyncio.run(verify_all())