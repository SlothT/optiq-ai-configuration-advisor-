"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch, setAuthToken } from "@/lib/api";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [needsSignup, setNeedsSignup] = useState(false);
  const [needsVerify, setNeedsVerify] = useState(false);
  const [loading, setLoading] = useState(false);

  async function resendVerification() {
    try {
      const result = (await apiFetch("/api/v1/auth/resend-verification", {
        method: "POST",
        body: JSON.stringify({ email }),
      })) as { message: string };
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not resend verification");
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    setNeedsSignup(false);
    setNeedsVerify(false);

    try {
      const result = (await apiFetch("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { access_token: string };
      setAuthToken(result.access_token);
      router.push("/settings");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNeedsSignup(true);
      }
      if (error instanceof ApiError && error.status === 403) {
        setNeedsVerify(true);
      }
      setMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
      <p className="text-sm uppercase tracking-[0.24em] text-accent">Auth</p>
      <h2 className="mt-2 text-3xl font-semibold">Sign in</h2>
      <p className="mt-2 text-sm text-ink/70">Use an account you have already confirmed from your inbox.</p>
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
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper disabled:opacity-60" disabled={loading} type="submit">
          {loading ? "Signing in..." : "Sign in"}
        </button>
        {message ? <p className="text-sm text-ink/70">{message}</p> : null}
        {needsVerify ? (
          <button className="text-left text-sm font-medium text-accent" type="button" onClick={() => void resendVerification()}>
            Resend verification email
          </button>
        ) : null}
        {needsSignup ? (
          <Link href="/auth/register" className="text-sm font-medium text-accent">
            Create an account with this email
          </Link>
        ) : (
          <p className="text-sm text-ink/70">
            New here?{" "}
            <Link href="/auth/register" className="font-medium text-accent">
              Sign up
            </Link>
          </p>
        )}
      </form>
    </section>
  );
}
