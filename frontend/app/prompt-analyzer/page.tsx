"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, getAuthToken } from "@/lib/api";
import type { PromptAnalysis, Project, ProviderView } from "@/lib/types";

const taskTypes = ["summarization", "qa", "sql_generation", "classification", "open_ended"];

export default function PromptAnalyzerPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [providers, setProviders] = useState<ProviderView[]>([]);
    const [projectId, setProjectId] = useState("");
    const [taskType, setTaskType] = useState("open_ended");
    const [judgeModel, setJudgeModel] = useState("gpt-4o-mini");
    const [promptText, setPromptText] = useState("Write a concise summary of the following customer feedback.");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [analysis, setAnalysis] = useState<PromptAnalysis | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const storedToken = getAuthToken();
        setToken(storedToken);
    }, []);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    const loadProviders = useCallback(async (activeToken: string, nextProjectId: string) => {
        const data = (await apiFetch(`/api/v1/projects/${nextProjectId}/providers`, { token: activeToken })) as ProviderView[];
        setProviders(data);
        const configuredModels = data.flatMap((provider) => provider.available_models.map((model) => model.id));
        if (configuredModels.length > 0) {
            setJudgeModel(configuredModels[0]);
        }
    }, []);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        if (data[0]) {
            setProjectId(data[0].id);
            await loadProviders(activeToken, data[0].id);
        }
    }, [loadProviders]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token);
    }, [token, loadProjects]);

    async function handleAnalyze() {
        if (!token || !projectId) {
            setMessage("Create and select a project first.");
            return;
        }
        setLoading(true);
        setMessage(null);
        try {
            const formData = new FormData();
            formData.append("project_id", projectId);
            formData.append("task_type", taskType);
            formData.append("judge_model", judgeModel);
            formData.append("text", promptText);
            if (selectedFile) {
                formData.append("file", selectedFile);
            }
            const result = (await apiFetch("/api/v1/prompts/analyze", { token, method: "POST", body: formData })) as PromptAnalysis;
            setAnalysis(result);
            setMessage(`Saved prompt version ${result.version}.`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Analysis failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <p className="text-sm uppercase tracking-[0.24em] text-accent">Screen 1</p>
                <h2 className="mt-2 text-3xl font-semibold">Prompt Analyzer</h2>
                <div className="mt-6 grid gap-4">
                    <label className="grid gap-2 text-sm font-medium">
                        Project
                        <select
                            className="rounded-2xl border border-black/10 px-4 py-3"
                            value={projectId}
                            onChange={(event) => {
                                const nextProjectId = event.target.value;
                                setProjectId(nextProjectId);
                                if (token && nextProjectId) {
                                    void loadProviders(token, nextProjectId);
                                }
                            }}
                        >
                            <option value="">Select a project</option>
                            {projects.map((project) => (
                                <option key={project.id} value={project.id}>
                                    {project.name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Task type
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                            {taskTypes.map((value) => (
                                <option key={value} value={value}>
                                    {value}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Judge model
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={judgeModel} onChange={(event) => setJudgeModel(event.target.value)}>
                            {providers.flatMap((provider) => provider.available_models).map((model) => (
                                <option key={model.id} value={model.id}>
                                    {model.display_name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Prompt text
                        <textarea className="min-h-48 rounded-2xl border border-black/10 px-4 py-3" value={promptText} onChange={(event) => setPromptText(event.target.value)} />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Upload MD / CSV / JSON
                        <input className="rounded-2xl border border-black/10 px-4 py-3" type="file" accept=".md,.markdown,.csv,.json" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
                    </label>
                    <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} onClick={handleAnalyze} type="button">
                        {loading ? "Analyzing..." : analysis ? "Re-analyze" : "Analyze prompt"}
                    </button>
                    {message ? <p className="text-sm text-ink/70">{message}</p> : null}
                </div>
            </div>

            <div className="grid gap-4">
                <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                    <h3 className="text-2xl font-semibold">Results</h3>
                    {analysis ? (
                        <div className="mt-5 grid gap-4">
                            <div className="rounded-2xl bg-sand p-4">
                                <p className="text-sm uppercase tracking-[0.2em] text-ink/60">Quality score</p>
                                <p className="text-4xl font-semibold">{analysis.quality_score}</p>
                            </div>
                            <div>
                                <p className="text-sm font-semibold">Strengths</p>
                                <ul className="mt-2 list-disc pl-5 text-sm text-ink/70">
                                    {analysis.strengths.map((item) => <li key={item}>{item}</li>)}
                                </ul>
                            </div>
                            <div>
                                <p className="text-sm font-semibold">Weaknesses</p>
                                <ul className="mt-2 list-disc pl-5 text-sm text-ink/70">
                                    {analysis.weaknesses.map((item) => <li key={item}>{item}</li>)}
                                </ul>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div className="rounded-2xl border border-black/10 p-4">
                                    <p className="text-ink/60">Tokens</p>
                                    <p className="text-xl font-semibold">{analysis.estimated_tokens}</p>
                                </div>
                                <div className="rounded-2xl border border-black/10 p-4">
                                    <p className="text-ink/60">Estimated cost</p>
                                    <p className="text-xl font-semibold">${analysis.estimated_cost_usd.toFixed(4)}</p>
                                </div>
                            </div>
                            <div>
                                <p className="text-sm font-semibold">Suggestions</p>
                                <ul className="mt-2 list-disc pl-5 text-sm text-ink/70">
                                    {analysis.suggested_improvements.map((item) => <li key={item}>{item}</li>)}
                                </ul>
                            </div>
                        </div>
                    ) : (
                        <p className="mt-4 text-sm text-ink/70">Run an analysis to see prompt quality feedback here.</p>
                    )}
                </div>
            </div>
        </section>
    );
}
