"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiFetch, getAuthToken } from "@/lib/api";
import { formatUsdCost } from "@/lib/cost";
import type { ModelAdvice, AdviceOption, Project, PromptAnalysis } from "@/lib/types";

export default function ModelAdvisorPage() {
    const router = useRouter();
    const [prompt, setPrompt] = useState("Write an 800-word introductory essay about remote work for a general audience.");
    const [preference, setPreference] = useState("cost");
    const [outputTokens, setOutputTokens] = useState(1200);
    const [baseline, setBaseline] = useState("");
    const [provider, setProvider] = useState("");
    const [localOnly, setLocalOnly] = useState(false);
    const [maxCost, setMaxCost] = useState("");
    const [models, setModels] = useState<Array<{ id: string; display_name: string }>>([]);
    const [projects, setProjects] = useState<Project[]>([]);
    const [projectId, setProjectId] = useState("");
    const [result, setResult] = useState<ModelAdvice | null>(null);
    const [submittedPrompt, setSubmittedPrompt] = useState("");
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        void apiFetch("/api/v1/models").then((data) => setModels(data.models)).catch(() => setMessage("Could not load the model list. Check API connectivity."));
        const token = getAuthToken();
        if (token) {
            void apiFetch("/api/v1/projects", { token }).then((data: Project[]) => {
                setProjects(data);
                setProjectId(data[0]?.id || "");
            }).catch(() => setMessage("Sign in again to save prompts and run optional tests."));
        }
    }, []);

    async function getAdvice() {
        setLoading(true);
        setMessage(null);
        setResult(null);
        try {
            const data = await apiFetch("/api/v1/advice", {
                method: "POST",
                body: JSON.stringify({
                    prompt, preference, expected_output_tokens: outputTokens,
                    baseline_model_id: baseline || null,
                    allowed_providers: provider ? [provider] : [], local_only: localOnly,
                    max_cost_usd: maxCost === "" ? null : Number(maxCost),
                }),
            }) as ModelAdvice;
            setResult(data);
            setSubmittedPrompt(prompt);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Advice failed");
        } finally {
            setLoading(false);
        }
    }

    async function prepareTest() {
        const token = getAuthToken();
        if (!token || !projectId || !result?.recommended) {
            setMessage("Sign in and select a project to save this prompt for optional testing. Advice needs no account or keys.");
            return;
        }
        setLoading(true);
        try {
            const data = new FormData();
            data.append("project_id", projectId);
            data.append("text", submittedPrompt);
            data.append("task_type", result.task_type);
            data.append("judge_model", "local");
            const saved = await apiFetch("/api/v1/prompts/analyze", { token, method: "POST", body: data }) as PromptAnalysis;
            const selected = [result.recommended.model_id];
            if (result.baseline && result.baseline.model_id !== selected[0]) selected.push(result.baseline.model_id);
            router.push(`/experiment-runner?${new URLSearchParams({
                project_id: projectId, prompt_id: saved.prompt_id, task_type: result.task_type,
                model_ids: selected.join(","), max_output_tokens: String(result.expected_output_tokens),
            }).toString()}`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Could not prepare comparison");
        } finally {
            setLoading(false);
        }
    }

    async function copyConfig(option: AdviceOption) {
        try {
            await navigator.clipboard.writeText(JSON.stringify({
                prompt: submittedPrompt, provider: option.provider, model: option.model_id,
                temperature: option.temperature, max_output_tokens: option.max_output_tokens,
            }, null, 2));
            setMessage("Copied the prompt and model settings.");
        } catch {
            setMessage("Clipboard is unavailable. Copy the model identifier and settings from the card.");
        }
    }

    return (
        <section className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <h2 className="text-3xl font-semibold">Model Advisor</h2>
                <p className="mt-2 text-sm text-ink/70">Find an affordable starting model for your prompt. Advice runs locally with no paid model calls, API keys, or dataset.</p>
                <div className="mt-6 grid gap-4">
                    <label className="grid gap-2 text-sm font-medium">Your prompt
                        <textarea className="min-h-48 rounded-2xl border border-black/10 p-4" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">Preference
                        <select className="rounded-2xl border border-black/10 p-3" value={preference} onChange={(event) => setPreference(event.target.value)}>
                            <option value="cost">Lower cost</option><option value="quality">More demanding quality</option>
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">Expected output tokens
                        <input className="rounded-2xl border border-black/10 p-3" type="number" min="1" max="4096" value={outputTokens} onChange={(event) => setOutputTokens(Number(event.target.value))} />
                        <span className="font-normal text-ink/60">An estimate and optional test limit. Words and tokens are different.</span>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">Compare cost with (optional)
                        <select className="rounded-2xl border border-black/10 p-3" value={baseline} onChange={(event) => setBaseline(event.target.value)}>
                            <option value="">No baseline</option>{models.map((model) => <option key={model.id} value={model.id}>{model.display_name}</option>)}
                        </select>
                    </label>
                    <details className="rounded-2xl border border-black/10 p-4">
                        <summary className="cursor-pointer text-sm font-medium">Provider and cost requirements</summary>
                        <div className="mt-3 grid gap-3 text-sm">
                            <label className="grid gap-2">Provider
                                <select className="rounded-xl border p-2" value={provider} onChange={(event) => setProvider(event.target.value)}>
                                    <option value="">Any supported provider</option>{["openai", "anthropic", "google", "ollama"].map((name) => <option key={name}>{name}</option>)}
                                </select>
                            </label>
                            <label className="flex gap-2"><input type="checkbox" checked={localOnly} onChange={(event) => setLocalOnly(event.target.checked)} />Local inference only</label>
                            <label className="grid gap-2">Maximum API cost per request (USD, optional)
                                <input className="rounded-xl border p-2" type="number" min="0" step="0.0001" value={maxCost} onChange={(event) => setMaxCost(event.target.value)} />
                            </label>
                        </div>
                    </details>
                    <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading || !prompt.trim()} onClick={getAdvice} type="button">{loading ? "Working..." : "Suggest a model"}</button>
                    {message ? <p role="status" className="text-sm text-ink/70">{message}</p> : null}
                </div>
            </div>
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                {result ? <div className="grid gap-4">
                    <h3 className="text-xl font-semibold">{result.recommended ? "Suggested starting model · untested" : result.outcome === "no_suitable_supported_model" ? "No suitable supported model" : "More information needed"}</h3>
                    <p className="text-sm text-ink/70">{result.explanation}</p>
                    {[result.recommended, ...result.alternatives].filter((option): option is AdviceOption => option !== null).map((option, index) => <div key={option.model_id} className={`rounded-2xl border p-4 ${index === 0 ? "border-accent bg-sand" : "border-black/10"}`}>
                        <h4 className="font-semibold">{option.display_name}</h4>
                        <p className="mt-1 text-sm">{option.model_id} · {formatUsdCost(option.estimated_cost_usd, option.cost_is_local)} / request</p>
                        <p className="mt-2 text-sm text-ink/70">{option.reason}</p>
                        <p className="mt-1 text-sm text-ink/60">{option.limitation}</p>
                        {option.pricing_source ? <a className="mt-2 block text-xs underline" href={option.pricing_source} target="_blank" rel="noreferrer">Pricing source · checked {option.pricing_checked_at}</a> : null}
                        <p className="mt-2 text-xs text-ink/60">Temperature {option.temperature} · output limit {option.max_output_tokens}</p>
                        <button className="mt-3 rounded-full border border-black/15 px-4 py-2 text-sm" type="button" onClick={() => void copyConfig(option)}>Copy prompt and settings</button>
                    </div>)}
                    {result.baseline ? <div className="rounded-2xl border border-black/10 p-4 text-sm">
                        <p>Baseline {result.baseline.model_id}: {formatUsdCost(result.baseline.estimated_cost_usd)} / request</p>
                        {result.baseline.estimated_savings_usd !== null ? <p className="mt-1">Estimated difference: {formatUsdCost(result.baseline.estimated_savings_usd)} / request</p> : null}
                        <p className="mt-2 text-ink/60">{result.baseline.note}</p>
                    </div> : null}
                    <ul className="list-disc space-y-2 pl-5 text-sm text-ink/60">{[...result.assumptions, ...result.limitations].map((item) => <li key={item}>{item}</li>)}</ul>
                    {result.recommended ? <div className="mt-2 grid gap-3 border-t pt-4">
                        <h4 className="font-semibold">Optional comparison</h4>
                        <p className="text-sm text-ink/60">Testing can cost more than it saves for a one-off task. Sign in and configure providers to compare outputs; review the estimate before execution.</p>
                        {projects.length ? <label className="grid gap-2 text-sm">Save in project
                            <select className="rounded-xl border p-3" value={projectId} onChange={(event) => setProjectId(event.target.value)}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
                        </label> : <Link href="/settings" className="text-sm underline">Sign in and create a project in Settings</Link>}
                        <button className="rounded-full border border-black/15 px-5 py-3 text-sm disabled:opacity-60" type="button" disabled={loading || !projectId} onClick={prepareTest}>Prepare optional test</button>
                    </div> : null}
                    {result.excluded.length ? <details className="text-sm"><summary className="cursor-pointer">Excluded candidates</summary><ul className="mt-2 space-y-2">{result.excluded.map((item) => <li key={item.model_id}>{item.model_id}: {item.reasons.join("; ")}</li>)}</ul></details> : null}
                </div> : <p className="text-sm text-ink/60">Paste a prompt to see model advice and estimated costs. Nothing is sent to model providers for advice.</p>}
            </div>
        </section>
    );
}
