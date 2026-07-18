from datetime import datetime
from backend.schemas.models import Job

# NOTE: LinkedIn's public guest API (jobs-guest/jobs/api/seeMoreJobPostings)
# is rate-limited/blocked aggressively in practice. Since LinkedIn is
# assist-only anyway (no auto-submit, no login automation per hard
# constraints), stubbed to match naukri.py rather than fighting anti-bot
# measures for a source that was never going to be automatable end-to-end.
# Revisit only with a proxy/stealth strategy if discovery volume is worth it.


async def fetch_linkedin_jobs(keyword: str, location: str = "India") -> list[Job]:
    return []