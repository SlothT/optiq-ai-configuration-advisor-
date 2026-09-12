"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { apiFetch, getAuthToken } from "@/lib/api";
import type { ExperimentSummary, Project } from "@/lib/types";

const MLFLOW_UI = process.env.NEXT_PUBLIC_MLFLOW_URL ?? "http://localhost:5000";

function metric(experiment: ExperimentSummary, key: string) {
    const value = experiment.results?.summary?.[key];
    return typeof value === "number" ? value : 0;
}

export default function DashboardPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [projectId, setProjectId] = useState("");
    const [tag, setTag] = useState("");
    const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
    const [selected, setSelected] = useState<string[]>([]);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        setToken(getAuthToken());
    }, []);

    const loadExperiments = useCallback(async (activeToken: string, nextProjectId: string, nextTag?: string) => {
        const query = new URLSearchParams({ project_id: nextProjectId, limit: "50" });
        if (nextTag) {
            query.set("tag", nextTag);
        }
        const data = (await apiFetch(`/api/v1/experiments?${query.toString()}`, { token: activeToken })) as ExperimentSummary[];
        setExperiments(data);
    }, []);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        const params = new URLSearchParams(window.location.search);
        const nextProjectId = params.get("project_id") || data[0]?.id || "";
        setProjectId(nextProjectId);
        if (nextProjectId) {
            await loadExperiments(activeToken, nextProjectId);
        }
    }, [loadExperiments]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token).catch((error: unknown) => {
            setMessage(error instanceof Error ? error.message : "Failed to load dashboard");
        });
    }, [token, loadProjects]);

    function toggle(id: string) {
        setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(-4)));
    }

    const compared = useMemo(
        () => experiments.filter((item) => selected.includes(item.id)),
        [experiments, selected],
    );

    return (
        <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
            <h2 className="text-3xl font-semibold">Dashboard</h2>
            <p className="mt-3 text-sm text-ink/70">Browse experiment history, compare metrics, and open the native MLflow UI.</p>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
                <select
                    className="rounded-2xl border border-black/10 px-4 py-3"
                    value={projectId}
                    onChange={(event) => {
                        const nextProjectId = event.target.value;
                        setProjectId(nextProjectId);
                        if (token && nextProjectId) {
                            void loadExperiments(token, nextProjectId, tag);
                        }
                    }}
                >
                    <option value="">Select a project</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
                <input className="rounded-2xl border border-black/10 px-4 py-3" placeholder="Filter by label or task type" value={tag} onChange={(event) => setTag(event.target.value)} />
                <button
                    className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper"
                    type="button"
                    onClick={() => token && projectId && void loadExperiments(token, projectId, tag)}
                >
                    Apply filter
                </button>
            </div>
            {message ? <p className="mt-3 text-sm text-ink/70">{message}</p> : null}

            <div className="mt-6 overflow-x-auto rounded-2xl border border-black/10">
                <table className="min-w-full text-left text-sm">
                    <thead className="bg-sand">
                        <tr>
                            {["Compare", "Date", "Task", "Models", "Status", "Quality", "MLflow", "Recommend"].map((header) => (
                                <th key={header} className="px-3 py-2 font-medium">{header}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {experiments.map((experiment) => (
                            <tr key={experiment.id} className="border-t border-black/5">
                                <td className="px-3 py-2">
                                    <input type="checkbox" checked={selected.includes(experiment.id)} onChange={() => toggle(experiment.id)} />
                                </td>
                                <td className="px-3 py-2">{experiment.created_at?.slice(0, 19).replace("T", " ") || "—"}</td>
                                <td className="px-3 py-2">{experiment.task_type}</td>
                                <td className="px-3 py-2">{experiment.model_ids.join(", ")}</td>
                                <td className="px-3 py-2 capitalize">{experiment.status}</td>
                                <td className="px-3 py-2">{metric(experiment, "quality_score") || "—"}</td>
                                <td className="px-3 py-2">
                                    {experiment.mlflow_run_id ? (
                                        <a className="text-accent" href={`${MLFLOW_UI}/#/experiments`} target="_blank" rel="noreferrer">Open</a>
                                    ) : "—"}
                                </td>
                                <td className="px-3 py-2">
                                    <Link className="text-accent" href={`/recommendations?project_id=${projectId}&experiment_id=${experiment.id}`}>Use</Link>
                                </td>
                            </tr>
                        ))}
                        {!experiments.length ? (
                            <tr><td className="px-3 py-4 text-ink/60" colSpan={8}>No experiments yet. Run one from Experiment Runner.</td></tr>
                        ) : null}
                    </tbody>
                </table>
            </div>

            {compared.length >= 2 ? (
                <div className="mt-8 grid gap-4">
                    <h3 className="text-xl font-semibold">Comparison</h3>
                    {["quality_score", "total_cost_usd", "latency_p50_ms"].map((key) => {
                        const max = Math.max(...compared.map((item) => metric(item, key)), 0.000001);
                        return (
                            <div key={key}>
                                <p className="mb-2 text-sm font-medium capitalize">{key.replaceAll("_", " ")}</p>
                                <div className="grid gap-2">
                                    {compared.map((item) => (
                                        <div key={`${item.id}-${key}`} className="grid grid-cols-[8rem_1fr_4rem] items-center gap-3 text-sm">
                                            <span className="truncate">{item.model_ids[0]}</span>
                                            <div className="h-3 rounded-full bg-sand">
                                                <div className="h-3 rounded-full bg-accent" style={{ width: `${(metric(item, key) / max) * 100}%` }} />
                                            </div>
                                            <span>{metric(item, key)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <p className="mt-6 text-sm text-ink/60">Select two or more experiments to compare quality, cost, and latency.</p>
            )}
        </section>
    );
}
