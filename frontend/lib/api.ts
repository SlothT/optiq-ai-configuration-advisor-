const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("optiq_token");
}

export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem("optiq_token", token);
  } else {
    window.localStorage.removeItem("optiq_token");
  }
}

export async function apiFetch(path: string, init?: RequestInit & { token?: string | null }) {
  const headers = new Headers(init?.headers ?? {});
  const token = init?.token ?? getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API request failed: ${response.status}`);
  }

  return response.json();
}
