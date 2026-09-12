"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch, getAuthToken } from "@/lib/api";
import type { Project, ProviderView } from "@/lib/types";

export default function SettingsPage() {
    const [token, setToken] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [projectName, setProjectName] = useState("");
    const [selectedProjectId, setSelectedProjectId] = useState<string>("");
    const [providers, setProviders] = useState<ProviderView[]>([]);
    const [providerName, setProviderName] = useState("openai");
    const [apiKey, setApiKey] = useState("");
    const [ollamaBaseUrl, setOllamaBaseUrl] = useState("");
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        const storedToken = getAuthToken();
        setToken(storedToken);
    }, []);

    const applyOllamaUrlFromProviders = useCallback((data: ProviderView[]) => {
        const ollama = data.find((provider) => provider.provider_name === "ollama");
        setOllamaBaseUrl(ollama?.ollama_base_url ?? "");
    }, []);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    const loadProviders = useCallback(async (activeToken: string, projectId: string) => {
        const data = (await apiFetch(`/api/v1/projects/${projectId}/providers`, { token: activeToken })) as ProviderView[];
        setProviders(data);
        applyOllamaUrlFromProviders(data);
    }, [applyOllamaUrlFromProviders]);

    const loadProjects = useCallback(async (activeToken: string) => {
        const data = (await apiFetch("/api/v1/projects", { token: activeToken })) as Project[];
        setProjects(data);
        if (!selectedProjectId && data[0]) {
            setSelectedProjectId(data[0].id);
            await loadProviders(activeToken, data[0].id);
        }
    }, [loadProviders, selectedProjectId]);

    useEffect(() => {
        if (!token) {
            return;
        }
        void loadProjects(token);
    }, [token, loadProjects]);

    async function createProject() {
        if (!token) {
            setMessage("Sign in first.");
            return;
        }
        if (!projectName.trim()) {
            setMessage("Enter a project name, then click Create project.");
            return;
        }
        try {
            const created = (await apiFetch("/api/v1/projects", {
                token,
                method: "POST",
                body: JSON.stringify({ name: projectName, description: "Phase 1 workspace" }),
                headers: { "Content-Type": "application/json" },
            })) as Project;
            setProjects((current) => [created, ...current]);
            setSelectedProjectId(created.id);
            setProjectName("");
            await loadProviders(token, created.id);
            setMessage(`Created project ${created.name}. You can save a provider now.`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Could not create project.");
        }
    }

    async function saveProvider() {
        if (!token) {
            setMessage("Sign in first.");
            return;
        }
        if (!selectedProjectId) {
            setMessage("Create or select a project first, then save the provider.");
            return;
        }
        try {
            await apiFetch(`/api/v1/projects/${selectedProjectId}/providers`, {
                token,
                method: "POST",
                body: JSON.stringify({
                    provider_name: providerName,
                    api_key: apiKey || null,
                    ollama_base_url: ollamaBaseUrl || null,
                }),
                headers: { "Content-Type": "application/json" },
            });
            await loadProviders(token, selectedProjectId);
            setApiKey("");
            setMessage(`Saved ${providerName} provider settings.`);
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Could not save provider.");
        }
    }

    const providerCards = useMemo(() => providers, [providers]);

    return (
        <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <h2 className="text-3xl font-semibold">Settings</h2>
                <p className="mt-3 text-sm text-ink/70">Create a project and store provider credentials for the current browser session.</p>

                <div className="mt-6 grid gap-4">
                    <label className="grid gap-2 text-sm font-medium">
                        New project name
                        <input className="rounded-2xl border border-black/10 px-4 py-3" value={projectName} onChange={(event) => setProjectName(event.target.value)} />
                    </label>
                    <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper" onClick={createProject} type="button">
                        Create project
                    </button>
                </div>

                <div className="mt-8 grid gap-3">
                    <p className="text-sm font-medium">Project switcher</p>
                    <select
                        className="rounded-2xl border border-black/10 px-4 py-3"
                        value={selectedProjectId}
                        onChange={(event) => {
                            const nextProjectId = event.target.value;
                            setSelectedProjectId(nextProjectId);
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
                </div>

                {message ? <p className="mt-4 text-sm text-ink/70">{message}</p> : null}
            </div>

            <div className="grid gap-6">
                <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                    <h3 className="text-2xl font-semibold">Provider settings</h3>
                    <div className="mt-5 grid gap-4">
                        <label className="grid gap-2 text-sm font-medium">
                            Provider
                            <select className="rounded-2xl border border-black/10 px-4 py-3" value={providerName} onChange={(event) => setProviderName(event.target.value)}>
                                <option value="openai">OpenAI</option>
                                <option value="ollama">Ollama</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="google">Google</option>
                            </select>
                        </label>
                        <label className="grid gap-2 text-sm font-medium">
                            API key
                            <input className="rounded-2xl border border-black/10 px-4 py-3" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
                        </label>
                        <label className="grid gap-2 text-sm font-medium">
                            Ollama base URL
                            <input
                                className="rounded-2xl border border-black/10 px-4 py-3"
                                placeholder="http://localhost:11434"
                                value={ollamaBaseUrl}
                                onChange={(event) => setOllamaBaseUrl(event.target.value)}
                            />
                        </label>
                        <button className="rounded-full bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-60" disabled={!selectedProjectId} onClick={saveProvider} type="button">
                            Save provider
                        </button>
                        {!selectedProjectId ? <p className="text-sm text-ink/60">Create a project on the left before saving a provider.</p> : null}
                    </div>
                </div>

                <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                    <h3 className="text-2xl font-semibold">Configured providers</h3>
                    <div className="mt-5 grid gap-3">
                        {providerCards.map((provider) => (
                            <div key={provider.provider_name} className="rounded-2xl border border-black/10 p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <strong className="capitalize">{provider.provider_name}</strong>
                                    <span className="text-sm text-ink/70">{provider.configured ? "Configured" : "Not configured"}</span>
                                </div>
                                <p className="mt-2 text-sm text-ink/70">
                                    Models: {provider.available_models.map((model) => model.display_name).join(", ") || "None available"}
                                </p>
                                {provider.provider_name === "ollama" && provider.ollama_base_url ? (
                                    <p className="mt-2 text-sm text-ink/70">Base URL: {provider.ollama_base_url}</p>
                                ) : null}
                                {provider.status_message ? <p className="mt-2 text-sm text-red-700">{provider.status_message}</p> : null}
                            </div>
                        ))}
                        {!providerCards.length ? <p className="text-sm text-ink/70">Select a project to see provider status.</p> : null}
                    </div>
                </div>
            </div>
        </section>
    );
}
