"""Inspectable prompt advice. No provider requests or learned-quality claims."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.config.model_registry import list_models, load_registry, resolve_model_info
from app.services.phase1 import estimate_cost, estimate_tokens

ADVISOR_VERSION = "rules-v1"
TIERS = {"budget": 0, "balanced": 1, "premium": 2}
TASK_PATTERNS = {
    "summarization": r"\b(summarize|summarise|summary|condense)\b",
    "classification": r"\b(classify|classification|categorize|categorise|label)\b",
    "extraction": r"\b(extract|extraction|parse)\b",
    "writing": r"\b(write|draft|rewrite|rephrase|essay|email|proofread)\b",
}
UNSUPPORTED = r"\b(code|coding|debug|sql|agent|diagnos\w*|prescrib\w*|medical|legal|investment|image|audio|video)\b"
CURRENT_INFO = r"\b(latest|today|current news|browse|web search|verified citations|verifiable sources|real.time)\b"


def advise(request: dict[str, Any]) -> dict[str, Any]:
    text = request["prompt"].strip()
    task = next((name for name, pattern in TASK_PATTERNS.items() if re.search(pattern, text, re.I)), "unknown")
    input_tokens = estimate_tokens(text)
    output_tokens = request.get("expected_output_tokens", 1024)
    assumptions = [
        f"Estimate uses {input_tokens} input tokens and {output_tokens} output tokens; actual output length can differ.",
        "Text-only standard API rates; no caching, tools, subscription credits, or provider discounts.",
        "Curated model tiers predict suitability; they are not measured quality or calibrated confidence.",
        "Provider access and model availability are checked during optional execution, not by this offline advice.",
    ]
    if task == "writing":
        assumptions.append("Assumes ordinary drafting from supplied information, not verified research or publication-level accuracy.")
    result = {
        "outcome": "suggested_starting_model", "task_type": task,
        "advice_method": ADVISOR_VERSION, "registry_version": load_registry().get("registry_version"),
        "input_tokens": input_tokens, "expected_output_tokens": output_tokens,
        "advice_cost_usd": 0.0, "assumptions": assumptions,
        "limitations": ["Untested on this prompt. Review an output before relying on the suggestion."],
        "recommended": None, "alternatives": [], "excluded": [], "baseline": None,
    }
    if task == "unknown" or re.search(UNSUPPORTED, text, re.I) or re.search(CURRENT_INFO, text, re.I):
        result.update(outcome="insufficient_information", explanation=(
            "This starter advisor covers routine writing, summarization, extraction, and classification. "
            "The request is ambiguous or needs capabilities outside that scope. Clarify the task or use explicit testing; "
            "a more expensive text model alone does not provide browsing or source verification."
        ))
        return result

    demanding = bool(re.search(r"\b(rigorous|nuanced|advanced|expert|complex|technical)\b", text, re.I))
    minimum_tier = 1 if demanding or request.get("preference") == "quality" else 0
    allowed = set(request.get("allowed_providers") or [])
    candidates = []
    for model in list_models():
        reasons = []
        local = model.provider == "ollama"
        if allowed and model.provider not in allowed:
            reasons.append("Provider excluded by your preference")
        if request.get("local_only") and not local:
            reasons.append("Local-only requirement")
        if task not in model.supported_tasks or TIERS.get(model.advice_tier, -1) < minimum_tier:
            reasons.append("Curated capability tier does not cover the stated requirements")
        if input_tokens + output_tokens + 64 > model.context_window:
            reasons.append("Estimated request exceeds the configured context limit")
        if output_tokens > model.max_tokens:
            reasons.append("Requested output exceeds the configured output limit")
        cost = None
        if local or model.pricing:
            cost = estimate_cost(model.id, input_tokens + 64, output_tokens)
        else:
            reasons.append("Unknown pricing")
        if not local:
            checked = date.fromisoformat(model.pricing_checked_at) if model.pricing_checked_at else None
            if checked is None or (date.today() - checked).days > 90:
                reasons.append("Pricing snapshot needs review")
        if request.get("max_cost_usd") is not None and cost is not None and cost > request["max_cost_usd"]:
            reasons.append("Exceeds your per-request API cost ceiling")
        if reasons:
            result["excluded"].append({"model_id": model.id, "reasons": reasons})
            continue
        candidates.append({
            "model_id": model.id, "display_name": model.display_name, "provider": model.provider,
            "tier": model.advice_tier, "estimated_cost_usd": cost, "cost_is_local": local,
            "pricing_source": model.pricing_source, "pricing_checked_at": model.pricing_checked_at,
            "temperature": 0.2, "max_output_tokens": output_tokens,
            "reason": f"Curated {model.advice_tier} candidate for {task}; compare an output to your requirements.",
            "limitation": "Zero API charges; local operating costs and hardware suitability are unmeasured." if local else "API estimate only; availability and output quality are unverified.",
        })
    # Never equate unmeasured local operating cost with cheaper hosted service.
    # Include local alternatives, but default hosted advice to comparable API rates.
    candidates.sort(key=lambda item: (
        0 if request.get("local_only") or not item["cost_is_local"] else 1,
        item["estimated_cost_usd"],
    ))
    if not candidates:
        result.update(outcome="no_suitable_supported_model", explanation="No supported candidate meets the stated requirements. Review exclusions or adjust the requirements.")
        return result
    result["recommended"] = candidates[0]
    result["alternatives"] = candidates[1:3]
    result["explanation"] = (
        f"Start with {candidates[0]['display_name']} for this {task} task. "
        "It has the lowest estimated API cost in the eligible hosted shortlist"
        if not candidates[0]["cost_is_local"] else
        f"Try {candidates[0]['display_name']} locally; API charges are zero but operation is not free"
    ) + "; suitability is predicted and has not been tested on your prompt."
    if demanding:
        result["limitations"].append("Demanding wording raised the minimum curated tier. This rule needs user validation.")
    baseline_id = request.get("baseline_model_id")
    if baseline_id:
        baseline = resolve_model_info(baseline_id)
        if baseline and (baseline.pricing or baseline.provider == "ollama"):
            baseline_cost = estimate_cost(baseline.id, input_tokens + 64, output_tokens)
            comparable = baseline.provider != "ollama" and not candidates[0]["cost_is_local"]
            result["baseline"] = {
                "model_id": baseline.id, "estimated_cost_usd": baseline_cost,
                "estimated_savings_usd": round(baseline_cost - candidates[0]["estimated_cost_usd"], 6) if comparable else None,
                "pricing_source": baseline.pricing_source, "pricing_checked_at": baseline.pricing_checked_at,
                "note": "Estimated API savings only if the suggested output is acceptable; excludes optional test spend." if comparable else "Local operating cost is unmeasured, so savings are not comparable.",
            }
        else:
            result["limitations"].append("Baseline is unavailable or has unknown pricing; no savings estimate is provided.")
    return result
