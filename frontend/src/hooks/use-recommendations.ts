"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface RecommendationItem {
    title: string;
    type: string;
    year: number | null;
    poster_url: string | null;
    source_service: string;
    genres: string[];
}

export interface RecommendationsData {
    top_genres: string[];
    wanted: RecommendationItem[];
    recently_added: RecommendationItem[];
    stats: {
        total_wanted: number;
        total_library: number;
    };
}

export function useRecommendations() {
    return useQuery<RecommendationsData>({
        queryKey: ["recommendations"],
        queryFn: () => apiFetch("/api/recommendations"),
        staleTime: 120_000,
    });
}
