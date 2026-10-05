# Optiq — Product Requirements Document (v1)

**Status:** Initial implementation authorized — pilot validation pending

**Last updated:** 2026-10-05

This PRD defines the proposed product direction, not a statement that these capabilities already exist. This revision replaces the dataset-first evaluation scope with prompt-first model advice. The prompt-first implementation is underway; current capabilities and limits are documented in the README.

## 1. Product positioning

> **Optiq helps you choose an affordable LLM for your prompt, explaining the quality–cost trade-off before you spend.**

Optiq is a local-first, open-source-oriented model advisor. A user supplies a prompt, and Optiq suggests models likely to perform the task adequately, explains the recommendation, and estimates costs. When the prediction is uncertain or the decision matters enough to justify testing, the user can run a small, budget-limited comparison.

The core question is:

> “Does this task need an expensive model, or could a cheaper one do it well enough?”

The product does not require users to build a dataset, define a JSON schema, or run a benchmark before receiving advice. Its central value is avoiding unnecessary model spending while making quality trade-offs understandable.

## 2. Problem and target user

Users often select a model because they have heard it is powerful, rather than because their particular task requires it. Repeatedly using that model for routine work can consume credits unnecessarily.

For example, an engineer chooses Opus to generate ordinary essay drafts. A cheaper model may satisfy their requirements, but the engineer has no convenient way to judge that before spending. A research essay with verifiable sources or demanding reasoning may justify a different choice. Optiq must account for those differences instead of categorizing every essay as easy.

**Initial audience:** Engineers, developers, and technically comfortable individual users who can use provider API keys or a local model, but want help choosing among models. Small teams are a secondary audience using the same workflow.

**Primary job to be done:** Before sending a prompt to a costly model, find a lower-cost suitable option and understand when the more expensive choice is justified.

Optiq estimates API usage cost. Consumer subscription credits, message limits, and plan-specific allowances are outside the first release unless the provider exposes reliable conversion rules. It must not equate API estimates with a user's subscription-credit balance.

## 3. Selected USP capabilities

The proposed differentiation is a focused, understandable decision workflow. Model selection itself is not unique; these capabilities must be validated against users' current practices and competing tools.

| Capability | User question | First-release behavior |
|---|---|---|
| **Prompt-based model advice** | “Which model is likely sufficient for this task?” | Assess the task and relevant requirements; suggest a small shortlist of suitable, affordable candidates |
| **Explainable cost and quality trade-offs** | “Why this model, and what might I save?” | Explain suitability, limitations, and estimated costs against an optional user-selected expensive model |
| **Optional budget-limited verification** | “Can I try the alternatives before committing?” | Run a small comparison only when requested; show outputs, costs, and evidence limitations |

Local-first operation, BYOK, simple setup, and user control support these capabilities. They are foundations, not standalone claims of novelty.

**Scope principle:** Help users choose a model efficiently. Do not build a general evaluation platform or routing gateway to deliver the first useful version.

## 4. Main user journey

1. **Enter a prompt.** The user pastes the actual task and supplied context. No labeled dataset is required.
2. **Set essential preferences.** Choose a cost/quality preference and, optionally, an existing model to compare against. Set expected output length, provider restrictions, or local-only use when relevant.
3. **Receive advice.** Optiq identifies the task, explains its assessment, and displays a recommended starting model plus up to two alternatives with estimated costs and important trade-offs.
4. **Clarify only when necessary.** If a missing requirement could materially change the advice, ask a short question or show the assumption used. For an essay, ordinary drafting versus source-supported publication may matter.
5. **Act on the recommendation.** Copy the model identifier and relevant settings for use elsewhere, or choose an optional bounded test using configured providers.
6. **Review test results if requested.** Compare outputs and actual reported usage, mark whether the result meets the need, and keep or change the starting recommendation.

Advice is useful on its own. Running every shortlisted model must not be required to obtain it.

## 5. Supported tasks and boundaries

Initial advice covers a limited set of text-task categories:

- Everyday writing and rewriting, including ordinary essay drafts and email drafts.
- Summarization of text supplied by the user.
- Simple extraction and classification from supplied text.

These categories provide an initial capability taxonomy, not a promise that every prompt within them is easy. Required accuracy, context length, instructions, output format, and specialized knowledge can change the model choice.

Complex coding, autonomous agents, tool execution, image/audio generation, retrieval pipelines, and high-stakes professional advice are outside the initial validated scope. Optiq may identify these requests and explain that its current evidence is insufficient rather than confidently assign a cheap model.

Model capabilities such as browsing and tool use are separate from raw language generation. If a prompt requires current information or source verification, Optiq must identify the missing capability; selecting a more expensive text model alone does not supply it.

## 6. Initial-release scope

| Area | Required | Deferred |
|---|---|---|
| Input | Prompt and supplied text context; a small preferences form | Document parsing, OCR, dataset-library workflows |
| Advice | Task assessment, curated model suitability, explicit requirements and uncertainty | Trained custom router, universal task coverage |
| Model set | Small maintained registry; availability checked before execution | Exhaustive provider coverage, automatic discovery of every model |
| Cost comparison | Per-request estimates and optional repeated-use forecast; optional baseline model | Subscription-credit accounting, guaranteed future savings |
| Verification | User-triggered single-prompt comparison of a small shortlist, bounded output and budget | Large experiments, repeated-trial statistics, automatic prompt optimization |
| Quality feedback | Side-by-side outputs, user acceptance feedback, deterministic checks where applicable | Mandatory paid judge, universal automated quality score |
| Result | Advice, reasons, limitations, model/settings copy action, lightweight saved comparison | Regression-test exports, product evaluation CLI, CI integrations |
| Runtime | Primary native Linux/WSL path; BYOK; optional local inference | Mandatory Docker Desktop, mandatory MLflow, platform-funded API usage |

No runtime production routing, automatic escalation, or silent execution of the recommendation is included. Those require separate product and budget decisions.

## 7. Recommendation approach

### 7.1 Assess the task before ranking models

Capture the task type, input/context size, requested output length, format requirements, reasoning or knowledge demands, language, and stated preferences. Distinguish explicit requirements from inferred assumptions.

Apply hard eligibility checks first: provider restrictions, context/output limits, required capabilities, availability, and any cost ceiling. A low price does not make an ineligible model suitable.

For eligible models, use a versioned capability registry and explicit selection rules to produce a practical shortlist. Initially, maintain a small curated model set and evaluate the advice on representative prompts. A trained routing model is not required for the first release.

An automated prompt assessor may assist with task classification, but its output is a prediction. It must not fabricate performance measurements or use an expensive model for every advisory request without accounting for that overhead. Record the advisory method and version.

### 7.2 Prefer affordability within the user's quality needs

Recommend a lower-cost starting option when the available evidence supports its suitability. Explain the reason in concrete terms, such as routine rewriting, manageable context length, or limited reasoning requirements.

Do not always choose the cheapest model. Important quality requirements may justify a stronger candidate. When the expected benefit of a more expensive model is unclear, make that uncertainty visible and offer optional testing.

Do not claim “lowest-cost capable model” across the entire market. Advice is limited to the supported registry, declared requirements, and available evidence.

### 7.3 Honest result states

| State | Meaning | User-facing behavior |
|---|---|---|
| **Suggested starting model** | Assessment supports trying this model for the prompt | Show reasons, assumptions, estimated cost, and alternatives; label it as untested on this prompt |
| **Tested on this prompt** | The user ran the model and reviewed the result or applicable checks | Show the output, feedback/checks, usage, and test scope; do not generalize one result into a reliability guarantee |
| **Insufficient information or evidence** | Important requirements or capability evidence are missing | Ask a targeted question or suggest a bounded comparison |
| **No suitable supported model** | Known requirements exclude the available model set | Explain exclusions without restoring an unsuitable candidate as a winner |

Avoid numerical confidence percentages unless they are calibrated and validated. Qualitative uncertainty must explain what is unknown, not merely attach a confidence label.

## 8. Cost transparency

Before execution, estimate generation cost using the selected model's pricing, estimated input tokens, and the user's expected output length. Show assumptions, pricing source/date, and whether token counts are measured or approximated. Account for provider-specific billable categories when applicable; unsupported pricing rules must be disclosed.

For an optional baseline comparison, use the same prompt and output-length assumptions. Present the difference as **estimated API savings if the cheaper output is acceptable**, not guaranteed savings or verified equal quality.

A repeated-use forecast may multiply the stated workload by the estimated per-request cost, but must show that assumption. Do not forecast subscription-credit savings from API prices.

Keep these costs distinct:

- **Advice overhead:** Any paid call used to analyze the prompt or select a model.
- **Verification spend:** Calls made to compare candidate outputs, including billable failures and retries.
- **Projected task cost:** Expected cost of using the selected model for the actual task.

A user's net savings must account for advice and testing overhead. For an inexpensive one-off task, comparison costs may exceed the possible savings; the interface should show this rather than automatically run more calls.

Unknown prices are not zero. Local inference may have zero API charges but still incurs compute, hardware, and energy costs. Label local comparisons accordingly.

## 9. Optional budget-limited verification

The user selects candidates and confirms a visible test scope and budget before calls are dispatched. Default to a small shortlist and bounded output length; no hidden paid judge or automatic premium fallback.

Reserve conservative estimated cost before each paid call, atomically across concurrent requests. Do not dispatch new calls when the remaining unreserved budget cannot cover them. Include any allowed retries and reconcile reservations against reported usage. Unknown paid pricing blocks budgeted execution until resolved.

Show outputs side by side, with model/settings, latency, reported token usage, recorded or estimated cost, errors, and user acceptance feedback. For extraction/classification, offer applicable deterministic checks when the user supplies a schema, allowed labels, or expected output. These are optional checks, not prerequisites for advice.

For subjective writing, a single output cannot prove that a model is generally good enough. User feedback establishes preference for the observed result; automated grading, if added later, must also disclose its limitations and cost.

Budget reservations control dispatch, not the provider's final invoice. In-flight requests, usage-reporting gaps, and pricing discrepancies may cause differences. Cancellation stops new work but does not imply active calls are unbilled. Preserve partial results and accounting.

## 10. Example experience

**Prompt:** “Write an 800-word introductory essay about remote work for a general audience.”

**Optional baseline:** The expensive model the user currently uses.

**Expected advice:** Identify ordinary long-form drafting, suggest a supported lower-cost writing model, and show estimated costs based on the stated length. Explain that specialized research, verified citations, or unusually demanding style requirements could change the recommendation.

**Next action:** Copy the suggested model/settings or spend a clearly stated amount to compare a draft with the baseline.

This is an illustrative workflow, not an assertion that a particular model will perform equally well or deliver a fixed percentage saving.

## 11. Trust repairs in the current repository

The existing application is a foundation, not validation of this product promise. Prioritize repairs that affect advice and optional testing:

| Gap | Required correction |
|---|---|
| Reference answers can enter generation input | Keep reference outputs evaluation-only when users supply them |
| Requirements are incompletely propagated | Apply the full preference and hard-requirement set through eligibility, estimation, and recommendations |
| Excluded candidates can be restored as winners | Return an honest unsupported/insufficient outcome instead |
| Evaluation and denominators differ across paths | Retain failures and use consistent deterministic checks where applicable; do not present unlike scores as comparable quality |
| Estimates omit call-path costs | Account for advisory calls, generation, permitted retries, and any evaluation separately |
| Model IDs and prices can become stale | Version the registry, record provenance, and distinguish unavailable or unknown-cost models |
| Existing “Auto” behavior could imply validated intelligent routing | Explain the actual selection method and validate it before making capability claims |

A prompt-writing score is not evidence that a specific model can complete the user's task. Fixing these issues takes priority over expanding the dashboard or adding optimization features.

## 12. Technical and contributor approach

Keep the existing FastAPI backend and Next.js frontend. Separate task assessment, model eligibility/ranking, pricing estimates, and optional provider execution so each can be inspected and tested independently.

Store advice assumptions, registry/advisor versions, selected configurations, optional test results, and cost records in the application database. SQLite supports native local development; PostgreSQL and queue services remain optional deployment choices. MLflow is optional, not a required source of truth.

Local-first means the application and stored history can run locally. Hosted inference or hosted prompt assessment sends selected data to that provider; disclose this before transmission. Local-only operation must not silently invoke a cloud assessor.

Contributor requirements:

- One primary documented setup/start path for Linux and WSL, with health checks and troubleshooting.
- No Docker Desktop requirement. Optional containers need a compatible engine; Docker CLI alone is insufficient.
- Routine restarts reuse dependencies and preserve data. Reinstall when dependency declarations change or the environment is recreated.
- Automated checks use provider fixtures and do not require paid keys. Live-provider checks are explicit and optional.
- Secrets remain absent from source control, logs, saved reports, and copy/export actions.
- Select an open-source license before publishing a licensed open-source release; this remains a maintainer decision.

This PRD does not finalize API contracts or migrations. Those follow scope review.

## 13. Implementation order

| Priority | Deliverable | Completion condition |
|---|---|---|
| **1 — Trust and foundations** | Repair constraints, leakage, accounting, registry provenance, and misleading result states | Advice and tests cannot silently violate requirements or hide costs |
| **2 — Prompt-first advisor** | Prompt input, essential preferences, small model registry, shortlist, explanations, cost comparison, copy action | A user can obtain useful advice without a dataset or paid multi-model experiment |
| **3 — Optional verification** | Bounded shortlist execution, side-by-side results, user feedback, usage/accounting | The user can inspect alternatives within a disclosed experiment scope and budget |
| **Later — Recurring workloads** | Dataset-based validation, configuration exports, regression CLI/CI, stronger learned selection | Pursue only when pilots show a recurring need |

The proposed initial release includes priorities 1–3. Automated search, universal quality grading, production routing, and team platforms are not initial commitments. Delivery estimates follow approved scope and a technical breakdown.

Current CI tests the application code. User configuration regression gates would be a separate future product capability.

## 14. Release acceptance criteria

1. A user can start Optiq through the documented native Linux/WSL setup without Docker Desktop.
2. A user can paste a supported prompt and obtain model advice without supplying reference answers or a dataset.
3. Advice shows task assessment, assumptions, suitability reasons, limitations, and transparent cost estimates.
4. Unsupported capabilities, unavailable models, hard restrictions, unknown prices, and missing information are handled explicitly.
5. Prompt-based advice is labeled as predicted suitability; an optional test is labeled with its actual evidence scope.
6. Advisory and comparison overhead are visible and included when discussing savings. No paid candidate execution occurs merely because advice was requested.
7. An optional comparison honors reservations across concurrent calls and permitted retries; incomplete runs retain costs and results.
8. Subjective outputs are not given fabricated accuracy guarantees, and failures do not disappear from summaries.
9. Local-only mode does not send prompts to hosted services. Credentials do not appear in reports or copy actions.
10. A reviewed set of representative prompts exercises suitable lower-cost choices, justified stronger-model choices, and unsupported or ambiguous requests before a pilot.

Use deterministic application tests for requirements and accounting, plus explicit live-provider trials and user review to validate the usefulness of advice. A successful software test alone does not establish recommendation quality.

## 15. Validation and competitive context

Run a small pilot with engineers and technically comfortable users who currently choose models manually. Test whether advice changes a real decision and whether the suggested cheaper output is acceptable to them.

Measure time to decision, acceptance of suggested outputs, observed task cost against the user's baseline, advisory/testing overhead, and repeat use. Track incorrect cheap-model advice as well as unnecessarily expensive recommendations. Set numerical success targets after collecting initial observations.

Prompt-based selection is an existing category. [Not Diamond's routing documentation](https://docs.notdiamond.ai/docs/key-concepts) describes model selection using quality, cost, and latency trade-offs. Optiq's proposed distinction is transparent advice, user control, accessible local operation, and optional bounded verification; superiority and uniqueness are not established.

The [earlier competitive research](docs/competitive-research.md) provides broader evaluation-tool context. Its dataset-first positioning proposal is superseded by this PRD and should not determine the initial product scope.

## 16. Scope review

The decisions proposed for review are:

- **Core problem:** Avoid unnecessarily expensive model use for a user's prompt.
- **Primary experience:** Advice first; optional testing second; no mandatory dataset.
- **Selected USPs:** Prompt-based suitability advice, explainable cost/quality trade-offs, and bounded verification.
- **Initial audience:** Engineers and technically comfortable users using APIs or local models.
- **Boundary:** A small supported task/model set, with explicit uncertainty; recurring-workload evaluation and automatic routing deferred.

Implementation follows the priorities above, starting with trust repairs and the prompt-first journey. User pilots and live-provider validation are required before claiming the recommendations reliably save money while meeting quality needs.
