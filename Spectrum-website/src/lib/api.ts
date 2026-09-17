/**
 * The one place the site talks to the Django backend.
 *
 * VITE_API_URL is inlined at build time. When it is unset the site runs on the
 * hardcoded fixtures in src/lib (the client-demo mode), and no request is made.
 */
const raw = (import.meta.env["VITE_API_URL"] as string | undefined) ?? "";

export const API_URL = raw.replace(/\/+$/, "");
export const hasApi = API_URL.length > 0;

export class ApiError extends Error {
  status: number;
  field: string | undefined;
  constructor(status: number, message: string, field?: string) {
    super(message);
    this.status = status;
    this.field = field;
  }
}

type Init = Omit<RequestInit, "body"> & { token?: string; json?: unknown; body?: BodyInit | null };

export async function apiFetch<T>(path: string, init: Init = {}): Promise<T> {
  const { token, json, headers: extra, ...rest } = init;
  const headers = new Headers(extra);
  headers.set("Accept", "application/json");
  let body: BodyInit | null = init.body ?? null;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...rest, headers, body });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { error?: string; field?: string };
    const message = data.error || response.statusText || `Request failed (${response.status})`;
    throw new ApiError(response.status, message, data.field);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}
