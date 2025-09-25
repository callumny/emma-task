"""
main.py

This is the FastAPI entrypoint for the Incident AI backend. It exposes endpoints
for analyzing transcripts, running LLM diagnostics, and checking health status.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.infra.logging import setup_logging, get_logger
from app.services.orchestrator import analyze_transcript, analyze_transcript_llm_only, llm_diagnostic
from typing import Optional

setup_logging()
log = get_logger("app.main")

app = FastAPI(title="Incident AI API")

# Enable CORS for all origins (simplifies frontend integration during development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Obviously don't do this anywhere else, but this is just a coding test demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    """Schema for incoming /analyze requests containing raw transcript text."""
    text: str

@app.post("/analyze")
def analyze(
    req: AnalyzeRequest,
    # use 'pattern=' for Pydantic v2; if you're on v1, switch back to regex=
    force_source: Optional[str] = Query(default=None, pattern="^(llm|rules)$")
):
    """
    Analyze a transcript and extract an incident report.

    Args:
        req: request body with transcript text
        force_source: optional override ("llm" or "rules") to select extraction method

    Returns:
        A JSON response with incident form, evidence, draft email, and extraction source.
    """
    try:
        log.info(f"/analyze called, force_source={force_source}")
        if force_source == "llm":
            return analyze_transcript_llm_only(req.text)
        return analyze_transcript(req.text)
    except Exception as e:
        log.exception("analysis.failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/diag/llm")
def diag_llm():
    """
    Run diagnostics on the LLM integration.

    Returns:
        Information about environment setup, model availability, and test call success.
    """
    try:
        info = llm_diagnostic()
        return info
    except Exception as e:
        log.exception("diag.llm.failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """
    Lightweight health check endpoint.

    Returns:
        {"ok": True} if the API is running.
    """
    return {"ok": True}
