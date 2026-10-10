"use client";

/**
 * Statistiques de la médiathèque (page /analytics).
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface AnalyticsOverview {
    total_items: number;
    movies: number;
    series: number;
    total_size_bytes: number;
    total_size_human: string;
    movie_size_human: string;
    series_size_human: string;
    avg_movie_size_human: string;
    avg_series_size_human: string;
    monitored: number;
    available: number;
    missing: number;
}

export interface DistributionItem {
    name: string;
    count: number;
}

export interface YearItem {
    year: number;
    count: number;
}

export interface BiggestItem {
    title: string;
    type: "movie" | "series" | string;
    size_bytes: number;
    size_human: string;
    /** Films : nom de qualité. Séries : le backend renvoie l'ID du profil (nombre). */
    quality: string;
    /** Pas encore exposé par le backend : si présent, lien direct vers la fiche. */
    external_id?: string | number | null;
}

export interface ServiceBreakdown {
    name: string;
    count: number;
}

export interface AnalyticsData {
    overview: AnalyticsOverview;
    quality_distribution: DistributionItem[];
    genre_distribution: DistributionItem[];
    year_distribution: YearItem[];
    top_biggest: BiggestItem[];
    service_breakdown: ServiceBreakdown[];
}

export function useAnalytics() {
    return useQuery<AnalyticsData>({
        queryKey: ["analytics"],
        queryFn: () => apiFetch<AnalyticsData>("/api/analytics"),
        staleTime: 120_000,
    });
}
