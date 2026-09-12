"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiFetch, getAuthToken, setAuthToken, ApiError } from "@/lib/api";

type Me = { email: string };

export function HeaderAuth() {
  const [email, setEmail] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setEmail(null);
      return;
    }
    try {
      const me = (await apiFetch("/api/v1/auth/me", { token })) as Me;
      setEmail(me.email);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
        setAuthToken(null);
      }
      setEmail(null);
    }
  }, []);

  useEffect(() => {
    const onAuth = () => {
      void refresh();
    };
    void refresh();
    window.addEventListener("optiq-auth", onAuth);
    return () => window.removeEventListener("optiq-auth", onAuth);
  }, [refresh]);

  if (email) {
    return (
      <div className="flex items-center gap-2 text-xs font-medium">
        <span className="max-w-[14rem] truncate text-ink/70">{email}</span>
        <button
          className="rounded-full px-4 py-2 text-ink transition hover:bg-black/5"
          type="button"
          onClick={() => {
            setAuthToken(null);
            setEmail(null);
          }}
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs font-medium">
      <Link href="/auth/login" className="rounded-full px-4 py-2 text-ink transition hover:bg-black/5">
        Sign In
      </Link>
      <Link href="/auth/register" className="rounded-full bg-ink px-4 py-2 text-paper transition hover:bg-ink/90">
        Get Started
      </Link>
    </div>
  );
}
