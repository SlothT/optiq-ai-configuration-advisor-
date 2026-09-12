"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { apiFetch, setAuthToken } from "@/lib/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
          renderButton: (element: HTMLElement, config: { theme: string; size: string; width: number; text: string }) => void;
        };
      };
    };
  }
}

export function GoogleSignIn({ label }: { label: "signin" | "signup" }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId || !containerRef.current) {
      return;
    }

    const handleCredential = async (credential: string) => {
      const result = (await apiFetch("/api/v1/auth/google", {
        method: "POST",
        body: JSON.stringify({ id_token: credential }),
      })) as { access_token: string };
      setAuthToken(result.access_token);
      router.push("/settings");
    };

    const start = () => {
      if (!window.google || !containerRef.current) {
        return;
      }
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          void handleCredential(response.credential);
        },
      });
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: "outline",
        size: "large",
        width: 320,
        text: label === "signup" ? "signup_with" : "signin_with",
      });
    };

    if (window.google) {
      start();
      return;
    }

    const existing = document.querySelector("script[data-optiq-google]");
    if (existing) {
      existing.addEventListener("load", start);
      return () => existing.removeEventListener("load", start);
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.dataset.optiqGoogle = "true";
    script.addEventListener("load", start);
    document.head.appendChild(script);
    return () => script.removeEventListener("load", start);
  }, [clientId, label, router]);

  if (!clientId) {
    return (
      <p className="text-xs text-ink/50">
        Google sign-in is optional. Add <code>NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> in <code>frontend/.env.local</code> and{" "}
        <code>GOOGLE_CLIENT_ID</code> in the API <code>.env</code> to enable it.
      </p>
    );
  }

  return <div ref={containerRef} className="flex justify-center" />;
}
