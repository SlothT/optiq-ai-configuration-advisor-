"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ApiError, apiFetch, setAuthToken } from "@/lib/api";

const verifyInFlight = new Map<string, Promise<{ access_token: string }>>();

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");
  const [message, setMessage] = useState("Confirming your email…");
  const [ok, setOk] = useState(false);

  useEffect(() => {
    if (!token) {
      setMessage("Open the confirmation link from your email. This page only works from that message.");
      return;
    }

    void (async () => {
      try {
        let pending = verifyInFlight.get(token);
        if (!pending) {
          pending = apiFetch("/api/v1/auth/verify", {
            method: "POST",
            body: JSON.stringify({ token }),
          }) as Promise<{ access_token: string }>;
          verifyInFlight.set(token, pending);
        }
        const result = await pending;
        setAuthToken(result.access_token);
        setOk(true);
        setMessage("Email confirmed. Taking you in…");
        window.setTimeout(() => router.push("/settings"), 800);
      } catch (error) {
        verifyInFlight.delete(token);
        setOk(false);
        setMessage(error instanceof ApiError ? error.message : "Verification failed.");
      }
    })();
  }, [token, router]);

  return (
    <section className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
      <p className="text-sm uppercase tracking-[0.24em] text-accent">Auth</p>
      <h2 className="mt-2 text-3xl font-semibold">{ok ? "You're in" : "Confirming email"}</h2>
      <p className="mt-4 text-sm text-ink/70">{message}</p>
    </section>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink/70">Confirming…</p>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
