"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Automatic search (native *arr command) ────────────────── */

export function useTriggerMediaSearch() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; command: any },
        Error,
        { type: "movie" | "series"; id: number | string; season?: number }
    >({
        mutationFn: ({ type, id, season }) => {
            const qs = season !== undefined ? `?season=${season}` : "";
            return apiFetch(`/api/media/${type}/${id}/search${qs}`, { method: "POST" });
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ["media", "detail", variables.type, String(variables.id)],
            });
        },
    });
}

/* ── Automatic search for specific episodes (missing grab) ──── */

export function useSearchEpisodes() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; command: any; count: number },
        Error,
        { id: number | string; episodeIds: number[] }
    >({
        mutationFn: ({ id, episodeIds }) =>
            apiFetch(`/api/media/series/${id}/search-episodes`, {
                method: "POST",
                body: JSON.stringify({ episode_ids: episodeIds }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ["media", "detail", "series", String(variables.id)],
            });
        },
    });
}

/* ── Live search activity (Sonarr command queue) ───────────── */

export interface SearchActivity {
    episode_ids: number[];
    seasons: number[];
    series_search: boolean;
    active: boolean;
}

/**
 * Poll which episodes/seasons of a series currently have a search running in
 * Sonarr, so the UI can show a "recherche en cours" indicator. Polls every 4s
 * while enabled; harmless to leave running on the page.
 */
export function useSeriesSearchActivity(id: number | string, enabled = true) {
    return useQuery<SearchActivity>({
        queryKey: ["media", "search-activity", String(id)],
        queryFn: () => apiFetch(`/api/media/series/${id}/search-activity`),
        enabled: enabled && !!id,
        refetchInterval: 4000,
        refetchOnWindowFocus: true,
        staleTime: 0,
    });
}

/* ── Interactive release search ────────────────────────────── */

export interface Release {
    guid: string;
    indexer_id: number;
    indexer: string;
    title: string;
    size_bytes: number;
    seeders: number | null;
    leechers: number | null;
    age_days: number;
    quality: string;
    custom_format_score: number;
    custom_formats: string[];
    protocol: string;
    rejected: boolean;
    rejections: string[];
    download_url: string | null;
    info_url: string | null;
}

export interface ReleasesResponse {
    items: Release[];
    total: number;
}

/**
 * Fetch candidate releases for a media item (interactive search).
 * Disabled by default — pass `enabled` to trigger the (slow) indexer search.
 */
export function useMediaReleases(
    type: "movie" | "series",
    id: number | string,
    enabled: boolean,
    season?: number,
    episode?: number,
) {
    // Episode search (fast, single query per indexer) takes precedence over a
    // season-pack search (slow fan-out). Only one is sent to the backend.
    const qs =
        type === "series"
            ? episode !== undefined
                ? `?episode=${episode}`
                : season !== undefined
                    ? `?season=${season}`
                    : ""
            : "";
    // For series, either a season or an episode must be chosen before searching.
    const canQuery =
        enabled && !!id && (type === "movie" || season !== undefined || episode !== undefined);
    return useQuery<ReleasesResponse>({
        queryKey: ["media", "releases", type, String(id), season ?? null, episode ?? null],
        queryFn: () => apiFetch(`/api/media/${type}/${id}/releases${qs}`),
        enabled: canQuery,
        staleTime: 60_000,
        retry: false,
    });
}

/* ── Grab a release ────────────────────────────────────────── */

export function useGrabRelease() {
    return useMutation<
        { status: string; release: any },
        Error,
        { type: "movie" | "series"; id: number | string; guid: string; indexer_id: number }
    >({
        mutationFn: ({ type, id, guid, indexer_id }) =>
            apiFetch(`/api/media/${type}/${id}/grab`, {
                method: "POST",
                body: JSON.stringify({ guid, indexer_id }),
            }),
    });
}
