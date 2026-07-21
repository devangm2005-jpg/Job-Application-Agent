from unittest.mock import AsyncMock, patch
import pytest
from google.genai.errors import ServerError, ClientError
from backend.schemas.models import Job
from backend.agents.jd_parser_agent import parse_job_description, _JDExtraction


def make_job(description: str = "We need a Python engineer with 3+ years experience.") -> Job:
    return Job(
        job_id="test_001",
        source="greenhouse",
        company="testco",
        title="Backend Engineer",
        location="Remote",
        url="https://testco.com/jobs/1",
        raw_description=description,
        requires_login_to_apply=False,
    )


def mock_response(extraction: _JDExtraction):
    """Builds a fake Gemini response object matching what response.text returns."""
    mock = AsyncMock()
    mock.text = extraction.model_dump_json()
    return mock


@pytest.mark.asyncio
async def test_parses_valid_job_description():
    fake_extraction = _JDExtraction(
        must_have_skills=["Python", "FastAPI"],
        nice_to_have_skills=["Docker"],
        years_experience=3,
        key_responsibilities=["Build APIs"],
        keywords_for_ats=["Python", "FastAPI", "REST"],
        seniority_level="mid",
    )

    with patch(
        "backend.agents.jd_parser_agent._call_gemini",
        new=AsyncMock(return_value=mock_response(fake_extraction)),
    ):
        result = await parse_job_description(make_job())

    assert result is not None
    assert result.job_id == "test_001"
    assert result.must_have_skills == ["Python", "FastAPI"]
    assert result.seniority_level == "mid"
    assert result.fit_score == 50  # placeholder, not model-generated


@pytest.mark.asyncio
async def test_empty_description_skips_api_call():
    with patch(
        "backend.agents.jd_parser_agent._call_gemini",
        new=AsyncMock(),
    ) as mock_call:
        result = await parse_job_description(make_job(description=""))

    assert result is None
    mock_call.assert_not_called()  # confirms we don't waste an API call on empty input


@pytest.mark.asyncio
async def test_client_error_returns_none_without_retry_loop():
    with patch(
        "backend.agents.jd_parser_agent._call_gemini",
        new=AsyncMock(side_effect=ClientError(400, {"message": "bad request"})),
    ):
        result = await parse_job_description(make_job())

    assert result is None


@pytest.mark.asyncio
async def test_malformed_json_response_returns_none():
    mock = AsyncMock()
    mock.text = "not valid json{{{"

    with patch(
        "backend.agents.jd_parser_agent._call_gemini",
        new=AsyncMock(return_value=mock),
    ):
        result = await parse_job_description(make_job())

    assert result is None


@pytest.mark.asyncio
async def test_fit_score_always_neutral_placeholder():
    """Guards against a future regression where fit_score accidentally
    gets model-generated instead of set as a deliberate placeholder."""
    fake_extraction = _JDExtraction(
        must_have_skills=["Go"],
        nice_to_have_skills=[],
        years_experience=5,
        key_responsibilities=["Scale services"],
        keywords_for_ats=["Go", "Kubernetes"],
        seniority_level="senior",
    )

    with patch(
        "backend.agents.jd_parser_agent._call_gemini",
        new=AsyncMock(return_value=mock_response(fake_extraction)),
    ):
        result = await parse_job_description(make_job())

    assert result.fit_score == 50