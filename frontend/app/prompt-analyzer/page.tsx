"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch, getAuthToken } from "@/lib/api";
import { analysisModeLabel, formatUsdCost } from "@/lib/cost";
import type { PromptAnalysis, Project, ProviderView, SavedPrompt } from "@/lib/types";

const taskTypes = ["summarization", "qa", "sql_generation", "classification", "open_ended"];

export default function PromptAnalyzerPage() {
    const router = useRouter();
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [providers, setProviders] = useState<ProviderView[]>([]);
    const [versions, setVersions] = useState<SavedPrompt[]>([]);
    const [projectId, setProjectId] = useState("");
    const [taskType, setTaskType] = useState("open_ended");
    const [judgeModel, setJudgeModel] = useState("auto");
    const [promptText, setPromptText] = useState("Write a concise summary of the following customer feedback.");
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [analysis, setAnalysis] = useState<PromptAnalysis | null>(null);
    const [sourcePromptId, setSourcePromptId] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const storedToken = getAuthToken();
        setToken(storedToken);
    }, []);

    const availableJudgeModels = useMemo(
        () => providers.filter((provider) => provider.configured).flatMap((provider) => provider.available_models),
        [providers],
    );

    const loadVersions = useCallback(async (activeToken: string, nextProjectId: string) => {
        const data = (await apiFetch(`/api/v1/prompts?project_id=${nextProjectId}`, { token: activeToken })) as SavedPrompt[];
        setVersions(data);
    }, []);

    const loadProviders = useCallback(async (activeToken: string, nextProjectId: string) => {
        const data = (await apiFetch(`/api/v1/projects/${nextProjectId}/providers`, { token: activeToken })) as ProviderView[];
        setProviders(data);
    }, []);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        if (data[0]) {
            setProjectId(data[0].id);
            await Promise.all([
                loadProviders(activeToken, data[0].id),
                loadVersions(activeToken, data[0].id),
            ]);
        }
    }, [loadProviders, loadVersions]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token);
    }, [token, loadProjects]);

    function addFiles(fileList: FileList | null) {
        if (!fileList?.length) {
            return;
        }
        setSelectedFiles((current) => {
            const next = [...current];
            Array.from(fileList).forEach((file) => {
                if (!next.some((item) => item.name === file.name && item.size === file.size)) {
                    next.push(file);
                }
            });
            return next;
        });
    }

    async function handleAnalyze() {
        if (!token || !projectId) {
            setMessage("Create and select a project first.");
            return;
        }
        if (!promptText.trim()) {
            setMessage("Enter a user prompt. Files are attached as context only.");
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
            selectedFiles.forEach((file) => formData.append("files", file));
            if (sourcePromptId) {
                formData.append("source_prompt_id", sourcePromptId);
            }
            const result = (await apiFetch("/api/v1/prompts/analyze", { token, method: "POST", body: formData })) as PromptAnalysis;
            setAnalysis(result);
            setSourcePromptId(result.prompt_id);
            await loadVersions(token, projectId);
            const skipped = Array.isArray(result.analysis_json.skipped_files)
                ? result.analysis_json.skipped_files.filter((item): item is string => typeof item === "string")
                : [];
            const mode = analysisModeLabel(result.analysis_json.analysis_mode);
            setMessage(`Saved prompt version ${result.version} (${mode}).${skipped.length ? ` Skipped: ${skipped.join("; ")}` : ""}`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Analysis failed");
        } finally {
            setLoading(false);
        }
    }

    function sendToExperiment() {
        if (!analysis || !projectId) {
            setMessage("Analyze a prompt before sending it to Experiment Runner.");
            return;
        }
        const params = new URLSearchParams({
            project_id: projectId,
            prompt_id: analysis.prompt_id,
            task_type: taskType,
        });
        router.push(`/experiment-runner?${params.toString()}`);
    }

    const promptTokens = typeof analysis?.analysis_json.prompt_tokens === "number" ? analysis.analysis_json.prompt_tokens : null;
    const contextTokens = typeof analysis?.analysis_json.context_tokens === "number" ? analysis.analysis_json.context_tokens : null;
    const contextFiles = Array.isArray(analysis?.analysis_json.context_files)
        ? analysis.analysis_json.context_files.filter((item): item is string => typeof item === "string")
        : [];

    return (
        <section className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <h2 className="text-3xl font-semibold">Prompt Analyzer</h2>
                <p className="mt-2 text-sm text-ink/70">Score your prompt. Uploaded files and folders are context, not a replacement for the prompt.</p>
                <div className="mt-6 grid gap-4">
                    <label className="grid gap-2 text-sm font-medium">
                        Project
                        <select
                            className="rounded-2xl border border-black/10 px-4 py-3"
                            value={projectId}
                            onChange={(event) => {
                                const nextProjectId = event.target.value;
                                setProjectId(nextProjectId);
                                setAnalysis(null);
                                setSourcePromptId(null);
                                if (token && nextProjectId) {
                                    void loadProviders(token, nextProjectId);
                                    void loadVersions(token, nextProjectId);
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
                    <div className="grid gap-2 text-sm font-medium">
                        Upload file or folder for context
                        <p className="font-normal text-ink/60">Optional. Markdown, text, CSV, JSON, or YAML. Large or binary files are skipped.</p>
                        <input
                            className="rounded-2xl border border-black/10 px-4 py-3"
                            type="file"
                            multiple
                            accept=".md,.markdown,.txt,.csv,.json,.yml,.yaml"
                            onChange={(event) => {
                                addFiles(event.target.files);
                                event.target.value = "";
                            }}
                        />
                        <label className="text-sm font-normal text-ink/70">
                            Or choose a folder
                            <input
                                className="mt-2 block w-full rounded-2xl border border-black/10 px-4 py-3"
                                type="file"
                                multiple
                                // @ts-expect-error non-standard directory picker
                                webkitdirectory=""
                                onChange={(event) => {
                                    addFiles(event.target.files);
                                    event.target.value = "";
                                }}
                            />
                        </label>
                        {selectedFiles.length ? (
                            <ul className="grid gap-1 font-normal text-ink/70">
                                {selectedFiles.map((file) => (
                                    <li key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-3">
                                        <span>{file.name}</span>
                                        <button className="text-xs" onClick={() => setSelectedFiles((current) => current.filter((item) => item !== file))} type="button">
                                            Remove
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        ) : null}
                    </div>
                    <label className="grid gap-2 text-sm font-medium">
                        Judge model
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={judgeModel} onChange={(event) => setJudgeModel(event.target.value)}>
                            <option value="auto">Auto (best configured model)</option>
                            {availableJudgeModels.map((model) => (
                                <option key={model.id} value={model.id}>
                                    {model.display_name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        User prompt
                        <textarea
                            className="min-h-48 rounded-2xl border border-black/10 px-4 py-3"
                            placeholder="Describe the task you want the model to do."
                            value={promptText}
                            onChange={(event) => setPromptText(event.target.value)}
                        />
                    </label>
                    <label className="grid gap-2 text-sm font-medium text-ink/80">
                        Task type
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                            {taskTypes.map((value) => (
                                <option key={value} value={value}>
                                    {value}
                                </option>
                            ))}
                        </select>
                    </label>
                    <div className="flex flex-wrap gap-3">
                        <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} onClick={handleAnalyze} type="button">
                            {loading ? "Analyzing..." : analysis ? "Re-analyze" : "Analyze prompt"}
                        </button>
                        <button className="rounded-full border border-black/15 bg-white px-5 py-3 text-sm font-medium disabled:opacity-60" disabled={!analysis} onClick={sendToExperiment} type="button">
                            Send to Experiment Runner
                        </button>
                    </div>
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
                                <p className="mt-1 text-sm text-ink/60">
                                    v{analysis.version}
                                    {analysis.judge_model ? ` · ${analysis.judge_model}` : ""}
                                    {` · ${analysisModeLabel(analysis.analysis_json.analysis_mode)}`}
                                </p>
                                <p className="mt-2 text-sm text-ink/70">
                                    Analyzed the user prompt{promptTokens != null ? ` (${promptTokens} tokens)` : ""}
                                    {contextTokens ? ` plus ${contextTokens} tokens of uploaded context` : " with no extra document context"}
                                    {contextFiles.length ? ` (${contextFiles.join(", ")})` : ""}.
                                </p>
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
                                    <p className="text-xl font-semibold">{formatUsdCost(analysis.estimated_cost_usd, analysis.cost_is_local || Boolean(analysis.analysis_json.cost_is_local))}</p>
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
                <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                    <h3 className="text-xl font-semibold">Saved versions</h3>
                    {versions.length ? (
                        <ul className="mt-4 grid gap-2">
                            {versions.map((prompt) => (
                                <li key={prompt.id}>
                                    <button
                                        className="w-full rounded-2xl border border-black/10 px-4 py-3 text-left text-sm hover:border-accent"
                                        onClick={() => {
                                            setPromptText(prompt.raw_text.split("--- Context from uploaded files ---")[0].trim());
                                            setTaskType(prompt.task_type);
                                            setSourcePromptId(prompt.id);
                                            setSelectedFiles([]);
                                            setMessage(`Loaded version ${prompt.version} for re-analysis.`);
                                        }}
                                        type="button"
                                    >
                                        v{prompt.version} · score {prompt.quality_score} · {prompt.task_type}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="mt-3 text-sm text-ink/70">Analyzed prompts for this project will appear here.</p>
                    )}
                </div>
            </div>
        </section>
    );
}
