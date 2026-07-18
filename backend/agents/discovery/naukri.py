from datetime import datetime
from backend.schemas.models import Job

# NOTE: Naukri.com is protected by Akamai bot-management at the edge
# (returns "Access Denied" / errors.edgesuite.net before any page content
# loads, even with a real headless browser + stealth patching attempted).
# Since Naukri is assist-only per hard constraints anyway (no auto-submit,
# no login automation), the effort-to-value ratio here isn't worth fighting
# enterprise bot detection for. Stubbed to keep the discovery interface
# consistent across all six sources — revisit only if playwright-stealth
# or a rotating-proxy approach becomes worth the time investment.


async def fetch_naukri_jobs(keyword: str) -> list[Job]:
    return []