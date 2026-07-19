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
) {
    return useQuery<ReleasesResponse>({
        queryKey: ["media", "releases", type, String(id)],
        queryFn: () => apiFetch(`/api/media/${type}/${id}/releases`),
        enabled: enabled && !!id,
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
