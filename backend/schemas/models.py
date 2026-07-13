from datetime import datetime
from typing import TypedDict,Literal
from pydantic import BaseModel, Field

class Job(BaseModel):
    job_id: str
    source: Literal["greenhouse","lever","ashby","linkedin","naukri","internshala"]
    company: str
    title: str
    location: str
    url: str
    raw_description: str
    requires_login_to_apply: bool
    discovered_at: datetime = Field(default_factory=datetime.now)

class ParsedJD(BaseModel):
    job_id: str
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    years_experience: int
    key_responsibilities: list[str]
    keywords_for_ats: list[str]
    seniority_level: Literal["intern","junior","mid","senior","lead"]
    fit_score: int = Field(ge=0, le=100)

class TailoredResume(BaseModel):
    job_id: str
    resume_json: dict
    rendered_path: str
    integrity_check_passed: bool

class TrackerRecord(BaseModel):
    id: str
    job_id: str
    company: str
    title: str
    source: str
    fit_score: str
    resume_version_path: str
    status: Literal["auto_submitted","awaiting_click","applied_manually","skipped"]
    applied_at: datetime | None = None
    notes: str = ""