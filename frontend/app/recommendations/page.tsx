"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, getAuthToken } from "@/lib/api";
import { AdvancedSettings } from "@/components/AdvancedSettings";
import { formatUsdCost } from "@/lib/cost";
import type { ExperimentSummary, Project, RecommendationResult } from "@/lib/types";

export default function RecommendationsPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
    const [projectId, setProjectId] = useState("");
    const [experimentId, setExperimentId] = useState("");
    const [goal, setGoal] = useState("cheapest");
    const [maxCost, setMaxCost] = useState("");
    const [maxLatency, setMaxLatency] = useState("");
    const [minQuality, setMinQuality] = useState("");
    const [requiresJson, setRequiresJson] = useState(false);
    const [result, setResult] = useState<RecommendationResult | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        setToken(getAuthToken());
    }, []);

    const loadExperiments = useCallback(async (activeToken: string, nextProjectId: string, preferredId?: string) => {
        const data = (await apiFetch(`/api/v1/experiments?project_id=${nextProjectId}`, { token: activeToken })) as ExperimentSummary[];
        const completed = data.filter((item) => item.status === "completed");
        setExperiments(completed);
        setExperimentId(preferredId && completed.some((item) => item.id === preferredId) ? preferredId : completed[0]?.id || "");
    }, []);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        const params = new URLSearchParams(window.location.search);
        const nextProjectId = params.get("project_id") || data[0]?.id || "";
        const nextExperimentId = params.get("experiment_id") || "";
        setProjectId(nextProjectId);
        if (nextProjectId) {
            await loadExperiments(activeToken, nextProjectId, nextExperimentId);
        }
    }, [loadExperiments]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token);
    }, [token, loadProjects]);

    async function recommend() {
        if (!token || !projectId) {
            setMessage("Select a project with a completed experiment.");
            return;
        }
        setLoading(true);
        setMessage(null);
        try {
            const payload = {
                project_id: projectId,
                experiment_id: experimentId || null,
                goal,
                max_cost: maxCost === "" ? null : Number(maxCost),
                max_latency_ms: maxLatency === "" ? null : Number(maxLatency),
                min_quality_score: minQuality === "" ? null : Number(minQuality),
                requires_structured_json: requiresJson,
            };
            const data = (await apiFetch("/api/v1/recommendations/model", {
                token,
                method: "POST",
                body: JSON.stringify(payload),
            })) as RecommendationResult;
            setResult(data);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Recommendation failed");
        } finally {
            setLoading(false);
        }
    }

    const recommendedId = result ? String(result.recommended_config.model_id ?? "") : "";
    const usable = result ? result.recommended_config.usable !== false && Boolean(recommendedId) && recommendedId !== "None" : false;

    return (
        <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <h2 className="text-3xl font-semibold">Recommendations</h2>
                <div className="mt-6 grid gap-4">
                    <label className="grid gap-2 text-sm font-medium">
                        Project
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={projectId} onChange={(event) => {
                            const nextProjectId = event.target.value;
                            setProjectId(nextProjectId);
                            if (token && nextProjectId) {
                                void loadExperiments(token, nextProjectId);
                            }
                        }}>
                            <option value="">Select a project</option>
                            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Experiment
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={experimentId} onChange={(event) => setExperimentId(event.target.value)}>
                            <option value="">Latest completed experiment</option>
                            {experiments.map((experiment) => (
                                <option key={experiment.id} value={experiment.id}>
                                    {experiment.created_at?.slice(0, 19)} · {experiment.model_ids.join(", ")}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        What matters most?
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={goal} onChange={(event) => setGoal(event.target.value)}>
                            <option value="highest_quality">Highest reference-check score</option>
                            <option value="cheapest">Cheapest</option>
                            <option value="fastest">Fastest</option>
                        </select>
                    </label>
                    <AdvancedSettings active={Boolean(maxCost || maxLatency || minQuality || requiresJson)}>
                    <p className="text-sm text-ink/60">Optional requirements exclude results that do not meet them.</p>
                    <label className="grid gap-2 text-sm">Maximum cost per case (USD, optional)<input className="rounded-xl border p-3" type="number" min="0" step="0.000001" value={maxCost} onChange={(event) => setMaxCost(event.target.value)} /></label>
                    <label className="grid gap-2 text-sm">Maximum observed mean latency (ms, optional)<input className="rounded-xl border p-3" type="number" min="0" value={maxLatency} onChange={(event) => setMaxLatency(event.target.value)} /></label>
                    <label className="grid gap-2 text-sm">Minimum reference-check score (0–100, optional)<input className="rounded-xl border p-3" type="number" min="0" max="100" value={minQuality} onChange={(event) => setMinQuality(event.target.value)} /></label>
                    <label className="flex gap-2 text-sm"><input type="checkbox" checked={requiresJson} onChange={(event) => setRequiresJson(event.target.checked)} />Require valid JSON objects for every case</label>
                    </AdvancedSettings>
                    <p className="text-sm text-ink/60">Unscored subjective outputs require your review. Ranking does not establish general quality.</p>
                    <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} onClick={recommend} type="button">
                        {loading ? "Scoring..." : "Recommend model"}
                    </button>
                    {message ? <p className="text-sm text-ink/70">{message}</p> : null}
                    {!experiments.length ? <p className="text-sm text-ink/60">No completed experiments yet.</p> : null}
                </div>
            </div>

            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                {result ? (
                    <div className="grid gap-4">
                        <div className="rounded-2xl bg-sand p-4">
                            <p className="text-sm uppercase tracking-[0.2em] text-ink/50">{String(result.recommended_config.outcome || "Observed comparison").replace(/_/g, " ")}</p>
                            <p className="text-2xl font-semibold">{usable ? recommendedId : "None yet"}</p>
                            <p className="mt-2 text-sm text-ink/70">{result.justification}</p>
                        </div>
                        <div>
                            <p className="font-semibold">Ranked options</p>
                            {result.ranked_options.length ? (
                                <ul className="mt-2 grid gap-2 text-sm">
                                    {result.ranked_options.map((option) => (
                                        <li key={`${String(option.model_id)}-${String(option.prompt_id)}`} className="rounded-2xl border border-black/10 px-4 py-3">
                                            {String(option.model_id)} · score {String(option.overall_score)} · reference check {option.quality_score == null ? "unscored" : String(option.quality_score)} · {formatUsdCost(option.cost_usd == null ? null : Number(option.cost_usd), Boolean(option.cost_is_local))} · {String(option.latency_ms)} ms
                                        </li>
                                    ))}
                                </ul>
                            ) : <p className="mt-2 text-sm text-ink/60">No successful runs to rank.</p>}
                        </div>
                        <div>
                            <p className="font-semibold">Excluded</p>
                            {result.excluded_options.length ? (
                                <ul className="mt-2 grid gap-2 text-sm text-ink/70">
                                    {result.excluded_options.map((option) => (
                                        <li key={`${String(option.model_id)}-${String(option.prompt_id)}`}>
                                            {String(option.model_id)}: {(option.reasons as string[] | undefined)?.join(", ")}
                                        </li>
                                    ))}
                                </ul>
                            ) : <p className="mt-2 text-sm text-ink/60">None excluded.</p>}
                        </div>
                    </div>
                ) : (
                    <p className="text-sm text-ink/60">Run scoring against a completed experiment to see a ranked model card here.</p>
                )}
            </div>
        </section>
    );
}
