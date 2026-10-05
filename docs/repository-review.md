# Repository review

Optiq is an LLM experiment application: projects own encrypted provider credentials and saved prompts; experiments generate answers across model/prompt/test-case combinations; evaluation produces metrics; recommendations rank the resulting configurations. It does not train models or independently optimize model weights. The prompt analyzer combines rules with optional model feedback.

The Linux/WSL setup work addresses contributor onboarding, optional dependencies, local mail, explicit job backends, SQLite concurrency, job-start metadata races, zero-temperature handling, and frontend dependency installation. It also updates Next.js from 14.2.17 to 14.2.35, the patch specified in the December 2025 advisory. A supported-major framework upgrade remains future maintenance work.

## Product correctness issues still present

These findings come from code inspection. They are not resolved by the development setup changes.

| Priority | Finding | Evidence and consequence |
|---|---|---|
| High | Reference answers are included in generation input | `_compose_generation_input` in `backend/app/services/phase1.py` appends `Reference Answer: ...`. The model can copy the expected answer, making reference-based accuracy unsuitable as an independent benchmark. Keep references only on the evaluation side. |
| High | Recommendation API drops constraints | `backend/app/api/recommendations.py` passes only goal and weights to `score_recommendations`, omitting max cost/latency, minimum quality, and structured JSON requirements. Unit tests of the scoring helper do not prove that the API honors these fields. Add API-level tests when fixing this. |
| High | Scoring helper can select an excluded configuration | When no option meets constraints, `score_recommendations` reinstates the highest-quality option. Return an explicit no-feasible-configuration result instead of silently violating limits. |
| High | Estimates and recorded costs omit evaluation spend | `estimate_experiment_cost` uses an output estimate capped at 512 tokens while generation uses registry limits. `evaluate_row` may make embedding, judge, and Ragas requests, whose usage is absent from recorded row costs. Estimates are not a budget cap, and reported totals are incomplete. |
| Medium | Quality depends on inconsistent evaluation paths | Ragas is selected for OpenAI generation rows with an OpenAI key; other providers use different paths. Fallback quality scores output text using prompt-writing rules. Provider-specific judges and fallback scores are not directly comparable evidence of answer correctness. |
| Medium | Structured output detection is weak | Recommendations accept an output starting with `{`, and use `any` across cases, without parsing JSON or requiring every case to succeed. Partial failures are also excluded from the successful-case averages. |
| Medium | Synchronous analysis blocks an async route | `backend/app/api/prompts.py` calls synchronous SQL/judge HTTP work from an async upload handler. A slow judge can delay other requests handled by that event loop. |
| Medium | Hosted Ollama URLs need an access policy | User-configurable URLs cause server-side HTTP requests. That is useful for self-hosted development, but public hosting needs a policy for allowed destinations, private networks, and response/error handling. |

## Validation completed locally

- All 24 backend tests pass in a fresh environment containing only core/development dependencies, including signup, verification, project/provider creation, prompt analysis, estimation, background execution, and recommendation persistence with fake adapters.
- SQLite Alembic upgrades complete and `alembic check` reports no metadata drift.
- Native API and frontend startup return HTTP 200; Ctrl+C stops both processes.
- Frontend lint/type checks and production build are checked by `./scripts/optiq check --build`.
- Compose YAML and inherited environment configuration are checked; CI now validates it with Compose and separately checks Postgres migration upgrades/downgrades.

Live provider calls, optional Ragas/MLflow execution, Docker image builds, and Postgres/RQ execution have not been verified in this WSL session. Docker Engine is unavailable here. The added CI workflows have not yet run on GitHub.

The repository also needs a maintainer-selected license before it can be distributed as licensed open source.
