"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── TMDB Recommendations ──────────────────────────────────── */

export interface TMDBItem {
  tmdb_id: number;
  title: string;
  type: string;
  year?: string;
  overview: string;
  rating?: number;
  poster_url?: string;
  backdrop_url?: string;
  in_library?: boolean;
}

export function useRecommendations() {
  return useQuery<{
    trending_movies: TMDBItem[];
    trending_series: TMDBItem[];
    because_you_have: {
      base_title: string;
      base_poster?: string;
      recommendations: TMDBItem[];
    }[];
    wanted: Record<string, unknown>[];
    tmdb_available: boolean;
  }>({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch("/api/recommendations"),
    staleTime: 3600_000,
  });
}
