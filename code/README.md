# SupportBrain — Multi-Domain Support Triage Agent

## Setup (3 steps)

1. Clone this repo
2. Copy `code/.env.example` to `code/.env` and add your API keys:
   - `GROQ_API_KEY` — get free at [console.groq.com](https://console.groq.com) (email only, no card)
   - `GEMINI_API_KEY` — get free at [aistudio.google.com](https://aistudio.google.com) (Google login)
3. `pip install -r code/requirements.txt`

## Run

```bash
python code/main.py
```

## Output

| File | Description |
|---|---|
| `support_issues/output.csv` | All 29 tickets with 5 output columns |
| `~/hackerrank_orchestrate/log.txt` | Full decision transcript |
| `code/audit.db` | SQLite audit log (queryable) |

### Useful audit queries

```sql
SELECT status, COUNT(*) FROM runs GROUP BY status;
SELECT * FROM runs WHERE status='Escalated';
SELECT provider_used, COUNT(*) FROM runs GROUP BY provider_used;
SELECT confidence, COUNT(*) FROM runs GROUP BY confidence;
```

## Architecture

| Module | Role |
|---|---|
| `main.py` | CLI entry point, Rich terminal UI |
| `agent.py` | Per-ticket pipeline (classify → risk → retrieve → generate) |
| `classifier.py` | Company detection, risk scoring, request type |
| `retriever.py` | TF-IDF RAG over local corpus (`data/` folder) |
| `llm_router.py` | Groq (primary) + Gemini (fallback), both free |
| `prompts.py` | System prompt + user prompt templates |
| `logger.py` | log.txt writer + SQLite audit database |

## Validation

```bash
python code/validate.py
```

Checks that `output.csv` has all required columns, valid status/type values, and no empty responses.

## Optional flags

```
--input PATH    Override input CSV (default: support_issues/support_issues.csv)
--output PATH   Override output CSV (default: support_issues/output.csv)
--verbose       Print per-ticket details to terminal
```

## Cost

**$0.00** — Both APIs are free tier, no credit card required.
