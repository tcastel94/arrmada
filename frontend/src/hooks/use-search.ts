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
