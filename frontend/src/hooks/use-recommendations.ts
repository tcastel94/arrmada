"use client";

/**
 * Suggestions TMDB (onglet « Suggestions » de /search).
 * ----------------------------------------------------------------
 * Le backend met la réponse en cache 1 h ; on la considère fraîche 30 min
 * côté navigateur. Le flux temps réel (SSE « new_import ») invalide la clé
 * ["recommendations"] quand un nouveau média arrive.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── TMDB Recommendations ──────────────────────────────────── */

export interface TMDBItem {
    /** Vrai ID TMDB (y compris pour les séries — à ne PAS confondre avec TVDB). */
    tmdb_id: number;
    title: string;
    original_title?: string;
    type: "movie" | "series" | string;
    /** Année sous forme de texte ("2024") ou null. */
    year?: string | null;
    overview: string;
    rating?: number | null;
    vote_count?: number;
    poster_url?: string | null;
    backdrop_url?: string | null;
    in_library?: boolean;
}

/** « Parce que tu as {base_title} » : un groupe de recommandations par film de base. */
export interface RecommendationGroup {
    base_title: string;
    base_poster?: string | null;
    recommendations: TMDBItem[];
}

/** Média surveillé encore sans fichier. */
export interface WantedItem {
    title: string;
    type: string;
    year: number | null;
    poster_url: string | null;
    source_service?: string | null;
}

export interface RecommendationsResponse {
    trending_movies: TMDBItem[];
    trending_series: TMDBItem[];
    because_you_have: RecommendationGroup[];
    wanted: WantedItem[];
    tmdb_available: boolean;
}

export function useRecommendations() {
    return useQuery<RecommendationsResponse>({
        queryKey: ["recommendations"],
        queryFn: () => apiFetch("/api/recommendations"),
        staleTime: 30 * 60_000,
    });
}
