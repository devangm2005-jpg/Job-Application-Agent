import json
import asyncio
from pathlib import Path
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.schemas.models import Job, ParsedJD, TailoredResume
from dotenv import load_dotenv

load_dotenv()

# Use native AsyncClient for proper connection pooling
client = genai.Client()
MASTER_RESUME_PATH = Path("backend/data/master_resume.json")

# ---- Base Pipeline Schemas ----
class _TailoredBullet(BaseModel):
    source_id: str
    rephrased_text: str

class _TailoringOutput(BaseModel):
    professional_summary: str
    selected_experience_bullets: list[_TailoredBullet]
    selected_project_bullets: list[_TailoredBullet]
    selected_skills: list[str]

# ---- Verification Schemas ----
class _VerificationResult(BaseModel):
    source_id: str
    traceable: bool
    reason: str

class _VerificationOutput(BaseModel):
    results: list[_VerificationResult]
    overall_passed: bool

# ---- Fixed Correction Schema (Resolves Validation Crashes) ----
class _CorrectionOutput(BaseModel):
    corrected_bullets: list[_TailoredBullet]

# ---- Prompt Configurations ----
TAILOR_SYSTEM_INSTRUCTION = """
You are a resume tailoring assistant. You will be given a candidate's master
resume content (as id + text pairs) and a target job's requirements.

STRICT RULES:
- You may only REORDER and REPHRASE existing bullets. Never invent a skill,
  employer, project, metric, or accomplishment not present in the source.
- Every bullet you output MUST reference a real source_id from the input.
- Rephrasing means: tighten wording, emphasize relevant parts, match
  terminology from the job description — not adding new claims, outcomes,
  or interpretations not explicitly stated in the source.
- selected_skills must be a subset of the candidate's master skill list.
"""

VERIFY_SYSTEM_INSTRUCTION = """
You are a strict fact-checker. You will see pairs of (original resume bullet,
rephrased version). For each pair, determine if the rephrased version
introduces ANY claim, outcome, metric, or interpretation not present in the
original. Be strict: paraphrasing/tightening wording is fine, adding new
information or implied results is not.
Set overall_passed to true only if ALL bullets are traceable.
"""

FIX_SYSTEM_INSTRUCTION = """
You are correcting resume bullets that failed a fact-check. For each bullet,
you're given: the original source text, your previous rephrase, and the
specific reason it was rejected. Rewrite ONLY to remove the unsupported
claim identified in the reason — stay as close to the original wording and
scope as possible. Do not add anything new. If in doubt, stay closer to the
original rather than further from it.
"""

# ---- Data Ingestion Helpers ----
def _load_master_resume_sync() -> dict:
    return json.loads(MASTER_RESUME_PATH.read_text())

def _build_id_lookup(master: dict) -> dict[str, str]:
    lookup = {}
    for exp in master.get("experience", []):
        for b in exp.get("bullets", []):
            lookup[b["id"]] = b["text"]
    for proj in master.get("projects", []):
        for b in proj.get("bullets", []):
            lookup[b["id"]] = b["text"]
    return lookup

# ---- Core API Engine ----
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
async def _call_gemini(system_instruction: str, prompt: str, schema: type[BaseModel]):
    return await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        ),
    )

# ---- Pipeline Async Operations ----
async def _verify(bullets: list[_TailoredBullet], id_lookup: dict[str, str]) -> _VerificationOutput:
    pairs_text = "\n\n".join(
        f"[{b.source_id}]\nOriginal: {id_lookup[b.source_id]}\nRephrased: {b.rephrased_text}"
        for b in bullets
    )
    prompt = f"Verify these rephrased bullets against their originals:\n\n{pairs_text}"
    response = await _call_gemini(VERIFY_SYSTEM_INSTRUCTION, prompt, _VerificationOutput)
    return _VerificationOutput.model_validate_json(response.text)

async def _fix_failed_bullets(
    failed: list[tuple[_TailoredBullet, str]], id_lookup: dict[str, str]
) -> dict[str, str]:
    items_text = "\n\n".join(
        f"[{b.source_id}]\nOriginal: {id_lookup[b.source_id]}\n"
        f"Previous rephrase: {b.rephrased_text}\nRejection reason: {reason}"
        for b, reason in failed
    )
    prompt = f"Fix these rejected bullets:\n\n{items_text}"
    # Fixed to utilize target schema _CorrectionOutput to eliminate schema extraction errors
    response = await _call_gemini(FIX_SYSTEM_INSTRUCTION, prompt, _CorrectionOutput)
    fixed = _CorrectionOutput.model_validate_json(response.text)
    return {b.source_id: b.rephrased_text for b in fixed.corrected_bullets}

# ---- Primary Module Interface Entry Point ----
async def tailor_resume(job: Job, parsed_jd: ParsedJD) -> TailoredResume | None:
    # Safely offload synchronous file reads from the execution thread pool
    loop = asyncio.get_running_loop()
    master = await loop.run_in_executor(None, _load_master_resume_sync)
    id_lookup = _build_id_lookup(master)

    source_bullets = "\n".join(f"[{bid}] {text}" for bid, text in id_lookup.items())
    tailor_prompt = f"""
    Job Title: {job.title}
    Must-have skills: {parsed_jd.must_have_skills}
    Key responsibilities: {parsed_jd.key_responsibilities}
    ATS keywords: {parsed_jd.keywords_for_ats}

    Candidate's master skills: {master.get("skills", {})}

    Candidate's resume bullets (id: text):
    {source_bullets}
    """
    try:
        response = await _call_gemini(TAILOR_SYSTEM_INSTRUCTION, tailor_prompt, _TailoringOutput)
        tailored = _TailoringOutput.model_validate_json(response.text)
    except Exception as e:
        print(f"❌ [tailoring] tailor step failed for '{job.job_id}': {e}")
        return None

    all_bullets = tailored.selected_experience_bullets + tailored.selected_project_bullets

    unknown_ids = [b.source_id for b in all_bullets if b.source_id not in id_lookup]
    if unknown_ids:
        print(f"❌ [tailoring] hallucinated source_ids for '{job.job_id}': {unknown_ids}")
        return None

    if not all_bullets:
        print(f"⚠️ [tailoring] no bullets selected for '{job.job_id}'")
        integrity_passed = False
    else:
        try:
            verification = await _verify(all_bullets, id_lookup)
        except Exception as e:
            print(f"❌ [tailoring] verification failed for '{job.job_id}': {e}")
            return None

        fail_map = {r.source_id: r.reason for r in verification.results if not r.traceable}

        if fail_map:
            print(f"⚠️ [tailoring] {len(fail_map)} bullet(s) failed integrity, attempting fix: {list(fail_map)}")
            failed_bullets = [(b, fail_map[b.source_id]) for b in all_bullets if b.source_id in fail_map]

            try:
                corrections = await _fix_failed_bullets(failed_bullets, id_lookup)
                for b in all_bullets:
                    if b.source_id in corrections:
                        b.rephrased_text = corrections[b.source_id]

                # Re-verify fixed components
                fixed_bullets = [b for b in all_bullets if b.source_id in fail_map]
                reverify = await _verify(fixed_bullets, id_lookup)
                
                # Treat as failing if it's not explicitly marked traceable in the verification loop
                passed_ids = {r.source_id for r in reverify.results if r.traceable}
                still_failing = set(fail_map.keys()) - passed_ids

                # Absolute hard fallback to prevent evaluation processing escape vectors
                for b in all_bullets:
                    if b.source_id in still_failing:
                        print(f"⚠️ [tailoring] '{b.source_id}' still not traceable after fix — using original text verbatim")
                        b.rephrased_text = id_lookup[b.source_id]

                integrity_passed = True  
            except Exception as e:
                print(f"❌ [tailoring] fix pass failed for '{job.job_id}': {e}")
                return None
        else:
            integrity_passed = True

    resume_json = {
        "professional_summary": tailored.professional_summary,
        "experience_bullets": [b.model_dump() for b in tailored.selected_experience_bullets],
        "project_bullets": [b.model_dump() for b in tailored.selected_project_bullets],
        "selected_skills": tailored.selected_skills,
    }

    return TailoredResume(
        job_id=job.job_id,
        resume_json=resume_json,
        rendered_path="",
        integrity_check_passed=integrity_passed,
    )

if __name__ == "__main__":
    import asyncio
    # Mock data definitions matching your backend schemas
    from backend.schemas.models import Job, ParsedJD

    async def main():
        print("🚀 Starting manual test run for Tailoring Agent...")
        
        # 1. Create a dummy job matching your strict Job class fields
        mock_job = Job(
            job_id="test_job_001",
            title="Senior Python Backend Engineer",
            company="Figma",
            location="Remote",
            url="https://example.com",
            source="lever",  
            raw_description="Looking for an engineer to build async Python applications.",
            requires_login_to_apply=False  
        )

        # 2. Create mock parsed job description attributes with matching lowercase constraints
        mock_parsed_jd = ParsedJD(
            job_id="test_job_001",
            must_have_skills=["Python", "Asyncio", "Pydantic"],
            nice_to_have_skills=["Docker", "AWS"],
            key_responsibilities=["Optimize API speeds", "Handle background workers"],
            years_experience=5,
            seniority_level="senior",  # Lowercase to pass Pydantic Literal constraint
            keywords_for_ats=["Concurrent systems", "Data Validation", "FastAPI"],
            fit_score=85
        )

        # 3. Execute the tailoring pipeline
        result = await tailor_resume(mock_job, mock_parsed_jd)

        print("\n--- Tailored Experience Bullets ---")
        for b in result.resume_json.get("experience_bullets", []):
            print(f"- [{b['source_id']}] {b['rephrased_text']}")


        # 4. Inspect the self-healing output pipeline results
        if result:
            print("\n✅ Tailoring Pipeline Finished Successfully!")
            print(f"Integrity Check Passed: {result.integrity_check_passed}")
            print("\n--- Generated Summary ---")
            print(result.resume_json.get("professional_summary"))
            print("\n--- Tailored Experience Bullets ---")
            for b in result.resume_json.get("experience_bullets", []):
                print(f"- [{b['source_id']}] {b['rephrased_text']}")
        else:
            print("\n❌ Tailoring Pipeline Failed to return a result.")

    # Execute the event loop explicitly
    asyncio.run(main())
