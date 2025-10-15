// src/utils/api.ts
import {
  RegisterRequest,
  LoginRequest,
  AuthResponse,
  RegisterResponse,
  User,
} from "../types/auth";

// כתובת הבסיס מה-ENV (Edge). אם אין, נופל ל-localhost:8080
const API_BASE_URL = import.meta.env.VITE_API_BASE ?? "http://localhost:8080";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
//   const url = `${API_BASE_URL}${endpoint}`;

//   const res = await fetch(url, {
//     headers: {
//       "Content-Type": "application/json",
//       ...(options.headers ?? {}),
//     },
//     ...options,
//   });

//   if (!res.ok) {
//     let msg = `HTTP ${res.status}`;
//     try {
//       const j = await res.json();
//       msg = j?.detail || j?.error || JSON.stringify(j);
//     } catch {
//       // ignore
//     }
//     throw new ApiError(res.status, msg);
//   }

//   return res.json() as Promise<T>;
// }

// ---------- Auth ----------
// src/utils/api.ts (החלף apiRequest הקיים)
// src/utils/api.ts - החלפה של apiRequest
async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  console.log(`[apiRequest] START ${options.method ?? "GET"} ${url}`);

  const controller = new AbortController();
  const timeoutMs = 20000; // 20s בזמן פיתוח — הורד/הגב לפי הצורך
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  // וודא שלא מוחלף ה-signal שלנו אם caller העביר signal
  const finalOptions: RequestInit = {
    ...options,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  };

  let res: Response;
  try {
    console.log("tring to fetch the url in the api.ts file", url);

    res = await fetch(url, finalOptions);
    console.log("succeed to fetch the url !!!");
    
  } catch (err: any) {
    clearTimeout(timeoutId);
    console.error(`[apiRequest] FETCH FAILED ${url}:`, err && (err.name || err.message) ? err : err);
    if (err && err.name === "AbortError") {
      throw new ApiError(0, "timeout");
    }
    throw new ApiError(0, err?.message ?? String(err));
  } finally {
    clearTimeout(timeoutId);
  }

  console.log(`[apiRequest] FIN ${res.status} ${url}`);

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j?.detail || j?.error || JSON.stringify(j);
    } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }

  // נסה לפרס JSON — ובמקרה של תשובה ריקה החזר אובייקט רלוונטי
  try {
    const text = await res.text();
    if (!text) return {} as T;
    return JSON.parse(text) as T;
  } catch (e) {
    console.error("[apiRequest] json parse error:", e);
    throw new ApiError(0, "invalid_json");
  }
}


export const authApi = {
  register(data: RegisterRequest): Promise<RegisterResponse> {
    return apiRequest<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  login(data: LoginRequest): Promise<AuthResponse> {
    console.log('[api.ts] try do the login');

    return apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  health(): Promise<{ ok: boolean; service: string }> {
    return apiRequest<{ ok: boolean; service: string }>("/health");
  },
};

// ---------- Helpers ----------
export const authHeader = (token?: string | null): Record<string, string> =>
  token ? { Authorization: `Bearer ${token}` } : {};


export type { User };
export default { authApi, apiRequest, authHeader };


