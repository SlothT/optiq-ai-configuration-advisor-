"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

type RegisterResult = {
  message: string;
};

export function RegisterForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [alreadyExists, setAlreadyExists] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    setAlreadyExists(false);

    try {
      const created = (await apiFetch("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as RegisterResult;
      setMessage(created.message);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setAlreadyExists(true);
      }
      setMessage(error instanceof Error ? error.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
      <p className="text-sm uppercase tracking-[0.24em] text-accent">Auth</p>
      <h2 className="mt-2 text-3xl font-semibold">Create your account</h2>
      <p className="mt-2 text-sm text-ink/70">
        We email a one-time confirmation link. You can sign in only after you open that inbox and click it.
      </p>
      <form className="mt-6 grid max-w-lg gap-4" onSubmit={handleSubmit}>
        <label className="grid gap-2 text-sm font-medium">
          Email
          <input
            className="rounded-2xl border border-black/10 px-4 py-3"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="grid gap-2 text-sm font-medium">
          Password
          <input
            className="rounded-2xl border border-black/10 px-4 py-3"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <p className="text-xs text-ink/50">At least 8 characters, with letters and numbers.</p>
        <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} type="submit">
          {loading ? "Creating account..." : "Create account"}
        </button>
        {message ? <p className="text-sm text-ink/70">{message}</p> : null}
        {alreadyExists ? (
          <Link href="/auth/login" className="text-sm font-medium text-accent">
            Sign in with this email
          </Link>
        ) : (
          <p className="text-sm text-ink/70">
            Already have an account?{" "}
            <Link href="/auth/login" className="font-medium text-accent">
              Sign in
            </Link>
          </p>
        )}
      </form>
    </section>
  );
}
