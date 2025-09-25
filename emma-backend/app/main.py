
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.infra.logging import setup_logging, get_logger
from app.services.orchestrator import analyze_transcript, analyze_transcript_llm_only, llm_diagnostic
from typing import Optional

setup_logging()
log = get_logger("app.main")

app = FastAPI(title="Incident AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str

@app.post("/analyze")
def analyze(
    req: AnalyzeRequest,
    # use 'pattern=' for Pydantic v2; if you're on v1, switch back to regex=
    force_source: Optional[str] = Query(default=None, pattern="^(llm|rules)$")
):
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
    try:
        info = llm_diagnostic()
        return info
    except Exception as e:
        log.exception("diag.llm.failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"ok": True}
