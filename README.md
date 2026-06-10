# DocAnchor — Autonomous Documentation Drift Detection

---

## Problem Statement

### Technical Docs Go Stale the Moment Code Changes — and Nobody Notices Until It Costs Hours

A modern engineering team commits dozens of times a day. Every function rename, every new parameter, every removed endpoint silently invalidates the documentation that describes it. READMEs, API references, architecture notes, and runbooks drift away from the code they describe — invisibly, until a consumer trusts them and gets burned.

No existing tool knows *which specific code change* invalidated *which specific sentence* of documentation. Doc rot is discovered by accident, weeks or months after the fact, at the worst possible moment: during onboarding, during an incident, during an integration.

**Why it matters:** Stale docs cause integration bugs, slow onboarding, repeated questions to senior engineers, and broken handoffs. Documentation is treated as a manual afterthought rather than a living artifact the system maintains — which is exactly the kind of legacy assumption an AI-first production function should overturn.

### Proposed Solution

DocAnchor links each documentation block to the code symbols it describes (functions, endpoints, config keys, schemas). On every commit it diffs the changed symbols, finds the docs that reference them, scores how far each doc has drifted, and an LLM drafts the corrected text as a suggested documentation PR. A Doc Health dashboard shows a freshness score per repo and surfaces the most stale, most-read docs first.

### Expected Impact
- Cut stale-documentation incidents by detecting drift the moment code changes — not months later
- Faster onboarding and fewer repeat questions to senior engineers
- Doc updates drafted in seconds as a reviewable PR rather than a forgotten chore
- A measurable Doc Health score that makes documentation quality visible to the team

---

## Overview

An autonomous pipeline that ingests a commit diff, extracts changed code symbols via AST parsing, maps those symbols to documentation blocks via a vector index, scores drift, drafts LLM rewrites, and delivers a prioritised Doc Health dashboard with a reviewable PR preview — all locally, with no external services required in demo mode.

---

## What Works Right Now

### ✅ Works out of the box (fully built)

| Feature | Status |
|---------|--------|
| Demo pipeline (end-to-end) | ✅ 4 pre-authored commit scenarios |
| Symbol extraction | ✅ tree-sitter AST + diff-text fallback |
| Doc block parsing | ✅ Markdown → DocBlock objects |
| Symbol-to-doc linking | ✅ TF-IDF vector index + regex matching |
| Drift scoring | ✅ 0–100 weighted algorithm |
| Mock LLM rewrites | ✅ No API key needed |
| Real LLM rewrites | ✅ OpenAI-compatible endpoint |
| Local PR preview | ✅ Unified diff generation |
| Real GitHub PR creation | ✅ Git Data API branch push + PR |
| GitHub token validation | ✅ Live scope check |
| Real GitHub commit fetching | ✅ REST API integration |
| Real GitHub repo analysis | ✅ Full pipeline on real repos |
| Real GitHub webhook | ✅ HMAC-secured push events |
| Persistent job storage | ✅ SQLite database |
| Real embeddings | ✅ sentence-transformers support |
| Slack alerts | ✅ Incoming webhook support |
| Per-author doc-debt report | ✅ GitHub API attribution |
| Executable doc examples | ✅ Python sandbox execution |
| Confidence-gated auto-merge | ✅ Low-risk auto-merge |

---

## Project Structure

```
docanchor/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/config.py
│   │   ├── models/schemas.py
│   │   ├── api/routes.py
│   │   ├── workers/analysis_worker.py
│   │   ├── services/
│   │   │   ├── symbol_extractor.py
│   │   │   ├── doc_parser.py
│   │   │   ├── drift_scorer.py
│   │   │   ├── vector_index.py
│   │   │   ├── llm_service.py
│   │   │   ├── github_fetcher.py
│   │   │   ├── github_service.py
│   │   │   ├── notifier.py
│   │   │   ├── doc_debt.py
│   │   │   ├── doc_executor.py
│   │   │   └── auto_merge.py
│   │   └── mocks/
│   │       └── mock_interfaces.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
├── sample_repo/
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10 + FastAPI |
| AST parsing | tree-sitter |
| Vector index | Qdrant (in-memory) + TF-IDF |
| LLM | OpenAI-compatible API |
| GitHub | REST API v3 via httpx |
| Frontend | React 18 + Vite + TypeScript |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Clone and configure
```bash
cp backend/.env.example backend/.env
```

### 2. Run — two terminals
```bash
bash start_backend.sh
bash start_frontend.sh
```

### 3. Try the demo pipeline
Open http://localhost:3000 and select any commit scenario.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOCKS` | `True` | Demo mode without credentials |
| `LLM_API_KEY` | — | OpenAI-compatible API key |
| `GITHUB_TOKEN` | — | GitHub PAT for real PRs |
| `WEBHOOK_SECRET` | — | HMAC secret for webhooks |
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook for alerts |

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/config` | Feature flags |
| `POST` | `/api/webhook/github` | Demo webhook |
| `POST` | `/api/webhook/push` | Real GitHub push webhook |
| `POST` | `/api/analyze/repo` | Analyze real GitHub commit |
| `POST` | `/api/github/commits` | Fetch commits |
| `POST` | `/api/github/validate` | Validate token |
| `GET` | `/api/jobs/{job_id}` | Poll job |
| `GET` | `/api/jobs` | List jobs |
| `GET` | `/api/dashboard/{job_id}` | Dashboard metrics |

---

## Pipeline — How It Works

```
Commit diff → Symbol Extraction → Doc Parsing → Symbol-to-Doc Linking → Drift Scoring → LLM Rewrite → PR Creation → Dashboard
```

---

## Demo Commit Scenarios

| # | Commit message | File | What drifts |
|---|---------------|------|-------------|
| 0 | feat: multi-currency routing | `src/payments.py` | `process_payment` docs |
| 1 | fix: hard-delete + GDPR | `src/users.py` | `deactivate_user` docs |
| 2 | refactor: drop webhook channel | `src/notifications.py` | `send_notification` docs |
| 3 | feat: payment v2 + GDPR combined | `payments.py` + `users.py` | Both doc sections |