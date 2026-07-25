"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { MediaItem } from "@/hooks/use-media";

export interface IndexerResult {
    title: string;
    indexer: string;
    size_bytes: number;
    seeders: number;
    leechers: number;
    age_days: number;
    download_url: string | null;
    info_url: string | null;
    categories: string[];
    protocol: string;
}

export interface SearchResponse {
    query: string;
    library: {
        items: MediaItem[];
        total: number;
    };
    indexers: {
        items: IndexerResult[];
        total: number;
    };
}

export function useUnifiedSearch(query: string) {
    return useQuery<SearchResponse>({
        queryKey: ["search", query],
        queryFn: () => apiFetch(`/api/search?q=${encodeURIComponent(query)}`),
        enabled: query.length >= 2,
    });
}

/* ── AI Search ────────────────────────────────────────────── */

export interface AISearchFilters {
    type?: "movie" | "series" | null;
    genres?: string[];
    year_min?: number | null;
    year_max?: number | null;
    quality_keywords?: string[];
    title_keywords?: string[];
    size_filter?: string | null;
    has_file?: boolean | null;
    sort_by?: string | null;
    description?: string;
}

export interface AISearchResponse {
    query: string;
    description: string;
    filters: AISearchFilters;
    items: MediaItem[];
    total: number;
    ai_available: boolean;
    error?: string;
}

export function useAISearch(query: string) {
    return useQuery<AISearchResponse>({
        queryKey: ["search", "ai", query],
        queryFn: () => apiFetch(`/api/search/ai?q=${encodeURIComponent(query)}`),
        enabled: query.length >= 3,
        staleTime: 60_000,
        retry: false,
    });
}

/* ── Discover lookup (new titles to add, via *arr TMDB lookup) ── */

export interface LookupItem {
    title: string;
    year: number | null;
    tmdb_id: number | null;
    overview: string;
    poster_url: string | null;
    type: "movie" | "series";
    in_library: boolean;
    arr_id: number | null;
}

/** Look up addable movies AND series matching the query (both *arr services). */
export function useDiscoverLookup(query: string, enabled = true) {
    return useQuery<LookupItem[]>({
        queryKey: ["lookup", "discover", query],
        queryFn: async () => {
            const q = encodeURIComponent(query);
            const [movies, series] = await Promise.all([
                apiFetch<LookupItem[]>(`/api/requests/lookup?q=${q}&type=movie`).catch(() => []),
                apiFetch<LookupItem[]>(`/api/requests/lookup?q=${q}&type=series`).catch(() => []),
            ]);
            return [...(movies || []), ...(series || [])];
        },
        enabled: enabled && query.length >= 2,
        staleTime: 60_000,
        retry: false,
    });
}
