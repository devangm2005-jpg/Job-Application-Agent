import pytest
from pydantic import ValidationError
from backend.schemas.models import Job, ParsedJD, TailoredResume, TrackerRecord


def test_job_valid():
    job = Job(
        job_id="gh_001",
        source="greenhouse",
        company="Acme",
        title="Backend Engineer",
        location="Remote",
        url="https://acme.com/jobs/1",
        raw_description="We need a backend engineer...",
        requires_login_to_apply=False,
    )
    assert job.job_id == "gh_001"


def test_job_rejects_bad_source():
    with pytest.raises(ValidationError):
        Job(
            job_id="x_001",
            source="indeed",  # not in Literal
            company="Acme",
            title="Backend Engineer",
            location="Remote",
            url="https://acme.com/jobs/1",
            raw_description="...",
            requires_login_to_apply=False,
        )


def test_parsed_jd_fit_score_bounds():
    with pytest.raises(ValidationError):
        ParsedJD(
            job_id="gh_001",
            must_have_skills=["python"],
            nice_to_have_skills=[],
            years_experience=2,
            key_responsibilities=["build stuff"],
            keywords_for_ats=["python"],
            seniority_level="junior",
            fit_score=150,  # out of range
        )


def test_tailored_resume_valid():
    resume = TailoredResume(
        job_id="gh_001",
        resume_json={"name": "Devang"},
        rendered_path="data/tailored_resumes/gh_001.pdf",
        integrity_check_passed=True,
    )
    assert resume.integrity_check_passed


def test_tracker_record_rejects_bad_status():
    with pytest.raises(ValidationError):
        TrackerRecord(
            id="1",
            job_id="gh_001",
            company="Acme",
            title="Backend Engineer",
            source="greenhouse",
            fit_score=80,
            resume_version_path="data/tailored_resumes/gh_001.pdf",
            status="rejected",  # not in Literal
        )