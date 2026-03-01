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
