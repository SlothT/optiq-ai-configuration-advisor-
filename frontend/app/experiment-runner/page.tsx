"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AdvancedSettings } from "@/components/AdvancedSettings";
import { ANSWER_LENGTHS } from "@/lib/answer-length";

import { apiFetch, getAuthToken } from "@/lib/api";
import { formatUsdCost } from "@/lib/cost";
import type { ExperimentRow, ExperimentSummary, Project, ProviderView, SavedPrompt } from "@/lib/types";

function parseCsv(text: string) {
    const [headerLine, ...lines] = text.trim().split(/\r?\n/);
    const headers = headerLine.split(",").map((item) => item.trim());
    return lines.filter(Boolean).map((line) => {
        const values = line.split(",");
        const row: Record<string, string> = {};
        headers.forEach((header, index) => {
            row[header] = (values[index] || "").trim();
        });
        return {
            input: row.input || row.prompt || row.text || "",
            reference_answer: row.reference_answer || row.reference || undefined,
            context: row.context || undefined,
        };
    });
}

type TestCase = { input: string; reference_answer?: string; context?: string };

export default function ExperimentRunnerPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [prompts, setPrompts] = useState<SavedPrompt[]>([]);
    const [providers, setProviders] = useState<ProviderView[]>([]);
    const [projectId, setProjectId] = useState("");
    const [selectedPromptIds, setSelectedPromptIds] = useState<string[]>([]);
    const [taskType, setTaskType] = useState("open_ended");
    const [selectedModels, setSelectedModels] = useState<string[]>([]);
    const [testInput, setTestInput] = useState("");
    const [batchCases, setBatchCases] = useState<TestCase[] | null>(null);
    const [temperature, setTemperature] = useState("0.2");
    const [maxOutputTokens, setMaxOutputTokens] = useState(1024);
    const [budget, setBudget] = useState("");
    const [handoffNotice, setHandoffNotice] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [projectLoading, setProjectLoading] = useState(false);
    const activeProject = useRef("");
    const [estimate, setEstimate] = useState<{
        estimated_cost_usd: number;
        estimated_rows: number;
        resolved_model_ids?: string[];
        cost_is_local?: boolean;
    } | null>(null);
    const [experiment, setExperiment] = useState<ExperimentSummary | null>(null);

    useEffect(() => {
        setToken(getAuthToken());
    }, []);

    const availableModels = useMemo(
        () => providers.filter((provider) => provider.configured).flatMap((provider) => provider.available_models),
        [providers],
    );
    const providerMessages = useMemo(
        () => providers.map((provider) => provider.status_message).filter((item): item is string => Boolean(item)),
        [providers],
    );

    const loadPrompts = useCallback(async (activeToken: string, nextProjectId: string, preferredPromptId?: string) => {
        const data = (await apiFetch(`/api/v1/prompts?project_id=${nextProjectId}`, { token: activeToken })) as SavedPrompt[];
        if (activeProject.current !== nextProjectId) return;
        setPrompts(data);
        const selected = preferredPromptId && data.some((prompt) => prompt.id === preferredPromptId)
            ? [preferredPromptId]
            : data[0]
                ? [data[0].id]
                : [];
        setSelectedPromptIds(selected);
        const selectedPrompt = data.find((prompt) => prompt.id === selected[0]);
        if (selectedPrompt) {
            setTaskType(selectedPrompt.task_type);
        }
    }, []);

    const loadProviders = useCallback(async (activeToken: string, nextProjectId: string) => {
        const data = (await apiFetch(`/api/v1/projects/${nextProjectId}/providers`, { token: activeToken })) as ProviderView[];
        if (activeProject.current !== nextProjectId) return;
        setProviders(data);
        const configured = data.filter((provider) => provider.configured).flatMap((provider) => provider.available_models.map((model) => model.id));
        setSelectedModels((current) => {
            if (current.includes("auto")) {
                return ["auto"];
            }
            const stillValid = current.filter((item) => configured.includes(item));
            return stillValid;
        });
    }, []);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        const params = new URLSearchParams(window.location.search);
        const requestedProjectId = data.some((project) => project.id === params.get("project_id"))
            ? params.get("project_id")! : data[0]?.id || "";
        const requestedPromptId = params.get("prompt_id") || "";
        const requestedTaskType = params.get("task_type");
        setProjectId(requestedProjectId);
        activeProject.current = requestedProjectId;
        if (requestedTaskType) {
            setTaskType(requestedTaskType);
        }
        if (requestedPromptId) {
            setHandoffNotice("Loaded the prompt from Model Advisor. Configure the suggested provider before testing; no calls run until confirmation.");
        }
        if (requestedProjectId) {
            setProjectLoading(true);
            try {
                await Promise.all([
                    loadPrompts(activeToken, requestedProjectId, requestedPromptId),
                    loadProviders(activeToken, requestedProjectId),
                ]);
                if (params.get("model_ids")) {
                    setSelectedModels(params.get("model_ids")!.split(",").filter(Boolean));
                }
                const requestedTokens = Number(params.get("max_output_tokens"));
                if (requestedTokens >= 1 && requestedTokens <= 4096) setMaxOutputTokens(requestedTokens);
            } finally {
                setProjectLoading(false);
            }
        }
    }, [loadPrompts, loadProviders]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token).catch((error) => setMessage(error instanceof Error ? error.message : "Could not load projects and models."));
    }, [token, loadProjects]);

    useEffect(() => {
        if (!token || !experiment || ["completed", "failed", "budget_stopped"].includes(experiment.status)) {
            return;
        }
        const timer = window.setInterval(async () => {
            const latest = (await apiFetch(`/api/v1/experiments/${experiment.id}`, { token })) as ExperimentSummary;
            setExperiment(latest);
            if (latest.status === "completed") {
                setMessage("Experiment completed. Review the table, then open Recommendations.");
            }
            if (latest.status === "budget_stopped") {
                setMessage("Stopped dispatching because the remaining budget could not cover another call. Review partial results.");
            }
            if (latest.status === "failed") {
                setMessage(latest.results?.error || "Experiment failed. Check worker logs.");
            }
        }, 2000);
        return () => window.clearInterval(timer);
    }, [token, experiment]);

    useEffect(() => {
        setEstimate(null);
    }, [projectId, selectedPromptIds, selectedModels, testInput, batchCases, maxOutputTokens, temperature]);

    function toggleModel(modelId: string) {
        setMessage(null);
        setSelectedModels((current) => {
            if (modelId === "auto") {
                return current.includes("auto") ? [] : ["auto"];
            }
            const withoutAuto = current.filter((item) => item !== "auto");
            return withoutAuto.includes(modelId)
                ? withoutAuto.filter((item) => item !== modelId)
                : [...withoutAuto, modelId];
        });
    }

    function togglePrompt(promptId: string) {
        setSelectedPromptIds((current) => (
            current.includes(promptId) ? current.filter((item) => item !== promptId) : [...current, promptId]
        ));
    }

    function testInputsPayload() {
        if (batchCases?.length) {
            return batchCases;
        }
        return testInput.trim() ? [{ input: testInput.trim() }] : [];
    }

    async function requestEstimate() {
        if (!token || !projectId) {
            setMessage("Create and select a project first.");
            return;
        }
        if (!selectedPromptIds.length || !selectedModels.length) {
            setMessage("Select at least one prompt and one model, or choose all configured models in Advanced settings.");
            return;
        }
        if (!selectedModels.includes("auto") && selectedModels.some((id) => !availableModels.some((model) => model.id === id))) {
            setMessage("A selected model is not configured for this project. Connect its provider in Settings or select an available model.");
            return;
        }
        setLoading(true);
        setMessage(null);
        try {
            const payload = {
                project_id: projectId,
                prompt_ids: selectedPromptIds,
                model_ids: selectedModels,
                test_inputs: testInputsPayload(),
                max_output_tokens: maxOutputTokens,
            };
            const response = await apiFetch("/api/v1/experiments/estimate", {
                token,
                method: "POST",
                body: JSON.stringify(payload),
            }) as { estimated_cost_usd: number; estimated_rows: number; resolved_model_ids?: string[]; cost_is_local?: boolean };
            setEstimate(response);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Cost estimate failed");
        } finally {
            setLoading(false);
        }
    }

    async function confirmRun() {
        if (!token || !projectId || !estimate) {
            return;
        }
        setLoading(true);
        try {
            const response = await apiFetch("/api/v1/experiments/run", {
                token,
                method: "POST",
                body: JSON.stringify({
                    project_id: projectId,
                    prompt_ids: selectedPromptIds,
                    model_ids: estimate.resolved_model_ids || selectedModels,
                    task_type: taskType,
                    test_inputs: testInputsPayload(),
                    max_output_tokens: maxOutputTokens,
                    confirm_cost: true,
                    budget_usd: budget === "" ? estimate.estimated_cost_usd : Number(budget),
                    temperature: temperature.trim() === "" ? 0.2 : Number(temperature),
                }),
            }) as ExperimentSummary;
            setExperiment(response);
            setEstimate(null);
            setMessage(`Queued experiment ${response.id}. Status: ${response.status}.`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Experiment run failed");
        } finally {
            setLoading(false);
        }
    }

    async function markOutput(rowIndex: number, accepted: boolean) {
        if (!token || !experiment) return;
        try {
            const updated = await apiFetch(`/api/v1/experiments/${experiment.id}/feedback`, {
                token, method: "POST", body: JSON.stringify({ row_index: rowIndex, accepted }),
            }) as ExperimentSummary;
            setExperiment(updated);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Could not save feedback");
        }
    }

    async function onUpload(file: File) {
        const text = await file.text();
        if (file.name.endsWith(".csv")) {
            setBatchCases(parseCsv(text));
            return;
        }
        const payload = JSON.parse(text);
        const rows = Array.isArray(payload) ? payload : [payload];
        setBatchCases(rows.map((row: Record<string, string> | string) => (
            typeof row === "string"
                ? { input: row }
                : { input: row.input || row.prompt || row.text || "", reference_answer: row.reference_answer, context: row.context }
        )));
    }

    const rows: ExperimentRow[] = experiment?.results?.rows || [];
    const selectedPrompt = prompts.find((prompt) => prompt.id === selectedPromptIds[0]);

    return (
        <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
            <h2 className="text-3xl font-semibold">Experiment Runner</h2>
            {handoffNotice ? <p className="mt-3 rounded-2xl bg-sand px-4 py-3 text-sm text-ink/80">{handoffNotice}</p> : null}

            <div className="mt-6 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
                <fieldset className="grid min-w-0 gap-4" disabled={loading || projectLoading}>
                    <label className="grid gap-2 text-sm font-medium">
                        Project
                        <select
                            className="rounded-2xl border border-black/10 px-4 py-3"
                            value={projectId}
                            disabled={projectLoading}
                            onChange={async (event) => {
                                const nextProjectId = event.target.value;
                                activeProject.current = nextProjectId;
                                setProjectId(nextProjectId);
                                setHandoffNotice(null);
                                setProviders([]);
                                setPrompts([]);
                                setSelectedModels([]);
                                setSelectedPromptIds([]);
                                setExperiment(null);
                                setEstimate(null);
                                setMessage(null);
                                if (token && nextProjectId) {
                                    setProjectLoading(true);
                                    try {
                                        await Promise.all([loadPrompts(token, nextProjectId), loadProviders(token, nextProjectId)]);
                                    } catch (error) {
                                        setMessage(error instanceof Error ? error.message : "Could not load this project's prompts and models.");
                                    } finally {
                                        setProjectLoading(false);
                                    }
                                }
                            }}
                        >
                            <option value="">Select a project</option>
                            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                        </select>
                    </label>

                    <div>
                        <p className="mb-2 text-sm font-medium">Saved prompts</p>
                        <div className="grid gap-2">
                            {prompts.map((prompt) => (
                                <button
                                    key={prompt.id}
                                    type="button"
                                    onClick={() => {
                                        togglePrompt(prompt.id);
                                        setTaskType(prompt.task_type);
                                    }}
                                    className={`rounded-2xl border px-4 py-3 text-left text-sm ${selectedPromptIds.includes(prompt.id) ? "border-accent bg-accent/5" : "border-black/10"}`}
                                >
                                    v{prompt.version} · {prompt.task_type}
                                </button>
                            ))}
                            {!prompts.length ? <p className="text-sm text-ink/60">Analyze a prompt first, then send it here.</p> : null}
                        </div>
                    </div>

                    {selectedPrompt ? (
                        <div className="rounded-2xl border border-black/10 px-4 py-3 text-sm text-ink/70">
                            <p className="mb-1 font-medium text-ink">Analyzed prompt</p>
                            {selectedPrompt.raw_text.slice(0, 240)}
                            {selectedPrompt.raw_text.length > 240 ? "…" : ""}
                        </div>
                    ) : null}

                    <div>
                        <p className="mb-2 text-sm font-medium">Available models</p>
                        <p className="mb-2 text-sm text-ink/60">Choose one or more models connected to this project. Review the cost before running the comparison.</p>
                        <div className="grid gap-2">
                            {selectedModels.includes("auto") ? <p className="text-sm text-ink/70">Comparing up to 8 configured models. The cost estimate lists the exact models. <button type="button" className="underline" onClick={() => setSelectedModels([])}>Choose individual models</button></p> : null}
                            {!selectedModels.includes("auto") ? <fieldset className="grid gap-2 rounded-2xl border border-black/10 p-3 text-sm" disabled={projectLoading || loading}>
                                <legend className="px-1">Models to compare</legend>
                                {availableModels.map((model) => (
                                    <label key={model.id} className="flex items-center gap-2">
                                        <input type="checkbox" checked={selectedModels.includes(model.id)} onChange={() => toggleModel(model.id)} />
                                        {model.display_name}
                                    </label>
                                ))}
                            </fieldset> : null}
                            {projectLoading ? <p role="status" className="text-sm text-ink/60">Loading models for this project…</p> : null}
                            {!projectLoading && !availableModels.length ? (
                                <p className="text-sm text-ink/60">No models listed yet. Save a provider in Settings, and for Ollama pull at least one model.</p>
                            ) : null}
                            {selectedModels.filter((id) => id !== "auto" && !availableModels.some((model) => model.id === id)).map((id) => <p key={id} className="text-sm text-red-700">{id} is selected but not configured. Connect its provider in Settings or <button type="button" className="underline" onClick={() => toggleModel(id)}>remove this selection</button>.</p>)}
                            {providerMessages.map((item) => <p key={item} className="text-sm text-red-700">{item}</p>)}
                        </div>
                    </div>

                    <label className="grid gap-2 text-sm font-medium">
                        Answer length
                        <select className="rounded-2xl border border-black/10 px-4 py-3" value={Object.values(ANSWER_LENGTHS).includes(maxOutputTokens) ? String(maxOutputTokens) : "custom"} onChange={(event) => { if (event.target.value !== "custom") setMaxOutputTokens(Number(event.target.value)); }}>
                            {Object.entries(ANSWER_LENGTHS).map(([name, limit]) => <option key={name} value={limit}>{name[0].toUpperCase() + name.slice(1)}</option>)}
                            {!Object.values(ANSWER_LENGTHS).includes(maxOutputTokens) ? <option value="custom">Custom · {maxOutputTokens} tokens</option> : null}
                        </select>
                        <span className="font-normal text-ink/60">Limit per answer: {maxOutputTokens} tokens. Exact limits are available in Advanced settings.</span>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Additional test input (optional)
                        <span className="font-normal text-ink/60">This is extra test input sent with the analyzed prompt, not a replacement for it.</span>
                        <textarea
                            className="min-h-32 rounded-2xl border border-black/10 px-4 py-3"
                            placeholder="Leave empty to test the saved prompt exactly as written."
                            value={testInput}
                            onChange={(event) => {
                                setTestInput(event.target.value);
                                setBatchCases(null);
                            }}
                            disabled={Boolean(batchCases?.length)}
                        />
                    </label>
                    <AdvancedSettings active={temperature !== "0.2" || maxOutputTokens !== 1024 || Boolean(batchCases?.length) || selectedModels.includes("auto")}>
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" disabled={projectLoading || loading || !availableModels.length} checked={selectedModels.includes("auto")} onChange={() => toggleModel("auto")} />Compare all configured models (up to 8)
                    </label>
                    <p className="text-sm text-ink/60">More models and test cases increase the number of calls. Review the complete estimate before confirming.</p>
                    <label className="grid gap-2 text-sm font-medium">Response variation (temperature)
                        <input className="rounded-xl border p-3" type="number" min="0" max="1" step="0.1" value={temperature} onChange={(event) => setTemperature(event.target.value)} />
                        <span className="font-normal text-ink/60">Default 0.2. Higher values produce more varied answers.</span>
                    </label>
                    <label className="grid gap-2 text-sm font-medium">Exact maximum output tokens per answer
                        <input className="rounded-xl border p-3" type="number" min="1" max="4096" value={maxOutputTokens} onChange={(event) => setMaxOutputTokens(Number(event.target.value))} />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                        Or upload a CSV / JSON batch of test cases
                        <input className="rounded-2xl border border-black/10 px-4 py-3" type="file" accept=".json,.csv" onChange={(event) => event.target.files?.[0] && void onUpload(event.target.files[0])} />
                        {batchCases?.length ? (
                            <span className="font-normal text-ink/60">
                                {batchCases.length} test case(s) loaded from file.
                                {" "}
                                <button className="underline" type="button" onClick={() => setBatchCases(null)}>Clear batch</button>
                            </span>
                        ) : null}
                    </label>
                    </AdvancedSettings>
                    {batchCases?.length ? <p className="text-sm text-ink/70">Testing {batchCases.length} uploaded cases. <button className="underline" type="button" onClick={() => setBatchCases(null)}>Clear batch</button></p> : null}
                    <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading || projectLoading} onClick={requestEstimate} type="button">
                        {loading ? "Working..." : "Estimate cost"}
                    </button>
                    {message ? <p className="text-sm text-ink/70">{message}</p> : null}
                </fieldset>

                <div>
                    {experiment ? (
                        <div className="grid gap-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <p className="text-sm uppercase tracking-[0.2em] text-ink/50">Status</p>
                                    <p className="text-2xl font-semibold capitalize">{experiment.status}</p>
                                    <p className="text-sm text-ink/60">{experiment.model_ids.join(", ")}</p>
                                </div>
                                {experiment.status === "completed" ? (
                                    <Link className="rounded-full bg-accent px-5 py-3 text-sm font-medium text-white" href={`/recommendations?project_id=${projectId}&experiment_id=${experiment.id}`}>
                                        Get recommendation
                                    </Link>
                                ) : null}
                            </div>
                            <div className="overflow-x-auto rounded-2xl border border-black/10">
                                <table className="min-w-full text-left text-sm">
                                    <thead className="bg-sand">
                                        <tr>
                                            {["Model", "Prompt", "Latency", "Cost", "Tokens", "Quality", "Accuracy", "Error"].map((header) => (
                                                <th key={header} className="px-3 py-2 font-medium">{header}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {rows.map((row, index) => (
                                            <tr key={`${row.model_id}-${row.prompt_id}-${index}`} className="border-t border-black/5">
                                                <td className="px-3 py-2">{row.model_id}</td>
                                                <td className="px-3 py-2">v{row.prompt_version ?? "?"}</td>
                                                <td className="px-3 py-2">{row.latency_ms}</td>
                                                <td className="px-3 py-2">{formatUsdCost(row.cost_usd, row.cost_is_local || row.provider === "ollama")}</td>
                                                <td className="px-3 py-2">{row.input_tokens + row.output_tokens}</td>
                                                <td className="px-3 py-2">{row.quality_score ?? "—"}</td>
                                                <td className="px-3 py-2">{row.accuracy ?? "—"}</td>
                                                <td className="px-3 py-2 text-red-700">{row.error || ""}</td>
                                            </tr>
                                        ))}
                                        {!rows.length ? (
                                            <tr><td className="px-3 py-4 text-ink/60" colSpan={8}>Waiting for worker results…</td></tr>
                                        ) : null}
                                    </tbody>
                                </table>
                            </div>
                            <p className="text-sm text-ink/60">Subjective outputs need your review. A single test is not a reliability guarantee. Unknown failed-call charges remain reserved.</p>
                            {rows.map((row, index) => <div key={`output-${index}`} className="rounded-2xl border border-black/10 p-4">
                                <h3 className="font-semibold">{row.model_id} · case {row.input_index + 1}</h3>
                                <pre className="mt-3 max-h-80 whitespace-pre-wrap overflow-auto text-sm">{row.raw_output || row.error || "No output"}</pre>
                                {!row.error && ["completed", "budget_stopped", "failed"].includes(experiment.status) ? <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                                    <button className="rounded-full border px-3 py-2" type="button" onClick={() => void markOutput(index, true)}>Meets my need</button>
                                    <button className="rounded-full border px-3 py-2" type="button" onClick={() => void markOutput(index, false)}>Does not meet my need</button>
                                    {experiment.results?.user_feedback?.[String(index)] ? <span>{experiment.results.user_feedback[String(index)].accepted ? "Accepted" : "Rejected"} for this output only</span> : null}
                                </div> : null}
                            </div>)}
                        </div>
                    ) : (
                        <p className="text-sm text-ink/60">Estimate cost, confirm the modal, then this panel will poll until the experiment finishes.</p>
                    )}
                </div>
            </div>

            {estimate ? (
                <div className="fixed inset-0 z-20 flex items-center justify-center bg-ink/40 p-4">
                    <div className="w-full max-w-md rounded-[2rem] bg-white p-6 shadow-panel">
                        <h3 className="text-xl font-semibold">Confirm experiment cost</h3>
                        <p className="mt-3 text-sm text-ink/70">
                            Estimated {formatUsdCost(estimate.estimated_cost_usd, estimate.cost_is_local)} across {estimate.estimated_rows} generation(s)
                            {estimate.resolved_model_ids ? ` using ${estimate.resolved_model_ids.join(", ")}` : ""}.
                        </p>
                        <p className="mt-2 text-sm text-ink/60">Maximum output tokens: {maxOutputTokens}. No automatic retries or paid judges. This controls dispatch; provider billing can differ.</p>
                        <label className="mt-4 grid gap-2 text-sm">Experiment budget (USD)
                            <input className="rounded-xl border p-3" type="number" min="0" step="0.000001" placeholder={String(estimate.estimated_cost_usd)} value={budget} onChange={(event) => setBudget(event.target.value)} />
                            <span className="text-ink/60">Leave empty to use the displayed reservation. Each experiment has its own budget.</span>
                        </label>
                        <div className="mt-6 flex gap-3">
                            <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper" onClick={confirmRun} type="button">Confirm and queue</button>
                            <button className="rounded-full border border-black/15 px-5 py-3 text-sm" onClick={() => setEstimate(null)} type="button">Cancel</button>
                        </div>
                    </div>
                </div>
            ) : null}
        </section>
    );
}
