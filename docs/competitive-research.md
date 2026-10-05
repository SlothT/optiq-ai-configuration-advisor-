# Optiq: competitive research and product direction

Research date: 5 October 2026.

## Recommendation

Position Optiq as a lightweight, local-first decision tool for small engineering teams selecting an LLM configuration for a specific task. The proposed promise is:

> Find the lowest-cost configuration that meets your quality and latency requirements, using your own examples and a reproducible evidence report.

Start with structured extraction and classification. Establish reliable evaluation before adding automatic prompt search or runtime routing. Treat this positioning as a hypothesis to validate with users, not an established market gap or an exclusive capability.

## Method and limitations

This review compares official product documentation and public product pages with Optiq's PRD, backend implementation, and frontend flows. It is a documentation-based comparison, not a hands-on trial of every product. Vendor performance, adoption, savings, and usability claims have not been independently verified. A feature not found in reviewed documentation must not be assumed absent from a competing product.

Optiq implementation references: `Optiq_PRD_v1.md`, `backend/app/services/phase1.py`, `backend/app/services/evaluation.py`, `backend/app/api/recommendations.py`, `backend/app/services/auto.py`, `backend/app/models/domain.py`, and `frontend/app/recommendations/page.tsx`.

## Comparable products

| Product | Documented strength | Relationship to Optiq | What to learn |
|---|---|---|---|
| Promptfoo | Local evaluation CLI/library, configurable assertions, comparison matrices, caching, concurrency, and CI integration | The closest open-source alternative to the experiment runner | Portable evaluation configuration, deterministic checks, inexpensive repeated runs, and regression gates. [Documentation](https://www.promptfoo.dev/docs/intro/) |
| Braintrust | Browser playgrounds, immutable experiments, code/judge scorers, production evaluation, and failure-to-dataset workflows | Strong reference for experiment analysis and iteration | Case-level output/score diffs, reproducible snapshots, and a clear path from exploratory runs to release evidence. [Evaluation workflow](https://www.braintrust.dev/docs/evaluate), [playgrounds](https://www.braintrust.dev/docs/evaluate/playgrounds) |
| LangSmith | Offline and online evaluations, datasets, human/code/judge/pairwise evaluation, and production feedback | Broader lifecycle platform with substantial evaluation overlap | Evaluator configuration and turning real failures into regression examples. [Evaluation documentation](https://docs.langchain.com/langsmith/evaluation) |
| Langfuse | UI experiments comparing prompt/model versions, dataset versions, evaluators, and baseline comparisons; self-hosting | Direct overlap with Optiq's GUI and self-hosting direction | Versioned datasets, pinned evaluators, metadata, and detailed baseline analysis. [UI experiments](https://langfuse.com/docs/evaluation/experiments/experiments-via-ui), [comparison](https://langfuse.com/docs/evaluation/experiments/compare-experiments) |
| Vellum | Visual prompt/workflow development and test suites with multiple metrics and regression testing | Similar guided workflow, with much broader orchestration | Guided test creation and task-specific validators. [Overview](https://docs.vellum.ai/home/getting-started/overview), [test suites](https://docs.vellum.ai/product/evaluation/quantitative-evaluation) |
| PromptLayer | Side-by-side model evaluation, version-triggered evaluations, backtests, and configurable evaluation columns | Another direct GUI competitor | Bind every result to prompt and dataset versions; combine code checks, human feedback, and judge scores. [Evaluations](https://www.promptlayer.com/evaluations/) |
| Portkey | Multi-model prompt comparison, prompt versioning/deployment, and gateway capabilities | Overlap with model comparison; adjacent to any future serving/routing layer | Keep provider access and deployment configuration portable. Its current site brands the gateway as PRISMA AIRS AI Gateway. [Prompt management](https://portkey.ai/features/prompt-management) |
| Not Diamond | Intelligent per-input model routing; current positioning emphasizes coding agents | A direct competitive threat to a future automatic-routing proposition | Model recommendation and cost/quality optimization are already established categories. Avoid claiming their invention. [Current product positioning](https://www.notdiamond.ai/) |

Artificial Analysis is an adjacent reference: its public analysis separates model intelligence, prices, speed, and latency. It can inform candidate discovery, but public benchmark results are not measurements on an Optiq user's workload. [Model and provider analysis](https://artificialanalysis.ai/)

## What is already common

The following are useful product requirements but weak standalone differentiators:

- Comparing models or prompt versions.
- Bring-your-own-key provider access.
- Local execution or self-hosting.
- Cost and latency dashboards.
- LLM-as-a-judge scoring.
- Prompt improvement suggestions.
- Returning a ranked result.

Promptfoo already supports cost and latency assertions, and weighted best-output selection. Its documentation distinguishes completed-response checks from mechanisms that limit spending. Therefore, a weighted recommendation and a cost threshold alone do not establish a defensible USP. [Assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [best-output selection](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/max-score/), [getting started](https://www.promptfoo.dev/docs/getting-started/)

Braintrust also supports feedback-assisted prompt improvement in its playground. Optiq should not present automatic prompt suggestions as a new category. [Playground annotation and optimization](https://www.braintrust.dev/docs/evaluate/playgrounds)

The PRD's statement that there is no systematic, constraint-aware tooling should be revised when the PRD is next updated. The evidence supports a competitive category with room for a focused workflow, not an empty market.

## Optiq's current position

Optiq already has a coherent foundation: project ownership, encrypted provider keys, a configurable model registry, prompt analysis, batch test inputs, asynchronous experiments, metrics, and a recommendation endpoint. The new Linux/WSL setup reduces contributor friction.

The implemented recommendation is a weighted ranking of observed model/prompt results. It is not yet an optimizer exploring a configuration space. Temperature is specified once for an experiment rather than searched across candidates. Auto expands configured models or picks a model using preferences/history; it is not a learned per-request router.

| Area | Present implementation | Gap to close |
|---|---|---|
| Task evaluation | References, overlap/embedding scores, optional Ragas, and judge/fallback quality | Consistent task-specific scoring with clear provenance and human calibration |
| Constraints | Request schema and filtering helper exist | UI exposes goals rather than requirement fields; API drops constraints; helper reinstates an excluded option when none qualify |
| Cost | Registry-based generation estimates and recorded generation usage | Evaluation/retry/fallback accounting, budget reservation, price provenance, and cost per accepted result |
| Datasets | Test inputs stored inside experiments | Reusable datasets, stable case IDs, versioning, development/holdout split, and segment labels |
| Comparisons | Summary tables and basic experiment comparison | Matched case diffs, failure analysis, uncertainty, and comparisons against a saved baseline |
| Optimization | Model/prompt selection and one experiment temperature | Bounded search over prompt variants and permitted model parameters |
| Operational workflow | Web application and development scripts | Product evaluation CLI, exportable configurations, and release gates; repository CI currently tests application code |
| Model catalog | Small YAML registry with static prices and adapter assumptions | Availability/capability checks and dated pricing snapshots; support new models based on capabilities rather than blanket parameters |
| Trust | Ownership checks, encrypted keys, recorded outputs | Reproducibility metadata, complete failure handling, rigorous validators, and a chosen open-source license |

### Correctness blockers

These are current implementation issues, not speculative feature requests:

1. `_compose_generation_input` sends the reference answer to the model being tested, contaminating evaluation.
2. The recommendation API omits requested cost, latency, quality, and structured-output constraints when calling its scoring helper.
3. The helper can recommend a configuration it excluded when every candidate violates requirements.
4. Different provider paths use different evaluation methods; fallback prompt-writing rules are not a reliable answer-quality metric.
5. Additional evaluation calls are missing from recorded costs; generation estimates use smaller output assumptions than the configured generation limits.
6. Structured-output detection checks an opening brace and accepts any successful-looking case instead of validating the JSON/schema across required cases.

See [repository review](repository-review.md) for further evidence. Fix these before promoting Optiq as a trustworthy advisor.

## Proposed USP

### Audience and initial task

Target backend/full-stack developers and small product teams who have a working LLM feature and need to choose or downgrade its model safely. The PRD's simultaneous focus on beginners, startups, consultants, and enterprise platform teams is too broad for an initial release.

Begin with JSON extraction and classification. Expected fields, types, labels, and critical-case behavior can be checked directly. Free-form assistant quality, RAG pipelines, SQL execution, and coding-agent routing introduce evaluation and infrastructure complexity that should follow later.

### Product promise

> Optiq helps small teams choose an affordable LLM configuration that passes their acceptance tests, with a local-first workflow and evidence they can reproduce and export.

This is a proposed combined positioning. None of its individual components is exclusive. Its value must be demonstrated through faster onboarding, useful acceptance-test templates, credible recommendations, and repeated real decisions.

### Differentiating experience

1. **Task definition before model selection.** Ask for expected output, schema/labels, critical failure cases, a baseline, and representative examples. Help users define success instead of treating prompt style as output quality.
2. **Requirements before weights.** Filter on acceptance thresholds, error rate, p95 latency, permitted providers, and structured-output validity. Rank only feasible candidates. Return `no feasible configuration` or `insufficient evidence` when appropriate.
3. **Evidence with uncertainty.** Show matched-case improvements/regressions, sample counts, repeated trials, confidence intervals, and results by task segment. Latency conclusions must identify the endpoint, region, concurrency, and cache conditions under which they were measured.
4. **Transparent economics.** Distinguish total experiment spend from projected serving cost. Include retries and fallback paths in cost per accepted response. Keep API charges separate from optional local hardware/energy costs; a local model has zero provider API charge, not necessarily zero operating cost.
5. **Controlled experiment spend.** Reserve a conservative per-call budget including evaluation, cap output/retries, and stop dispatching new work when the remaining budget is insufficient. Disclose in-flight requests and uncertainty in provider billing; do not promise an absolute invoice cap without reliable accounting.
6. **Portable decision report.** Export prompt/configuration, dataset and evaluator fingerprints, model/price snapshots, measurements, exclusion reasons, and example failures. Provide Python/TypeScript examples and a regression-test configuration.

Local-first means experiment records and secrets can remain in the user's environment. Requests still leave that environment when a cloud provider is enabled. A fully local workflow requires a local model and local evaluators.

### Example user journey

An engineer imports representative extraction examples, defines the schema and critical fields, sets a latency target, chooses a baseline, and enters a maximum experiment budget. Optiq compares a small model shortlist on development cases, validates candidates on held-out cases, and presents:

- Recommended configuration, or an explicit no-decision outcome.
- Quality/failure differences from the baseline with uncertainty.
- Cost per accepted extraction and the experiment's evaluation spend.
- Tail latency measured under stated conditions.
- Failed cases and reasons other configurations were excluded.
- An export suitable for review and regression testing.

This is an illustrative future workflow; the current application does not implement all of it.

## Roadmap with release gates

| Milestone | Work | Gate |
|---|---|---|
| 1. Trustworthy comparison | Fix reference leakage and constraints; pin evaluator policy; validate schemas; retain failures; improve cost accounting | API-level tests prove references never enter generation, constraints are enforced, and all-failed/all-infeasible runs produce no recommendation |
| 2. Decision-focused MVP | Version datasets; save baselines; expose requirements; support extraction/classification templates; add matched-case views and export | A new user can complete one meaningful comparison and understand failures, tradeoffs, and the recommendation without editing application code |
| 3. Affordable optimization | Add bounded parameter/prompt search, budget reservation, cache-aware execution, repeats, and holdout validation | Recommended candidates pass untouched holdout tests; measured search spend and stopping behavior match the displayed accounting |
| 4. Team workflow | Product evaluation CLI, CI regression gates, import/export integrations, saved decision history | A team can reproduce a decision and detect a regression outside the web UI |
| Later | Scheduled re-evaluation, richer task evaluators, or serving integrations | Add only after users repeatedly request these workflows and the cost/benefit is measured |

Keep the default installation lightweight. Dataset snapshots and evidence can start in SQLite plus local artifacts. Add Postgres/RQ for shared or durable execution. Keep MLflow and heavyweight evaluation packages optional. Consider importing/exporting existing Promptfoo configurations rather than immediately recreating every assertion engine.

## Validation and measures

Interview 5–10 intended users about their most recent model-selection decision. Ask for a representative dataset, current process, acceptance requirements, experiment budget, and what evidence would make them switch a deployed configuration. Conduct these interviews before investing in a broad dashboard or routing engine.

Use pilots to compare Optiq against each team's existing process. Measure time to first usable decision, evaluator setup effort, experiment cost, acceptance on held-out cases, recommendation reproducibility, and whether users return for a second decision. Any time/savings target is a product hypothesis until measured.

Possible business model: a licensed open-source local core with paid collaboration, managed execution, private deployment support, or maintained task packs. Pricing and willingness to pay require separate research. Do not make the core depend on hosted accounts merely to run a local experiment.

The long-term advantage would come from validated task packs, calibration practices, integrations, and trust earned from repeated decisions. A weighted scoring formula or an attractive dashboard alone is readily reproducible by competitors.
