"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Watched / resume status (library badges) ──────────────── */

export interface KodiWatchedEntry {
    playcount: number;
    resume_position: number; // seconds
    resume_total: number; // seconds
    lastplayed: string | null;
    title: string;
    year: number | null;
}

/** Map keyed by TMDB id → watched/resume state from Kodi. */
export function useKodiWatchedStatus(enabled = true) {
    return useQuery<Record<string, KodiWatchedEntry>>({
        queryKey: ["kodi", "watched"],
        queryFn: () => apiFetch("/api/kodi/watched-status"),
        enabled,
        staleTime: 60_000,
    });
}

/* ── Play on Kodi ──────────────────────────────────────────── */

export function useKodiPlay() {
    return useMutation<
        { status: string; detail?: string; kodi?: string; movieid?: number },
        Error,
        { tmdb_id: number; service_id?: number }
    >({
        mutationFn: (body) =>
            apiFetch("/api/kodi/play", { method: "POST", body: JSON.stringify(body) }),
    });
}

/* ── Maintenance ───────────────────────────────────────────── */

export interface KodiDrift {
    radarr_total: number;
    kodi_total: number;
    missing_count: number;
    missing_in_kodi: { tmdb_id: string; title: string; year: number | null }[];
}

export function useKodiDrift(enabled = true) {
    return useQuery<KodiDrift>({
        queryKey: ["kodi", "drift"],
        queryFn: () => apiFetch("/api/kodi/drift"),
        enabled,
        staleTime: 60_000,
    });
}

export function useKodiClean() {
    return useMutation<{ status: string; detail?: string }, Error, { service_id?: number } | void>({
        mutationFn: (body) =>
            apiFetch("/api/kodi/clean", { method: "POST", body: JSON.stringify(body || {}) }),
    });
}

export function useKodiSync() {
    const qc = useQueryClient();
    return useMutation<{ success: number; failed: number }, Error, void>({
        mutationFn: () => apiFetch("/api/kodi/sync", { method: "POST" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi"] }),
    });
}

/* ── Settings (instances) ──────────────────────────────────── */

export interface KodiInstance {
    id: number;
    name: string;
    url: string;
    is_enabled: boolean;
    api_key: string;
}

export function useKodiSettings() {
    return useQuery<KodiInstance[]>({
        queryKey: ["kodi", "settings"],
        queryFn: () => apiFetch("/api/kodi/settings"),
    });
}

export function useAddKodi() {
    const qc = useQueryClient();
    return useMutation<
        { id: number; message: string },
        Error,
        { name: string; url: string; api_key: string; is_enabled?: boolean }
    >({
        mutationFn: (body) =>
            apiFetch("/api/kodi/settings", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi", "settings"] }),
    });
}

export function useDeleteKodi() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/kodi/settings/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi", "settings"] }),
    });
}

export function useTestKodi() {
    return useMutation<
        { ok: boolean; version?: string; name?: string; detail?: string },
        Error,
        number
    >({
        mutationFn: (id) => apiFetch(`/api/kodi/test/${id}`, { method: "POST" }),
    });
}

export function useKodiDiscover() {
    return useMutation<{ name: string; url: string }[], Error, void>({
        mutationFn: () => apiFetch("/api/kodi/discover"),
    });
}
