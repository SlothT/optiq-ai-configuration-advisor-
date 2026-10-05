# Model Advisor: current behavior

The primary journey is prompt → model advice → optional output comparison. Advice requires no account or provider key and never calls a model provider. The API is `POST /api/v1/advice`; the UI retains `/prompt-analyzer` as its route but displays **Model Advisor**.

## Selection rules

The advisor identifies routine writing, summarization, extraction, or classification using local task patterns. Ambiguous requests, coding/agent tasks, high-stakes requests, and requests needing browsing or current information receive an insufficient-information response. This is a deliberately small starter taxonomy, not a universal understanding of prompts.

Eligible models must match provider/local-only restrictions, configured input/output limits, a supported task, a curated capability tier, and any per-request API cost ceiling. Demanding wording or the quality preference raises the minimum tier. Models are then ordered by estimated API cost within that eligible set. Local options are offered separately from comparable hosted economics; their compute costs are unknown.

Balanced currently uses the same minimum curated tier as cost. It does not invent a measured quality/cost trade-off. Capability tiers are manually curated hypotheses, and classification rules can misread a prompt. The returned method/version, assumptions, and limitations make those decisions inspectable. Do not interpret advice as benchmark evidence or a calibrated confidence score.

The registry includes a small enabled starter set and keeps disabled legacy entries for history. Paid pricing carries a source and checked date; advice excludes snapshots over 90 days old. Provider entitlement and live model availability are not established by advice. Configure and explicitly test a model before relying on it.

## Pricing sources

Rates were checked on 2026-10-05 against [OpenAI GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o), [OpenAI GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), and [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing). Update `backend/app/config/models.yaml` and its version when refreshing prices or model identifiers. Capability tiers are Optiq's assumptions, not claims supported by those pricing pages.

Costs use standard text-token rates and an expected output length. Tools, caching, discounts, subscription allowances, and local operating costs are not covered. Gemini Flash-Lite comparisons disable optional thinking; reported thought tokens, if present, are included in output usage.

## Optional verification

Sign in, create a project, configure providers, and prepare a test from the advisor. Saving the prompt uses local rules without paid prompt review. The prompt, candidate/baseline identifiers, and output limit carry into Experiment Runner. Additional input is optional; leaving it empty runs the saved prompt itself. No reference answer enters generation input.

Estimate and explicitly confirm the comparison. Output limits are identical between estimation and execution. Budgets apply to individual experiments; they are not shared account-wide limits. An atomic queued-to-running claim prevents two workers dispatching the same reservation. The worker persists progress before and after each call. Automatic retries, embedding evaluation, and paid judges are disabled in this path.

Provider-reported usage is distinguished from token estimates. Failed calls with unknown billing retain a reservation and an unresolved cost, rather than a fabricated zero. Partial results survive a dispatch stop or job failure. Local development jobs can still be interrupted by an API reload; use the persistent queue for durable deployment work.

JSON references are compared as parsed values with explicit case/type preservation. Classification references use normalized whitespace with case preserved. Other subjective responses remain unscored. Side-by-side review and user feedback apply only to observed outputs, not statistically established performance. Ranked experiment results enforce hard requirements and reject failed candidates; quality requirements cannot pass with unknown quality.

## Next validation work

Review representative supported prompts with actual users and opt-in live-provider trials. Measure whether cheaper suggestions produce acceptable outputs and whether advice/testing overhead leaves useful savings. Improve the taxonomy or model tiers only with evidence. Learned routing, repeated-trial reliability, dataset regressions, and CI gates remain outside this implementation.
