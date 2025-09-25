
# Quick test commands

## 0) Start the backend with logging
```bash
cd incident-ai
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export LOG_LEVEL=INFO
export OPENAI_API_KEY=sk-...            # set your actual key
export OPENAI_MODEL=gpt-4o-mini         # optional
uvicorn app.main:app --reload --port 8000
```

## 1) Health check
```bash
curl -s http://127.0.0.1:8000/health
```

## 2) LLM diagnostics (confirms SDK import, key visibility, and a tiny test call)
```bash
curl -s http://127.0.0.1:8000/diag/llm | jq .
```

You should see:
- `env_key_present: true`
- `sdk_import_ok: true`
- `test_call_ok: true` (if the key is valid)

## 3) Analyze (normal, with fallback to rules)
```bash
curl -s http://127.0.0.1:8000/analyze -H "Content-Type: application/json" -d @sample.json | jq .
```

## 4) Force LLM-only path (for debugging)
```bash
curl -s "http://127.0.0.1:8000/analyze?force_source=llm" -H "Content-Type: application/json" -d @sample.json | jq .
```

If you get `"extraction_source": "llm_empty"`, the LLM returned nothing or failed to parse. Check `/diag/llm` and server logs.

## sample.json example
```json
{
  "text": "Hi, it's Greg Jones. I've fallen again. I'm in the living room. This is the third time this week."
}
```
