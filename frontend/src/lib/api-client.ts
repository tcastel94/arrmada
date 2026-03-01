import { API_URL } from "./constants";
import { TokenResponse } from "@/types/api";

/** Stored JWT token key */
const TOKEN_KEY = "arrmada_token";

/** Get the stored auth token */
export function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
}

/** Set the auth token */
export function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
}

/** Remove the auth token */
export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
}

/** Check if user is authenticated */
export function isAuthenticated(): boolean {
    return !!getToken();
}

/**
 * Base fetch wrapper for the ArrMada backend API.
 * Automatically adds auth headers and handles errors.
 */
export async function apiFetch<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const token = getToken();

    const headers: HeadersInit = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
    };

    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers,
    });

    // Handle 401 — redirect to login
    if (response.status === 401) {
        clearToken();
        if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
            window.location.href = "/login";
        }
        throw new Error("Not authenticated");
    }

    // Handle 204 no content
    if (response.status === 204) {
        return undefined as T;
    }

    // Handle errors
    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({
            detail: response.statusText,
        }));
        throw new Error(errorBody.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

/** Login with password */
export async function login(password: string): Promise<TokenResponse> {
    const data = await apiFetch<TokenResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
    });
    setToken(data.access_token);
    return data;
}

/** Logout */
export function logout(): void {
    clearToken();
    if (typeof window !== "undefined") {
        window.location.href = "/login";
    }
}
