"use client";

import { apiFetch } from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// ── Types ────────────────────────────────────────────────────

export interface TrashSyncStatus {
    last_sync: string | null;
    sonarr_cf_count: number;
    radarr_cf_count: number;
    sonarr_qp_count: number;
    radarr_qp_count: number;
    cache_age_hours: number | null;
    is_stale: boolean;
}

export interface TrashCFSummary {
    trash_id: string;
    name: string;
    scores: Record<string, number> | null;
    category: string;
}

export interface RecommendedProfile {
    profile_name: string;
    profile_id: string;
    service_type: string;
    description: string;
    custom_formats: TrashCFSummary[];
    score_profile: string;
}

export interface MediaPreferences {
    display_type: "sdr" | "hdr10" | "hdr10plus" | "dolby_vision" | "dv_hdr10_fallback";
    audio_type: "stereo" | "surround_51" | "surround_71" | "atmos";
    language: "vo" | "vf" | "multi" | "vostfr";
    quality: "720p" | "1080p" | "2160p" | "best";
    watches_anime: boolean;
    watches_french_series: boolean;
}

export interface ApplyResult {
    success: boolean;
    cfs_created: number;
    cfs_updated: number;
    profiles_created: number;
    profiles_updated: number;
    errors: string[];
}

// ── Queries ──────────────────────────────────────────────────

export function useTrashStatus() {
    return useQuery<TrashSyncStatus>({
        queryKey: ["trash-guides", "status"],
        queryFn: () => apiFetch("/api/trash-guides/status"),
        staleTime: 60_000,
    });
}

export function useTrashCustomFormats(service = "sonarr", category?: string) {
    return useQuery<TrashCFSummary[]>({
        queryKey: ["trash-guides", "custom-formats", service, category],
        queryFn: () => {
            const params = new URLSearchParams({ service });
            if (category) params.set("category", category);
            return apiFetch(`/api/trash-guides/custom-formats?${params}`);
        },
        staleTime: 300_000, // 5min
    });
}

// ── Mutations ────────────────────────────────────────────────

export function useTrashSync() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (force: boolean = false) =>
            apiFetch("/api/trash-guides/sync", {
                method: "POST",
                body: JSON.stringify({ force }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["trash-guides"] });
        },
    });
}

export function useTrashRecommend() {
    return useMutation<RecommendedProfile[], Error, MediaPreferences>({
        mutationFn: (prefs) =>
            apiFetch("/api/trash-guides/recommend", {
                method: "POST",
                body: JSON.stringify(prefs),
            }),
    });
}

export function useTrashApply() {
    return useMutation<ApplyResult, Error, { service_id: number; recommendations: string[]; dry_run?: boolean }>({
        mutationFn: (body) =>
            apiFetch("/api/trash-guides/apply", {
                method: "POST",
                body: JSON.stringify(body),
            }),
    });
}
