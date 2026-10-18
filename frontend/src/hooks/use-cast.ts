"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface CastDevice {
    id: number;
    uuid: string;
    name: string;
    ip: string;
    port: number;
    model: string | null;
    video_capable: boolean;
}

export function useCastDevices() {
    return useQuery<CastDevice[]>({
        queryKey: ["cast", "devices"],
        queryFn: () => apiFetch("/api/cast/devices"),
        staleTime: 60_000,
    });
}

export function useCastDiscover() {
    const qc = useQueryClient();
    return useMutation<CastDevice[], Error, void>({
        mutationFn: () => apiFetch("/api/cast/discover", { method: "POST" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["cast", "devices"] }),
    });
}

export function useDeleteCastDevice() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/cast/devices/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["cast", "devices"] }),
    });
}

/** Film : tmdb_id. Épisode : tvdb_id de la série + numéros de saison et d'épisode. */
export type CastPlayBody = {
    device_id: number;
    media_id?: string;
    title?: string;
} & ({ tmdb_id: number } | { tvdb_id: number; season: number; episode: number });

export function useCastPlay() {
    return useMutation<
        { status: string; detail?: string; player_state?: string },
        Error,
        CastPlayBody
    >({
        mutationFn: (body) => apiFetch("/api/cast/play", { method: "POST", body: JSON.stringify(body) }),
    });
}

export function useCastControl() {
    return useMutation<
        { status: string; detail?: string },
        Error,
        { device_id: number; action: "pause" | "play" | "stop" | "quit" | "volume" | "mute"; value?: number | boolean }
    >({
        mutationFn: (body) => apiFetch("/api/cast/control", { method: "POST", body: JSON.stringify(body) }),
    });
}

/* ── Jellyfin config ───────────────────────────────────────── */

export interface JellyfinConfig {
    configured: boolean;
    id?: number;
    name?: string;
    url?: string;
    is_enabled?: boolean;
}

export function useJellyfinConfig() {
    return useQuery<JellyfinConfig>({
        queryKey: ["cast", "jellyfin"],
        queryFn: () => apiFetch("/api/cast/jellyfin"),
    });
}

export function useSetJellyfin() {
    const qc = useQueryClient();
    return useMutation<{ status: string; detail?: string }, Error, { url: string; api_key: string; name?: string }>({
        mutationFn: async (body) => {
            const res = await apiFetch<{ status: string; detail?: string }>("/api/cast/jellyfin", {
                method: "POST",
                body: JSON.stringify(body),
            });
            // Le backend répond 200 {status:"error"} (ex: clé API manquante) :
            // on le remonte en vraie erreur pour ne pas afficher « enregistré ».
            if (res?.status === "error") throw new Error(res.detail || "Configuration Jellyfin refusée");
            return res;
        },
        onSuccess: () => qc.invalidateQueries({ queryKey: ["cast", "jellyfin"] }),
    });
}

/** Marqueurs d'épisode (intro / générique) : serveur assez récent et plugin qui les calcule. */
export interface JellyfinSegmentsSupport {
    supported: boolean;
    providers: string[];
    checked: boolean;
}

export function useTestJellyfin() {
    return useMutation<
        { ok: boolean; server?: string; version?: string; detail?: string; segments?: JellyfinSegmentsSupport },
        Error,
        void
    >({
        mutationFn: () => apiFetch("/api/cast/jellyfin/test"),
    });
}
