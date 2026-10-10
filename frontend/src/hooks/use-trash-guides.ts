"use client";

/**
 * TRaSH Guides : synchronisation des données, recommandations de profils
 * selon le matériel de l'utilisateur, application aux Sonarr/Radarr et
 * score de conformité (utilisé aussi par le Dashboard).
 */
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

/** Résumé d'un « Custom Format » (format personnalisé) TRaSH. */
export interface TrashCFSummary {
    trash_id: string;
    name: string;
    scores: Record<string, number> | null;
    /** hdr | audio | language | anime | unwanted | quality | autre… */
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

/** Résultat d'une application (ou d'un aperçu `dry_run`) sur un service. */
export interface ApplyResult {
    success: boolean;
    cfs_created: number;
    cfs_updated: number;
    profiles_created: number;
    profiles_updated: number;
    errors: string[];
}

export interface ApplyPayload {
    service_id: number;
    /** IDs de profils TRaSH (= nom de fichier source). */
    recommendations: string[];
    /** true = simulation : le backend compte ce qui changerait sans rien écrire. */
    dry_run?: boolean;
}

// ── Queries ──────────────────────────────────────────────────

export function useTrashStatus() {
    return useQuery<TrashSyncStatus>({
        queryKey: ["trash-guides", "status"],
        queryFn: () => apiFetch<TrashSyncStatus>("/api/trash-guides/status"),
        staleTime: 60_000,
        retry: 1,
        retryDelay: 1000,
    });
}

// ── Mutations ────────────────────────────────────────────────

/** Re-télécharge les données TRaSH depuis GitHub (force = ignore le cache 24 h). */
export function useTrashSync() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, boolean | void>({
        mutationFn: (force) =>
            apiFetch("/api/trash-guides/sync", {
                method: "POST",
                body: JSON.stringify({ force: force ?? false }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["trash-guides"] });
        },
    });
}

export function useTrashRecommend() {
    return useMutation<RecommendedProfile[], Error, MediaPreferences>({
        mutationFn: (prefs) =>
            apiFetch<RecommendedProfile[]>("/api/trash-guides/recommend", {
                method: "POST",
                body: JSON.stringify(prefs),
            }),
    });
}

/**
 * Applique (ou simule avec `dry_run`) des profils sur un service.
 * Après une vraie application, le score de conformité affiché sur le
 * Dashboard change → on invalide `["trash-guides","compliance"]`.
 */
export function useTrashApply() {
    const qc = useQueryClient();
    return useMutation<ApplyResult, Error, ApplyPayload>({
        mutationFn: (body) =>
            apiFetch<ApplyResult>("/api/trash-guides/apply", {
                method: "POST",
                body: JSON.stringify(body),
            }),
        onSuccess: (_res, body) => {
            if (!body.dry_run) qc.invalidateQueries({ queryKey: ["trash-guides", "compliance"] });
        },
    });
}

// ── Compliance (dashboard) ──────────────────────────────────

export interface ComplianceItem {
    service_id: number;
    service_name: string;
    service_type: string;
    trash_total: number;
    trash_found: number;
    compliance_pct: number;
    applied_profiles: string[];
}

export function useTrashCompliance() {
    return useQuery<ComplianceItem[]>({
        queryKey: ["trash-guides", "compliance"],
        queryFn: () => apiFetch<ComplianceItem[]>("/api/trash-guides/compliance"),
        staleTime: 300_000, // 5 min
        retry: 1,
    });
}
