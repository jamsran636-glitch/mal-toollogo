import type { TokenResponse } from "../types";

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export class NetworkError extends Error {}

let accessToken = sessionStorage.getItem("mal_access_token");
let refreshPromise: Promise<TokenResponse> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (token) sessionStorage.setItem("mal_access_token", token);
  else sessionStorage.removeItem("mal_access_token");
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  const detail = body?.detail;
  const message = typeof detail === "string" ? detail : "Сервер хүсэлтийг хүлээн авсангүй";
  return new ApiError(response.status, message, detail);
}

export async function refreshSession(): Promise<TokenResponse> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    }).then(async (response) => {
      if (!response.ok) throw await parseError(response);
      const result = await response.json() as TokenResponse;
      setAccessToken(result.access_token);
      return result;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function api<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });
  } catch {
    throw new NetworkError("Сүлжээний холболт алдагдсан байна");
  }
  if (response.status === 401 && retry && !path.includes("/auth/")) {
    await refreshSession();
    return api<T>(path, options, false);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function download(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_URL}${path}`, { headers, credentials: "include" });
  if (!response.ok) throw await parseError(response);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
