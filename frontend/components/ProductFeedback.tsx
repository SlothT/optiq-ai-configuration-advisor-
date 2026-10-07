"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { apiFetch } from "@/lib/api";

export function ProductFeedback() {
  const page = usePathname();
  const [rating, setRating] = useState("helpful");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  if (page.startsWith("/auth/")) return null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    setMessage("");
    try {
      await apiFetch("/api/v1/feedback", { method: "POST", body: JSON.stringify({ page, rating, comment }) });
      setComment("");
      setMessage("Thanks for your feedback.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not send feedback. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <footer className="mt-8 rounded-2xl border border-black/10 bg-white/70 p-4">
      <details>
        <summary className="cursor-pointer text-sm font-medium">Give feedback</summary>
        <form onSubmit={submit} className="mt-4 grid max-w-lg gap-3 text-sm">
          <label className="grid gap-2">Was this page useful?
            <select className="rounded-xl border p-3" value={rating} onChange={(event) => setRating(event.target.value)}>
              <option value="helpful">Yes</option><option value="not_helpful">No</option>
            </select>
          </label>
          <label className="grid gap-2">What could we improve? (optional)
            <textarea className="rounded-xl border p-3" maxLength={1000} value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          <p className="text-ink/60">We save this page, your rating, and your comment. Please leave out passwords, API keys, and private prompt details.</p>
          <button disabled={sending} className="rounded-full bg-ink px-4 py-2 text-paper disabled:opacity-60" type="submit">{sending ? "Sending…" : "Send feedback"}</button>
          {message ? <p role="status">{message}</p> : null}
        </form>
      </details>
    </footer>
  );
}
