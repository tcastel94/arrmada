"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface DownloadItem {
    id: number;
    title: string;
    status: string;
    progress: number;
    size_bytes: number;
    size_left_bytes: number;
    time_left: string | null;
    source_service: string;
    service_type: string;
    movie_id: number | null;
    series_id: number | null;
    download_client: string;
    indexer: string;
    quality: string;
}

export interface DownloadsResponse {
    items: DownloadItem[];
    total: number;
}

export function useDownloads() {
    return useQuery<DownloadsResponse>({
        queryKey: ["downloads"],
        queryFn: () => apiFetch("/api/downloads"),
        refetchInterval: 10_000, // Refresh every 10s for active downloads
    });
}

// ── Queue actions ────────────────────────────────────────────

export function useRemoveQueueItem() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; id: number; blocklisted: boolean },
        Error,
        { type: string; id: number; removeFromClient?: boolean; blocklist?: boolean }
    >({
        mutationFn: ({ type, id, removeFromClient = true, blocklist = false }) =>
            apiFetch(`/api/downloads/queue/${type}/${id}/remove`, {
                method: "POST",
                body: JSON.stringify({ removeFromClient, blocklist }),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["downloads"] });
        },
    });
}

export function useRetryQueueItem() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; id: number; search_triggered: boolean },
        Error,
        { type: string; id: number; movie_id?: number | null; series_id?: number | null }
    >({
        mutationFn: ({ type, id, movie_id, series_id }) =>
            apiFetch(`/api/downloads/queue/${type}/${id}/retry`, {
                method: "POST",
                body: JSON.stringify({ movie_id, series_id }),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["downloads"] });
        },
    });
}
