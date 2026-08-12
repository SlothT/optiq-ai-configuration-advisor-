# Optiq — Product Requirements Document (v1)

**Document Name:** Optiq_PRD_v1.md
**Status:** Approved for Build (MVP Scope Locked)
**Owner:** Toshi Srivastava
**Last Updated:** 2026-07-24

---

## 1. Executive Summary

Optiq is an AI Configuration Advisor — a platform that helps engineers building LLM applications answer two expensive, repeatedly-asked questions: *"Is my prompt good?"* and *"Which model/configuration should I use?"*

Rather than acting as a passive evaluation dashboard, Optiq actively analyzes prompts, benchmarks models against user-defined constraints (cost, latency, accuracy), and recommends optimal **model-level** configurations (model, temperature, prompt version). All experiments are logged and compared via MLflow, turning ad-hoc trial-and-error into a repeatable, data-driven decision process.

The MVP will ship in 4 weeks with five core features: Prompt Analyzer, Experiment Runner, Automatic Evaluation (Ragas), Model Recommendation Engine, and an MLflow Dashboard. RAG-aware recommendations (embedding, chunking, retrieval) are deferred to v2.

---

## 1.1 MVP Scope Lock (Approved 2026-07-24)

Decisions confirmed before build:

| Area | MVP Decision | Deferred |
|---|---|---|
| **Recommendations** | Model-only: model + temperature + prompt version | Full RAG stack (embedding, chunk size, top-K, retriever) |
| **Auth** | Lightweight email/password + JWT; projects per user | OAuth, teams, RBAC |
| **Model providers** | Config-driven adapter layer; user enables providers via settings | Platform-managed API keys |
| **API keys** | BYOK — users supply keys for paid providers; keys encrypted at rest, never sent to frontend | Platform billing / free tier |
| **Open-source models** | Ollama adapter (local or remote Ollama URL); config-file model registry | vLLM, hosted open-weight endpoints |
| **Auto mode** | User selects "Auto" — router picks best available model from their configured providers based on constraints (cost, latency, quality preset) | Intelligent cross-provider routing without user keys |
| **Experiments** | Single-shot: prompt + optional test inputs → model → output | RAG pipelines (embed → retrieve → generate) |
| **Evaluation** | Ragas (primary) + LLM-as-judge when no ground truth | DeepEval, context precision/recall |
| **Datasets** | Inline JSON/CSV upload per experiment; optional reference answers | Persistent dataset library, document/RAG datasets |
| **Database** | Lean Postgres: users, projects, prompts, provider keys, experiment metadata | Heavy dataset storage, chat history |
| **Experiment history** | MLflow as system of record for metrics, params, artifacts | Duplicating full metrics in Postgres |
| **Prompt analysis judge** | User selects which configured model runs the analysis | Fixed platform judge model |
| **Dev/prod** | All runs hit live APIs using user's keys (or Ollama); no mock/fixture mode | Cached/mock responses |

**Cost philosophy (solo developer):** Minimize infra and storage. Postgres holds app entities only; MLflow holds experiment data; datasets are ephemeral uploads per run, not a managed library.

**Auto mode (MVP behavior):** When the user selects "Auto" instead of a specific model, the recommendation engine ranks only models the user has configured (valid API key or reachable Ollama endpoint), applies their constraints, and routes the experiment/analysis call to the top-ranked candidate. Auto is constraint-aware routing across *their* providers, not a hidden platform model.

---

## 2. Problem Statement

Every engineer building an LLM application must make decisions with no reliable tooling to support them:

- Is my prompt well-written?
- Which model should I choose (GPT-5, Claude Opus, Claude Sonnet, Gemini, local model)?
- Can I get similar quality with a cheaper model?
- Am I wasting tokens?
- Will my prompt hallucinate?
- Should I use RAG at all, and is my context too large?

Today these decisions are made through intuition and manual trial-and-error, costing teams thousands of dollars and many engineering hours per project. There is no systematic, constraint-aware tool that evaluates these trade-offs and recommends a configuration.

---

## 3. Vision

Optiq becomes the default pre-deployment checkpoint for LLM application teams — the tool engineers run before shipping a prompt or model choice to production, the same way a linter or CI pipeline is run before merging code.

Long-term, Optiq evolves from a recommendation tool into a continuous configuration-optimization engine that tracks how prompt/model/RAG configurations perform over time and proactively flags regressions or better alternatives as new models are released.

---

## 4. Target Users

- **AI/ML Engineers** building LLM-powered features (chatbots, RAG systems, agents, summarizers).
- **Backend/Full-stack Engineers** who use LLMs but are not ML specialists and need guardrails.
- **Startup Founders/CTOs** who need to control LLM cost and latency budgets while maintaining quality.
- **AI Platform/Infra Teams** at mid-to-large companies standardizing prompt and model choices across teams.
- **Consultants/Agencies** building LLM solutions for multiple clients with varying constraints.

---

## 5. User Personas

### Persona 1 — Aditi, AI Engineer at a Series-A Startup
- Building a customer support RAG bot.
- Needs to hit sub-2-second latency and stay within a tight token budget.
- Currently manually swaps models and eyeballs outputs — no systematic comparison.
- Goal: "Tell me the best config for my constraints, don't make me guess."

### Persona 2 — Rohan, Backend Engineer (Non-ML Background)
- Was asked to "add AI" to an existing product feature.
- Doesn't know prompt engineering best practices.
- Goal: "Review my prompt and tell me what's wrong with it in plain language."

### Persona 3 — Meera, Head of AI Platform at a Mid-Size Company
- Owns LLM spend across 5 product teams.
- Needs auditable, comparable experiment logs to justify model choices to leadership.
- Goal: "Give me a dashboard where I can see why we picked Model X over Model Y for each use case."

---

## 6. User Stories

**Prompt Analysis**
- As an engineer, I want to paste or upload a prompt so that I can get a quality score with strengths/weaknesses.
- As an engineer, I want token usage and cost estimates for my prompt so I can budget accurately.
- As an engineer, I want concrete suggested rewrites (not just criticism) so I can act immediately.

**Model Comparison**
- As an engineer, I want to compare multiple models on the same task/dataset so I can see accuracy, latency, and cost side by side.
- As an engineer, I want a single recommended model with a stated reason so I don't have to interpret raw numbers myself.

**Constraint-Based Recommendation**
- As an engineer, I want to specify max cost, max latency, min accuracy, and context size so the platform filters out non-viable configurations.
- As an engineer, I want an explanation of *why* a configuration was excluded (e.g., "Claude Opus exceeds your cost budget") so I trust the recommendation.

**Full Configuration Recommendation** *(deferred to v2)*
- As an engineer, I want to describe my use case and receive a full RAG stack recommendation (embedding, chunk size, top-K). *Not in MVP.*

**Provider & Key Management**
- As an engineer, I want to add my own API keys for OpenAI/Anthropic/Gemini so the platform can run experiments on my behalf without platform billing.
- As an engineer, I want to connect Ollama (local or remote) so I can benchmark open-source models at zero API cost.
- As an engineer, I want an "Auto" option that picks the best model from my configured providers based on my constraints.

**Experiment Tracking**
- As a platform owner, I want every run logged to MLflow with full metadata so I can audit and compare experiments over time.
- As a team, I want to see historical trends so we know when a new model release changes the optimal configuration.

---

## 7. Functional Requirements

### FR1 — Prompt Analyzer
- FR1.1: Accept prompt via text input or file upload (Markdown, CSV, JSON). PDF and website URL deferred to v2.
- FR1.2: Return a Prompt Quality Score (0–100).
- FR1.3: Return categorized strengths and weaknesses (clarity, format, edge cases, failure behavior, hallucination guardrails, few-shot presence).
- FR1.4: Return estimated token usage and estimated cost per request (based on user's configured provider pricing).
- FR1.5: Return a list of concrete suggested improvements.
- FR1.6: Support re-analysis of an edited/improved prompt version for before/after comparison.
- FR1.7: User selects which configured model acts as the LLM-as-judge for analysis (must have valid key or Ollama endpoint).

### FR2 — Experiment Runner
- FR2.1: Allow user to select 2+ models (or "Auto") to compare on the same prompt/test inputs.
- FR2.2: Allow user to compare 2+ prompt versions on the same model.
- FR2.3: Execute test runs against live model APIs using the user's BYOK credentials or Ollama endpoint.
- FR2.4: Display results in a comparison table (quality score, latency, cost, token usage).
- FR2.5: Support two dataset modes (see Section 12.1): **with reference answers** or **prompt-only** (no ground truth).

### FR3 — Automatic Evaluation
- FR3.1: Compute evaluation metrics using **Ragas** (answer relevancy; faithfulness when optional per-row `context` is provided). DeepEval deferred to v2.
- FR3.2: When reference answers exist: compute accuracy via semantic similarity (embedding-based) or exact match (structured tasks).
- FR3.3: When no reference answers: use LLM-as-judge (user-selected model) + Ragas answer relevancy as quality proxy.
- FR3.4: Compute cost per request based on provider pricing tables (config-driven).
- FR3.5: Compute latency (p50/p95) per run.
- FR3.6: Compute token usage (input/output/total).

### FR4 — Recommendation Engine (Model-Only)
- FR4.1: Accept user-defined goals (cheapest, fastest, highest quality, or custom weighted priorities).
- FR4.2: Accept hard constraints (max cost, max latency, min quality score, structured output requirement).
- FR4.3: Filter out configurations violating constraints and explain why each was excluded.
- FR4.4: Rank remaining viable configurations using the Overall Score formula (Section 16). Candidates = model × temperature × prompt version from experiment results.
- FR4.5: Return a single top recommendation with a human-readable justification.
- FR4.6: Support "Auto" mode — rank across user's configured providers and select the best viable model.
- ~~FR4.7: Full RAG stack recommendation~~ → **Deferred to v2.**

### FR5 — MLflow Dashboard
- FR5.1: Log every experiment run with full metadata (see Section 14).
- FR5.2: Provide a UI to browse, filter, and compare past experiments (query MLflow API; link to MLflow native UI for deep inspection).
- FR5.3: Support visual comparison (charts) of metrics across runs.
- FR5.4: Support tagging/labeling experiments by use case or project.

### FR6 — Authentication & Project Management
- FR6.1: Lightweight auth: email/password + JWT sessions. OAuth deferred.
- FR6.2: Users can create and switch between projects to organize experiments.
- FR6.3: Users can store encrypted provider API keys and Ollama base URL per project.
- FR6.4: Model registry loaded from config file — new models/providers added via YAML without core code changes.

### FR7 — Model Provider Layer *(new)*
- FR7.1: Unified adapter interface: `generate()`, `estimate_cost()`, `get_pricing()`, `health_check()`.
- FR7.2: MVP adapters: OpenAI, Anthropic, Google Gemini, Ollama (open-source).
- FR7.3: Providers and model IDs defined in `config/models.yaml`; enabled per user based on stored keys.
- FR7.4: "Auto" selection delegates to Recommendation Engine to pick best configured model for the task.

---

## 8. Non-Functional Requirements

- **NFR1 — Performance:** Prompt analysis response returned in <5s (excluding live model test calls). Recommendation engine computation <2s for experiment data already in MLflow.
- **NFR2 — Scalability:** Backend must support concurrent experiment runs without blocking the UI (async job queue).
- **NFR3 — Extensibility:** New models/providers must be addable via config (pricing table + API adapter) without core code changes.
- **NFR4 — Reliability:** Failed model API calls must be retried with backoff and surfaced clearly in the UI, not silently dropped.
- **NFR5 — Cost Safety:** Users must see an estimated cost *before* running a multi-model experiment and confirm before execution.
- **NFR6 — Auditability:** Every recommendation must be traceable to the underlying experiment/evaluation data that produced it.
- **NFR7 — Security:** API keys for third-party model providers stored encrypted at rest; never exposed to frontend.
- **NFR8 — Portability:** Core evaluation logic should run identically locally and in production (same MLflow tracking backend interface).

---

## 9. System Architecture (HLD)

```
                        ┌─────────────────────┐
                        │      Frontend        │
                        │  (React / Next.js)   │
                        └──────────┬───────────┘
                                   │ REST/WS
                        ┌──────────▼───────────┐
                        │     API Gateway       │
                        │   (FastAPI Backend)   │
                        └──────────┬───────────┘
             ┌─────────────────────┼─────────────────────────┐
             │                     │                         │
   ┌─────────▼─────────┐ ┌────────▼─────────┐     ┌──────────▼─────────┐
   │  Prompt Analyzer   │ │ Experiment Runner │     │ Recommendation      │
   │  Service           │ │ Service (async     │     │ Engine Service      │
   │                    │ │ job queue)         │     │                     │
   └─────────┬─────────┘ └────────┬─────────┘     └──────────┬─────────┘
             │                     │                          │
             │            ┌────────▼─────────┐                │
             │            │ Model Adapter Layer│               │
             │            │ (OpenAI, Anthropic,│               │
             │            │  Gemini, local)     │               │
             │            └────────┬─────────┘                │
             │                     │                          │
             │            ┌────────▼─────────┐                │
             └───────────►│ Evaluation Engine │◄───────────────┘
                          │ (Ragas/DeepEval)   │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │   MLflow Tracking  │
                          │       Server        │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │   PostgreSQL DB     │
                          │ (users, projects,   │
                          │  prompts, results)  │
                          └─────────────────────┘
```

**Key architectural decisions:**
- Model calls and evaluations run as async background jobs (RQ + Redis) to avoid blocking API responses.
- MLflow is the single source of truth for experiment metrics and artifacts; Postgres holds app entities only (users, projects, prompts, keys).
- A config-driven Model Adapter Layer (`config/models.yaml` + per-provider adapters) abstracts SDKs; adding a model is a YAML edit, not a code change.
- BYOK: the platform never holds platform-wide API keys; users supply their own. Ollama requires no key.

---

## 10. Module Breakdown

| Module | Responsibility |
|---|---|
| **Prompt Analyzer** | Parses input, scores prompt quality, estimates tokens/cost, generates improvement suggestions via LLM-as-judge. |
| **File Ingestion** | Extracts text from PDF/Markdown/CSV/JSON/website inputs for prompt/context analysis. |
| **Model Adapter Layer** | Unified interface (`generate()`, `estimate_cost()`, `get_pricing()`) per provider (OpenAI, Anthropic, Google, local/Ollama). |
| **Experiment Runner** | Orchestrates multi-model/multi-prompt runs, queues jobs, collects raw outputs. |
| **Evaluation Engine** | Runs Ragas metrics, LLM-as-judge (no ground truth), latency/cost/token stats. |
| **Recommendation Engine** | Model-only: constraint filtering + weighted scoring across model × temperature × prompt version. |
| **Model Registry & Auto Router** | Config-driven model list; Auto picks best configured provider per constraints. |
| **Provider Key Manager** | Encrypted BYOK storage; Ollama URL config. |
| **MLflow Integration Layer** | Logs params/metrics/artifacts per run; exposes query API for dashboard. |
| **Dashboard/UI** | Prompt analyzer view, experiment comparison view, recommendation view, MLflow browser view. |
| **Auth & Project Management** | User accounts, project workspaces, API key storage. |

---

## 11. API Specifications

Base URL: `/api/v1`

### Prompt Analyzer
```
POST /prompts/analyze
Body: {
  "project_id": "string",
  "prompt_text": "string",       // optional if file provided
  "file": "multipart/file",       // optional, MD/CSV/JSON
  "task_type": "string",          // e.g. "summarization", "sql_generation"
  "judge_model": "string"         // user-selected model from configured providers
}
Response: {
  "prompt_id": "string",
  "quality_score": 87,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "estimated_tokens": 620,
  "estimated_cost_usd": 0.012,
  "suggested_improvements": ["..."]
}
```

### Experiment Runner
```
POST /experiments/run
Body: {
  "project_id": "string",
  "prompt_ids": ["string"],
  "models": ["gpt-4o", "claude-sonnet-4", "auto"],  // or Ollama model IDs
  "test_inputs": [                                  // inline dataset (no persistent dataset_id required)
    {
      "input": "string",
      "reference_answer": "string",   // optional
      "context": "string"             // optional — enables Ragas faithfulness per row
    }
  ],
  "task_type": "string",
  "temperature": 0.2                  // optional, default per model config
}
Response: {
  "experiment_id": "string",
  "status": "queued"
}

GET /experiments/{experiment_id}
Response: {
  "experiment_id": "string",
  "status": "completed",
  "results": [
    {
      "model": "claude-sonnet-4",
      "quality_score": 0.94,
      "accuracy": 0.91,              // present only when reference_answer provided
      "latency_s": 1.2,
      "cost_usd": 0.007,
      "tokens": {"input": 400, "output": 220}
    }
  ]
}
```

### Recommendation Engine (Model-Only)
```
POST /recommendations/model
Body: {
  "project_id": "string",
  "experiment_id": "string",       // recommendation based on completed experiment results
  "task_type": "string",
  "constraints": {
    "max_cost_usd": 0.01,
    "max_latency_s": 1.5,
    "min_quality_score": 0.90,
    "requires_structured_json": true
  },
  "weights": {"quality": 0.5, "cost": 0.2, "latency": 0.2, "hallucination": 0.1}
}
Response: {
  "recommended": {
    "model": "claude-sonnet-4",
    "temperature": 0.2,
    "prompt_version": "v2"
  },
  "reason": "Satisfies all constraints and offers the highest overall score.",
  "excluded": [
    {"model": "claude-opus-4", "reason": "Exceeds cost budget"},
    {"model": "gpt-4o-mini", "reason": "Misses quality target"}
  ],
  "ranked_options": [ /* full scored list */ ]
}
```

~~POST /recommendations/configuration~~ → **Deferred to v2** (RAG stack).

### Provider Keys
```
POST /projects/{project_id}/providers
Body: {
  "provider": "openai" | "anthropic" | "google" | "ollama",
  "api_key": "string",              // omit for ollama
  "ollama_base_url": "http://localhost:11434"  // ollama only
}

GET /projects/{project_id}/providers
Response: { "configured": ["openai", "ollama"], "available_models": ["gpt-4o", "llama3.2", ...] }
```

### MLflow / Experiment History
```
GET /experiments?project_id=&tag=&limit=
GET /experiments/{experiment_id}/metrics
GET /experiments/compare?ids=exp1,exp2,exp3
```

### Auth & Projects
```
POST /auth/register
POST /auth/login
GET  /projects
POST /projects
```

---

## 12. Database Schema

*Lean schema for solo-dev cost control. Experiment metrics live in MLflow, not duplicated in Postgres.*

**users**
| Column | Type |
|---|---|
| id | UUID (PK) |
| email | varchar, unique |
| password_hash | varchar |
| created_at | timestamp |

**projects**
| Column | Type |
|---|---|
| id | UUID (PK) |
| user_id | UUID (FK → users) |
| name | varchar |
| created_at | timestamp |

**provider_keys**
| Column | Type |
|---|---|
| id | UUID (PK) |
| project_id | UUID (FK → projects) |
| provider | varchar (openai, anthropic, google, ollama) |
| encrypted_key | varchar (nullable for ollama) |
| ollama_base_url | varchar (nullable) |
| created_at | timestamp |

**prompts**
| Column | Type |
|---|---|
| id | UUID (PK) |
| project_id | UUID (FK) |
| version | int |
| raw_text | text |
| task_type | varchar |
| quality_score | float |
| estimated_tokens | int |
| estimated_cost_usd | float |
| judge_model | varchar |
| created_at | timestamp |

**experiments**
| Column | Type |
|---|---|
| id | UUID (PK) |
| project_id | UUID (FK) |
| mlflow_run_id | varchar |
| status | varchar (queued, running, completed, failed) |
| task_type | varchar |
| test_inputs_json | jsonb (ephemeral — not a separate datasets table) |
| created_at | timestamp |

**recommendations**
| Column | Type |
|---|---|
| id | UUID (PK) |
| project_id | UUID (FK) |
| experiment_id | UUID (FK, nullable) |
| request_payload | jsonb |
| recommended_config | jsonb |
| excluded_options | jsonb |
| created_at | timestamp |

~~**datasets**~~ — removed for MVP. Test inputs uploaded inline per experiment (`test_inputs_json`).

~~**experiment_results**~~ — removed for MVP. Results queried from MLflow runs.

### 12.1 Dataset Format (MVP)

Users provide test inputs inline when starting an experiment. Two supported modes:

**Mode A — With reference answers (recommended when available)**
```json
[
  {
    "input": "Summarize this ticket: Customer cannot reset password",
    "reference_answer": "Password reset issue reported.",
    "context": null
  }
]
```
- **Accuracy:** semantic similarity (embedding cosine) between model output and `reference_answer`; exact match for JSON/SQL task types.
- **Quality:** Ragas answer relevancy.

**Mode B — Prompt-only / no ground truth**
```json
[
  { "input": "Write a welcome email for a SaaS onboarding flow" }
]
```
- **Accuracy:** not computed.
- **Quality:** LLM-as-judge score (user-selected model) + Ragas answer relevancy.

**Optional `context` field (not RAG):** A static context string per row. When provided, Ragas faithfulness checks whether the output stays grounded in that context. This is *not* a retrieval pipeline — just optional per-row grounding text.

**Upload formats:** JSON array (preferred) or CSV with columns `input`, `reference_answer` (optional), `context` (optional).

**Minimum for smoke test:** Zero test inputs — experiment runs the prompt once per model with no user message (useful for latency/cost comparison only).

---

## 13. AI Pipeline

1. **Input Ingestion** — prompt text or file (MD/CSV/JSON) → normalized plain text.
2. **Static Prompt Analysis** — rule-based checks + LLM-as-judge (user-selected model) → quality score, strengths/weaknesses/suggestions.
3. **Token & Cost Estimation** — tokenizer run against prompt; mapped to provider pricing from config.
4. **Experiment Execution** — for each model (or Auto-selected model): prompt + test inputs → Model Adapter → raw outputs, latency, tokens.
5. **Evaluation** — Ragas metrics + optional accuracy (if reference answers) or LLM-as-judge (if not).
6. **Scoring & Ranking** — Overall Score per model × temperature × prompt version; constraint filtering.
7. **Recommendation** — top configuration selected; templated human-readable justification.
8. **Logging** — all params, metrics, artifacts → MLflow; experiment metadata → Postgres.

---

## 14. MLflow Integration

Each experiment run logs the following to MLflow:

**Params**
- Experiment ID, Task Type, Model, Temperature, Max Tokens, Prompt Version, Judge Model

**Metrics**
- Prompt Score, Quality Score, Accuracy (if applicable), Answer Relevancy, Faithfulness (if context provided), Latency (p50/p95), Token Usage (input/output), Cost, Overall Recommendation Score

**Artifacts**
- Raw prompt text, raw model outputs, evaluation report (JSON), test inputs (JSON)

**Tags**
- Project name, use case, provider, has_ground_truth (true/false)

MLflow's Tracking Server acts as the historical system of record, enabling:
- Run-to-run comparison (e.g., "why did config A outperform config B?")
- Trend analysis across model versions/releases over time
- Reproducibility — any past recommendation can be traced back to its exact experiment run

---

## 15. Evaluation Metrics

| Metric | Tool | MVP? | Description |
|---|---|---|---|
| Answer Relevancy | Ragas | Yes | Does the answer address the input? Works without ground truth. |
| Faithfulness | Ragas | Yes (conditional) | Output grounded in per-row `context` string when provided. |
| Accuracy | Custom (embeddings) | Yes (conditional) | Semantic similarity or exact match vs. `reference_answer`. |
| Quality Score | LLM-as-judge | Yes (conditional) | User-selected model scores output 0–1 when no reference answer. |
| Latency (p50/p95) | Internal timing | Yes | Response time per request. |
| Token Usage | Tokenizer | Yes | Input/output/total tokens per request. |
| Cost per Request | Pricing table × tokens | Yes | Estimated USD cost from config. |
| Context Precision/Recall | Ragas | v2 | Requires RAG pipeline. |
| Hallucination Rate | DeepEval | v2 | Deferred; faithfulness covers partial need in MVP. |

---

## 16. Recommendation Engine Logic

**Overall Score Formula (default weights, user-configurable):**

```
Overall Score = 0.5 × Quality
              − 0.2 × Cost
              − 0.2 × Latency
              − 0.1 × Hallucination
```

Where Quality, Cost, Latency, and Hallucination are each normalized to a 0–1 scale (min-max normalization across candidate configurations) before applying weights.

**Process:**
1. Gather candidate configurations from completed experiment MLflow runs: **model × temperature × prompt version**.
2. Restrict candidates to models the user has configured (valid BYOK or Ollama).
3. Apply **hard constraint filtering** — exclude configs violating max cost, max latency, min quality score, or structured-output requirements; state reason for each exclusion.
4. Normalize remaining metrics across the surviving candidate set (min-max to 0–1).
5. Compute Overall Score using default or user-supplied weights.
6. Rank and return top configuration. If user selected "Auto", the top-ranked model becomes the Auto routing target for subsequent calls.

**Explainability requirement:** Every recommendation must include a plain-language reason (e.g., *"Accuracy loss only 2%, latency 2x lower, cost 55% lower — best cost/performance ratio"*) rather than only a numeric score.

---

## 17. UI/UX Wireframes

*(Described structurally; visual mockups to be created in Figma post-PRD approval.)*

**Screen 1 — Prompt Analyzer**
- Left panel: prompt text input / file upload (MD, CSV, JSON) / task type selector / **judge model selector** (from configured providers).
- Right panel: Quality Score (large numeric badge), Strengths (✔ list), Weaknesses (✘ list), Token/Cost estimate cards, Suggested Improvements list.
- CTA: "Re-analyze" after edits; "Send to Experiment Runner" button.

**Screen 2 — Experiment Runner**
- Model multi-select chips (from configured providers + **Auto** option).
- Test inputs: paste JSON/CSV inline OR upload file (optional reference answers).
- "Run Comparison" button with pre-run cost estimate confirmation modal.
- Results table: Model | Quality | Accuracy* | Latency | Cost | Tokens (*if ground truth provided).

**Screen 3 — Recommendation Engine (Model-Only)**
- Constraint input form (max cost, max latency, min quality score, structured JSON toggle).
- Priority preset selector (Cheapest / Fastest / Highest Quality / Custom sliders).
- Result card: Recommended model + temperature + prompt version, reason text, excluded options with reasons.
- Requires a completed experiment as input (select from history).

**Screen 4 — MLflow Dashboard**
- Table/list of past experiments with filters (project, date, task type, tag).
- Comparison view with charts (bar) across selected runs.
- Link to MLflow native UI for artifact/param deep-dive (learning MLflow firsthand).

**Screen 5 — Auth, Projects & Provider Settings**
- Simple login/register.
- Project switcher in top nav.
- Provider settings: add/remove API keys (OpenAI, Anthropic, Google), Ollama URL, view available models from config.

---

## 18. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React + Next.js, Tailwind CSS |
| Backend API | Python, FastAPI |
| Async Jobs | RQ + Redis (simpler for MVP solo dev) |
| Database | PostgreSQL (lean schema — Section 12) |
| Experiment Tracking | MLflow (self-hosted via Docker Compose) |
| Evaluation Libraries | Ragas (MVP); DeepEval (v2) |
| Tokenizer | tiktoken + provider-specific equivalents |
| Model Providers | Config-driven: OpenAI, Anthropic, Google Gemini, Ollama |
| Model Registry | `config/models.yaml` — add models/providers without code changes |
| File Parsing | pandas (CSV), stdlib json, markdown-it (MD) |
| Auth | JWT + email/password (bcrypt) |
| Secrets | Fernet encryption for BYOK at rest |
| Deployment | Docker + Docker Compose (MVP local); cloud later |
| CI/CD | GitHub Actions |

---

## 19. Folder Structure

```
Optiq/
├── frontend/
│   ├── app/
│   │   ├── prompt-analyzer/
│   │   ├── experiment-runner/
│   │   ├── recommendations/
│   │   ├── dashboard/
│   │   └── auth/
│   ├── components/
│   ├── lib/
│   └── public/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── prompts.py
│   │   │   ├── experiments.py
│   │   │   ├── recommendations.py
│   │   │   └── auth.py
│   │   │   └── providers.py
│   │   ├── services/
│   │   │   ├── prompt_analyzer/
│   │   │   ├── experiment_runner/
│   │   │   ├── evaluation_engine/
│   │   │   ├── recommendation_engine/
│   │   │   └── model_adapters/
│   │   │       ├── openai_adapter.py
│   │   │       ├── anthropic_adapter.py
│   │   │       ├── gemini_adapter.py
│   │   │       └── ollama_adapter.py
│   │   ├── config/
│   │   │   └── models.yaml          # model registry + pricing
│   │   ├── mlflow_integration/
│   │   ├── models/            # DB ORM models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── workers/           # Celery tasks
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── mlflow/
│   └── docker-compose.mlflow.yml
├── infra/
│   ├── docker-compose.yml
│   └── github-actions/
├── docs/
│   └── Optiq_PRD_v1.md
└── README.md
```

---

## 20. Development Roadmap (Phases)

### Phase 0 — Setup (Week 0)
- Repo scaffolding, Docker Compose (Postgres + MLflow + Redis), CI pipeline skeleton.

### Phase 1 — MVP Core (Weeks 1–4)
- **Week 1:** Repo scaffold (Docker Compose: Postgres + MLflow + Redis), lightweight auth, provider key storage, Prompt Analyzer.
- **Week 2:** Model Adapter Layer (config-driven) + Experiment Runner (multi-model + Auto, async via RQ).
- **Week 3:** Ragas evaluation + MLflow logging wired end-to-end; lean dashboard querying MLflow.
- **Week 4:** Model-only Recommendation Engine + cost confirmation modal + polish.

### Phase 2 — RAG & Advanced Evaluation (Weeks 5–7)
- Full RAG stack recommendation (embedding, chunk size, top-K, retriever).
- RAG experiment pipeline (embed → retrieve → generate).
- DeepEval integration; context precision/recall.
- Persistent dataset library; PDF/URL ingestion.

### Phase 3 — Platform Hardening (Weeks 8–10)
- Multi-project support, team accounts, role-based access.
- API key management UI, rate limiting, retry/backoff robustness.
- Cost-safety confirmations, audit logs.

### Phase 4 — Advanced Intelligence (Weeks 11+)
- Automatic regression detection when new model versions are released.
- Prompt auto-rewrite (apply suggested improvements automatically, re-score).
- Multi-turn/agentic workflow evaluation support.

---

## 21. Acceptance Criteria

**Prompt Analyzer**
- [ ] Given a prompt and user-selected judge model, returns quality score, strengths, weaknesses, token estimate, and cost estimate within 5 seconds.
- [ ] Uploaded MD/CSV/JSON inputs are correctly parsed into analyzable text.
- [ ] Suggested improvements are specific and actionable (not generic platitudes).

**Experiment Runner**
- [ ] User can select ≥2 models (or Auto) and run against the same prompt/test inputs using their BYOK or Ollama.
- [ ] Results table displays quality, latency, cost, and token usage per model; accuracy when reference answers provided.
- [ ] Failed model calls are retried and clearly flagged if they ultimately fail.
- [ ] Pre-run cost estimate shown and requires user confirmation.

**Recommendation Engine**
- [ ] Given constraints and a completed experiment, excludes non-viable model configs and states why for each.
- [ ] Top recommendation includes model + temperature + prompt version with human-readable justification referencing ≥2 metrics.
- [ ] Auto mode ranks only user's configured providers.

**MLflow Integration**
- [ ] Every experiment run logged to MLflow with params, metrics, artifacts (Section 14).
- [ ] Dashboard retrieves and displays ≥2 runs side-by-side with comparison chart.
- [ ] MLflow native UI accessible for learning/inspection.

**Auth & Providers**
- [ ] Email/password registration and login with JWT.
- [ ] Users can store encrypted provider keys and connect Ollama.
- [ ] Models loaded from config; new models addable via YAML without code changes.

**General**
- [ ] Core API endpoints in Section 11 implemented with documented response shapes.
- [ ] No mock/fixture dev mode — all experiments use live user-configured APIs.

---

## 22. Future Scope

- Support for additional providers (Mistral, Cohere, open-weight models via vLLM).
- Auto-regression testing: re-run saved experiments automatically when a tracked model is updated, and alert on score drift.
- Prompt auto-optimization loop (iteratively apply suggestions, re-score, converge on best version).
- Team collaboration features: comments, approvals, shared prompt libraries.
- Agentic/multi-turn workflow evaluation (tool-use accuracy, multi-step task completion rate).
- Marketplace of pre-built, benchmarked prompt templates per task type.
- Native browser/VS Code extension for in-editor prompt scoring.
- SOC2-ready audit logging and enterprise SSO for larger organizations.

---

*End of Document — Optiq_PRD_v1.md*
