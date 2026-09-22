import { useAuthStore } from '../store/authStore';
import type { AuthTokens } from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_URL) {
  // Fails loudly at startup instead of letting every request silently
  // hit "undefined/api/v1/..." — see frontend/README.md for local setup
  // (copy .env.example to .env and set VITE_API_BASE_URL).
  console.error(
    'VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env and restart the dev server.',
  );
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** JSON-serializable request body; sets Content-Type: application/json. */
  json?: unknown;
  /** Form-encoded request body (used by OAuth2 password flow login). */
  form?: Record<string, string>;
  /** Skip attaching the Authorization header and skip the 401-refresh dance. */
  skipAuth?: boolean;
}

// Ensures concurrent 401s trigger only a single /auth/refresh call.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      logout();
      return null;
    }
    const tokens: AuthTokens = await res.json();
    setTokens(tokens);
    return tokens.access_token;
  } catch {
    logout();
    return null;
  }
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
  isRetry = false,
): Promise<T> {
  const { json, form, skipAuth, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    ...((headers as Record<string, string>) ?? {}),
  };

  let body: BodyInit | undefined;
  if (json !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    finalHeaders['Content-Type'] = 'application/x-www-form-urlencoded';
    body = new URLSearchParams(form).toString();
  }

  if (!skipAuth) {
    const { accessToken } = useAuthStore.getState();
    if (accessToken) {
      finalHeaders['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    body,
  });

  if (res.status === 401 && !skipAuth && !isRetry) {
    if (!refreshInFlight) {
      refreshInFlight = refreshAccessToken().finally(() => {
        refreshInFlight = null;
      });
    }
    const newAccessToken = await refreshInFlight;
    if (newAccessToken) {
      return request<T>(path, options, true);
    }
    // Refresh failed: send the user back to login.
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Session expired. Please log in again.');
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // response body wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', json }),
  patch: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', json }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
  postForm: <T>(path: string, form: Record<string, string>, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', form }),
};
