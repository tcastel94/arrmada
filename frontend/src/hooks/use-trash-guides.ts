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
    /** Score réellement appliqué dans le profil (jeu de scores TRaSH du profil). */
    score?: number | null;
    /** « profil » ou nom du groupe TRaSH d'où vient le format. */
    source?: string | null;
}

export interface RecommendedProfile {
    profile_name: string;
    profile_id: string;
    service_type: string;
    description: string;
    custom_formats: TrashCFSummary[];
    score_profile: string;
    /** Nom du profil tel qu'il sera créé dans Sonarr / Radarr. */
    trash_name?: string;
    cutoff?: string;
    /** Qualités autorisées, meilleure en premier. */
    qualities?: string[];
    /** Groupes de formats TRaSH appliqués. */
    groups?: string[];
}

export interface MediaPreferences {
    display_type: "sdr" | "hdr10" | "hdr10plus" | "dolby_vision" | "dv_hdr10_fallback";
    audio_type: "stereo" | "surround_51" | "surround_71" | "atmos";
    language: "vo" | "vf" | "multi" | "vostfr";
    quality: "720p" | "1080p" | "2160p" | "best";
    watches_anime: boolean;
    watches_french_series: boolean;
}

export interface FormatScore {
    name: string;
    score: number;
    source: string;
}

export interface ProfileChange {
    name: string;
    id: number | null;
    action: "created" | "updated" | "unchanged";
    cutoff: string;
    min_format_score: number;
    cutoff_format_score: number;
    upgrade_allowed: boolean;
    qualities: string[];
    groups: string[];
    scores: FormatScore[];
    unknown_qualities: string[];
}

/** Taille de qualité (Mo par minute ; null = illimité). */
export interface SizeChange {
    quality: string;
    min: number;
    preferred: number | null;
    max: number | null;
}

/** Résultat d'une application (ou d'un aperçu `dry_run`) sur un service. */
export interface ApplyResult {
    success: boolean;
    dry_run: boolean;
    cfs_created: number;
    cfs_updated: number;
    cfs_unchanged: number;
    profiles_created: number;
    profiles_updated: number;
    created_formats: string[];
    updated_formats: string[];
    profiles: ProfileChange[];
    sizes: SizeChange[];
    warnings: string[];
    errors: string[];
}

export interface ApplyPayload {
    service_id: number;
    /** IDs de profils TRaSH (= nom de fichier source). */
    recommendations: string[];
    /** Réponses de l'assistant (groupes liés à l'écran et à l'audio). */
    prefs?: MediaPreferences;
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

// ── Bascule de la bibliothèque vers un profil ───────────────

export interface AssignResult {
    profile: string;
    profile_id: number;
    total: number;
    to_change: number;
    changed: number;
    dry_run: boolean;
}

/** Bascule tous les films / séries vers un profil (dry_run : compte seulement). */
export function useTrashAssign() {
    return useMutation<AssignResult, Error, { service_id: number; profile_name: string; dry_run: boolean }>({
        mutationFn: (body) =>
            apiFetch<AssignResult>("/api/trash-guides/assign-profile", {
                method: "POST",
                body: JSON.stringify(body),
            }),
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
