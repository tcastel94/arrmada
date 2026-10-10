"use client";

/**
 * Journal d'activité.
 * ----------------------------------------------------------------
 * `useActivityTimeline(filters)` : flux unifié (évènements ArrMada
 * persistés + historique Radarr/Sonarr en direct), filtrable. Utilisé par
 * /activity et le dashboard. (L'ancien `useActivityFeed`, qui ne lisait que
 * l'historique *arr, a été retiré : plus aucun écran ne l'utilisait.)
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Unified activity timeline (persisted events + *arr history) ─ */

export interface TimelineItem {
    id: string;
    ts: number; // epoch seconds
    category: string; // download | subtitle | playback | library | telegram | system
    action: string; // grab | grabbed | imported | sub_download | kodi_play | cast_play | …
    status: "ok" | "ko" | "info";
    source: string; // arrmada | kodi | radarr | sonarr | bazarr | telegram
    media_type: string | null;
    media_id: string | null;
    tmdb_id: number | null;
    title: string | null;
    subtitle: string | null;
    detail: string | null;
    duration_ms: number | null;
    device: string | null;
    size_bytes?: number | null;
    poster_url?: string | null;
    /** Données libres attachées à l'évènement (évènements persistés). */
    meta?: Record<string, unknown> | null;
}

export interface TimelineGroup {
    key: string;
    title: string;
    media_type: string | null;
    media_id: string | null;
    tmdb_id: number | null;
    poster_url: string | null;
    count: number;
    last_ts: number;
    items: TimelineItem[];
}

export interface TimelineResponse {
    items?: TimelineItem[];
    groups?: TimelineGroup[];
    total: number;
    grouped: boolean;
}

export interface TimelineFilters {
    categories?: string[];
    statuses?: string[];
    source?: string;
    search?: string;
    group?: "none" | "media";
    /** Nombre max d'évènements (backend : 1 → 500, défaut ici 200). */
    limit?: number;
}

export function useActivityTimeline(filters: TimelineFilters) {
    const qs = new URLSearchParams();
    if (filters.categories?.length) qs.set("categories", filters.categories.join(","));
    if (filters.statuses?.length) qs.set("statuses", filters.statuses.join(","));
    if (filters.source) qs.set("source", filters.source);
    if (filters.search) qs.set("search", filters.search);
    if (filters.group) qs.set("group", filters.group);
    qs.set("limit", String(filters.limit ?? 200));

    return useQuery<TimelineResponse>({
        queryKey: ["activity", "timeline", filters],
        queryFn: () => apiFetch(`/api/activity/timeline?${qs.toString()}`),
        refetchInterval: 20_000,
        // Changer un filtre ou « Charger plus » garde la liste actuelle à
        // l'écran pendant la requête (au lieu de repasser par les squelettes).
        placeholderData: keepPreviousData,
    });
}
