const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

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
  window.dispatchEvent(new Event("optiq-auth"));
}

function parseErrorMessage(text: string, status: number) {
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    /* use fallback */
  }
  return text || `API request failed: ${status}`;
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

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}. Start the backend, then try again.`,
      0,
    );
  }

  if (!response.ok) {
    const message = parseErrorMessage(await response.text(), response.status);
    throw new ApiError(message, response.status);
  }

  return response.json();
}
