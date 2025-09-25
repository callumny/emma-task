# Emma Backend

## What’s inside (structure)

- `app/main.py`  
  FastAPI entrypoint (routes: `/analyze`, `/diag/llm`, `/health`)  
  CORS middleware for calling from your frontend  

- `app/services/orchestrator.py`  
  Orchestrates extraction: tries **LLM** (if key present), always has **rules** fallback  
  Merges results, builds the **incident form**, assembles the **draft email**  

- `app/llm/extract.py`  
  Builds the LLM prompt, calls OpenAI, returns normalized **facts** + **evidence**  
  Clamps outputs to allowed types/assessments (prevents hallucinated values)  

- `app/rules/extract.py`  
  Pure regex rules: detects **incident_type**, **location**, **name**, **emergency services**  
  Adds **evidence** with text spans; calls policy logic for risk assessments  

- `app/rules/assessments.py`  
  Policy-aligned checks for **risk assessments** (e.g., recurring falls → moving & handling review)  

- `app/config/incident_config.py`  
  Loads `config/incident_patterns.yml` (incident regex patterns + locations)  

- `app/infra/logging.py`  
  Central logging setup (`LOG_LEVEL`), `get_logger()`  

- `config/incident_patterns.yml`  
  YAML of **incident patterns** and **locations** (keys under `patterns:` become allowed incident types)  

- `config/prompts/extract_incident_prompt.txt`  
  The **LLM prompt** template (tokens: `[[ALLOWED_TYPES]]`, `[[ALLOWED_ASSESSMENTS]]`, `[[TRANSCRIPT]]`)  

- `config/allowed_risk_assessments.yml`  
  Allowed **risk assessment** names used to validate model output  

- `requirements.txt`  
  Python dependencies  

---

## How it works (pipeline)

- Receive transcript (POST `/analyze`)  
- If `OPENAI_API_KEY` is set:  
  - Build prompt from config → call model → parse/normalize **facts** + **evidence**  
- Always run **rules** extractor:  
  - Regex for incident type, location, name; simple toggles (e.g., ambulance)  
  - Policy rules to infer **risk assessment** (e.g., recurring falls)  
- Merge:  
  - Prefer LLM values where present; backfill with rules if missing  
  - Normalize & de-duplicate **evidence** (field + quote)  
- Output:  
  - Structured **incident form**  
  - Human-readable **draft email** (SUMMARY + DETAILS)  
  - Source used: `llm` or `rules`  

---

## Environment variables

- `OPENAI_API_KEY` – enables LLM extraction path  
- `OPENAI_MODEL` – defaults to `gpt-4o-mini`  
- `LOG_LEVEL` – `DEBUG | INFO | WARNING | ERROR` (default `INFO`)  
- `FRONTEND_ORIGIN` – lock CORS to a specific origin (if you restrict it)  
- `INCIDENT_CONFIG` – override path to `incident_patterns.yml`  
- `LLM_PROMPT_PATH` – override path to `extract_incident_prompt.txt`  
- `ALLOWED_RISK_ASSESSMENTS_PATH` – override path to allowed RAs YAML  

---

## API endpoints

- `POST /analyze`  
  **Body:** `{ "text": "<transcript>" }`  
  **Query (optional):** `?force_source=llm|rules`  
  **Returns:** `{ extraction_source, incident_form, evidence, draft_email }`  

- `GET /diag/llm`  
  Quick LLM diagnostics (env/model/test call)  

- `GET /health`  
  Liveness: `{ "ok": true }`  

---

## Get started

### 1. Python & repo
- Use **Python 3.11+**  
- `cd emma-backend`

### 2. Create a virtualenv & install
```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
