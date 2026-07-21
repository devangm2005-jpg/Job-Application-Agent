import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from backend.schemas.models import Job, ParsedJD
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

PARSE_SYSTEM_INSTRUCTION = """
You are an expert ATS (Applicant Tracking System) job description parser. 
Analyze the job title and description text to extract structured insights.
Be objective and strict. Do not invent years of experience if not explicitly mentioned.
"""


class _JDExtraction(BaseModel):
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    years_experience: int
    key_responsibilities: list[str]
    keywords_for_ats: list[str]
    seniority_level: str



async def parse_job_description(job: Job) -> Optional[ParsedJD]:
    """Asynchronously parses raw job postings into strict, structured Pydantic schemas using Gemini."""

    cleaned_description = (job.raw_description or "").strip()[:6000]

    if not cleaned_description:
        return None
    
    prompt = f"""
Analyze this posting data to build structured matching records.

Job Title: {job.title}
Company:{job.company}

Job Description Text:
{cleaned_description}
"""
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=PARSE_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_JDExtraction,
                temperature=0.1
            ),
        )

        if not response.text:
            return None        

        extraction = _JDExtraction.model_validate_json(response.text)

        # FIX: Sanitize the seniority string before passing it into ParsedJD
        raw_seniority = extraction.seniority_level.lower().strip()
        
        # Enforce safe routing choices back to allowed Literal constraints
        if "intern" in raw_seniority:
            clean_seniority = "intern"
        elif "junior" in raw_seniority:
            clean_seniority = "junior"
        elif "senior" in raw_seniority:
            clean_seniority = "senior"
        elif "lead" in raw_seniority or "manager" in raw_seniority or "principal" in raw_seniority:
            clean_seniority = "lead"
        else:
            clean_seniority = "mid" # Defend against unpredictable outputs with a standard default

        # Dump extraction data fields safely
        extraction_dict = extraction.model_dump()
        extraction_dict["seniority_level"] = clean_seniority # Inject the cleaned version


        return ParsedJD(
            job_id=job.job_id,
            fit_score=50,  # neutral placeholder — real scoring needs resume context, added in Phase 3
            **extraction_dict,
        )
    
    except Exception as e:
        print(f"❌ [AI Parser] Pipeline processing failed for job token '{job.job_id}': {e}")
        return None
    

# Verification execution test runner
if __name__ == "__main__":
    async def test_parser():
        print("⏳ Initializing mock AI transaction execution...")
        mock_job = Job(
            job_id="gh_demo_101",
            source="greenhouse",
            company="stripe",
            title="Senior Python Backend Engineer (FastAPI)",
            location="Bangalore, India",
            url="https://stripe.com",
            raw_description="We are looking for a Senior Engineer with 5+ years of experience in Python and FastAPI. Docker and AWS are a plus.",
            requires_login_to_apply=False
        )
        
        result = await parse_job_description(mock_job)
        if result:
            print("\n🎉 [AI Parser Success] Structured extraction data received:")
            print(f"🥇 Seniority Match: {result.seniority_level.upper()}")
            print(f"💼 Required Experience: {result.years_experience} Years")
            print(f"🔥 Core Skills: {result.must_have_skills}")
            print(f"✨ ATS Keywords: {result.keywords_for_ats}\n")

    # Run the isolation worker loop safely
    asyncio.run(test_parser())
