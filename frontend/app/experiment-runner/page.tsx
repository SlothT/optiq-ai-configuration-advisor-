"use client";

import { useEffect, useState } from "react";

import { apiFetch, getAuthToken } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function ExperimentRunnerPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [projectId, setProjectId] = useState("");
    const [promptId, setPromptId] = useState("");
    const [modelIds, setModelIds] = useState("gpt-4o,llama3.2");
    const [testInputs, setTestInputs] = useState("[{\"input\":\"Summarize the feedback\"}]");
    const [message, setMessage] = useState<string | null>(null);
    const [result, setResult] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        const storedToken = getAuthToken();
        setToken(storedToken);
    }, []);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token);
    }, [token]);

    async function loadProjects(activeToken: string) {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        if (data[0]) {
            setProjectId(data[0].id);
        }
    }

    async function runExperiment() {
        if (!token || !projectId) {
            setMessage("Create and select a project first.");
            return;
        }
        try {
            const response = await apiFetch("/api/v1/experiments/run", {
                token,
                method: "POST",
                body: JSON.stringify({
                    project_id: projectId,
                    prompt_ids: promptId ? [promptId] : [],
                    model_ids: modelIds.split(",").map((item) => item.trim()).filter(Boolean),
                    task_type: "open_ended",
                    test_inputs: JSON.parse(testInputs),
                    confirm_cost: true,
                }),
                headers: { "Content-Type": "application/json" },
            });
            setResult(response as Record<string, unknown>);
            setMessage("Experiment submitted and completed in the backend response path.");
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Experiment run failed");
        }
    }

    return (
        <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
            <p className="text-sm uppercase tracking-[0.24em] text-accent">Screen 2</p>
            <h2 className="mt-2 text-3xl font-semibold">Experiment Runner</h2>
            <div className="mt-6 grid gap-4 max-w-3xl">
                <select className="rounded-2xl border border-black/10 px-4 py-3" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                    <option value="">Select a project</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
                <input className="rounded-2xl border border-black/10 px-4 py-3" placeholder="Prompt ID" value={promptId} onChange={(event) => setPromptId(event.target.value)} />
                <input className="rounded-2xl border border-black/10 px-4 py-3" placeholder="Model IDs comma-separated" value={modelIds} onChange={(event) => setModelIds(event.target.value)} />
                <textarea className="min-h-40 rounded-2xl border border-black/10 px-4 py-3" value={testInputs} onChange={(event) => setTestInputs(event.target.value)} />
                <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper" onClick={runExperiment} type="button">
                    Run experiment
                </button>
                {message ? <p className="text-sm text-ink/70">{message}</p> : null}
            </div>
            {result ? <pre className="mt-6 overflow-x-auto rounded-2xl bg-sand p-4 text-xs">{JSON.stringify(result, null, 2)}</pre> : null}
        </section>
    );
}
