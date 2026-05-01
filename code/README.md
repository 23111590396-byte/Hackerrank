# SupportBrain — Multi-Domain Triage Agent

> **HackerRank Orchestrate · May 2026**  
> Powered by Groq (primary) + Google Gemini (fallback) · **Total cost: $0.00**

---

## What it does

SupportBrain reads a CSV of customer support tickets for three companies
(**HackerRank**, **Claude/Anthropic**, **Visa**), determines the right action
for each ticket using RAG + LLM, and writes a structured `output.csv`.

Each ticket gets:
| Field | Description |
|---|---|
| `response` | User-facing reply or escalation message |
| `product_area` | Support category (assessment, billing, fraud, …) |
| `status` | `Replied` or `Escalated` |
| `request_type` | `bug` / `product_issue` / `feature_request` / `invalid` |
| `justification` | 1–2 sentence reasoning |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r code/requirements.txt
```

### 2. Configure API keys

```bash
cp code/.env.example code/.env
# Edit code/.env and add your keys:
# GROQ_API_KEY    → free at console.groq.com (email only)
# GEMINI_API_KEY  → free at aistudio.google.com (Google login)
```

### 3. Run

```bash
python code/main.py
```

Output is written to `support_issues/output.csv`.

### Optional flags

```
--input PATH    Override input CSV path (default: support_issues/support_issues.csv)
--output PATH   Override output CSV path (default: support_issues/output.csv)
--verbose       Print per-ticket details to terminal
```

---

## Project Structure

```
code/
├── main.py          ← CLI entry, Rich UI, CSV I/O
├── agent.py         ← Per-ticket pipeline
├── retriever.py     ← Corpus loader + TF-IDF search
├── classifier.py    ← Company detect, risk check, type classify
├── llm_router.py    ← Groq → Gemini fallback routing
├── prompts.py       ← System prompt + user prompt templates
├── logger.py        ← log.txt writer + SQLite audit
├── .env.example     ← API key template
└── requirements.txt

support_issues/
├── support_issues.csv   ← Input tickets
└── output.csv           ← Generated output (after running)

data/
├── hackerrank/    ← HackerRank support corpus
├── claude/        ← Claude/Anthropic support corpus
└── visa/          ← Visa support corpus
```

---

## Architecture

```
support_issues.csv
        │
        ▼
    main.py  ──────────────────────────────────────────────
        │                                                  │
        ▼                                                  │
    agent.py  ← core pipeline                             │
     1. classify()   → company + request_type             │
     2. risk_check() → escalate? yes/no                   │
     3. retrieve()   → top-3 corpus chunks (TF-IDF)       │
     4. generate()   → LLM call (Groq → Gemini)           │
     5. format()     → output row                         │
     6. audit()      → SQLite + log.txt                   │
        │
   ┌────┴────────────────┬──────────────┐
retriever.py       classifier.py    llm_router.py
TF-IDF RAG         keywords+rules   Groq → Gemini
        │
    data/
  hackerrank/
  claude/
  visa/
```

---

## Logs and Audit

| File | Location | Purpose |
|---|---|---|
| `log.txt` | `~/hackerrank_orchestrate/log.txt` | Human-readable decision log |
| `audit.db` | `code/audit.db` | SQLite, all 29 rows queryable |

### Useful audit queries

```sql
-- Status summary
SELECT status, COUNT(*) FROM runs GROUP BY status;

-- All escalated tickets
SELECT ticket_id, company, justification FROM runs WHERE status='Escalated';

-- Provider usage
SELECT provider_used, COUNT(*) FROM runs GROUP BY provider_used;
```

---

## Free API providers

| Provider | Model | Free limit | Speed |
|---|---|---|---|
| **Groq** (primary) | llama-3.3-70b-versatile | 6K TPM, 30 RPM | 315 tok/s ⚡ |
| **Google AI Studio** (fallback) | gemini-2.0-flash | 1,500 req/day | Fast |

Sign up:
- Groq → [console.groq.com](https://console.groq.com) — email only
- Gemini → [aistudio.google.com](https://aistudio.google.com) — Google login
