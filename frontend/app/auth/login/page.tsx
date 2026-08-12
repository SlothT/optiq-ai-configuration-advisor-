"use client";

import { useState } from "react";

import { apiFetch, setAuthToken } from "@/lib/api";

export default function LoginPage() {
    const [email, setEmail] = useState("demo@optiq.local");
    const [password, setPassword] = useState("Password123");
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setLoading(true);
        setMessage(null);

        try {
            const result = await apiFetch("/api/v1/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password }),
                headers: { "Content-Type": "application/json" },
            });
            setAuthToken(result.access_token as string);
            setMessage("Logged in. Token stored locally for this browser session.");
        } catch (error) {
            setMessage(error instanceof Error ? error.message : "Login failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
            <p className="text-sm uppercase tracking-[0.24em] text-accent">Auth</p>
            <h2 className="mt-2 text-3xl font-semibold">Login</h2>
            <form className="mt-6 grid gap-4 max-w-lg" onSubmit={handleSubmit}>
                <label className="grid gap-2 text-sm font-medium">
                    Email
                    <input className="rounded-2xl border border-black/10 px-4 py-3" value={email} onChange={(event) => setEmail(event.target.value)} />
                </label>
                <label className="grid gap-2 text-sm font-medium">
                    Password
                    <input className="rounded-2xl border border-black/10 px-4 py-3" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                </label>
                <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} type="submit">
                    {loading ? "Logging in..." : "Login"}
                </button>
                {message ? <p className="text-sm text-ink/70">{message}</p> : null}
            </form>
        </section>
    );
}
