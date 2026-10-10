"use client";

/**
 * Hooks de recherche (page « Rechercher & Ajouter »).
 * ----------------------------------------------------------------
 *  - useUnifiedSearch  : titres déjà présents dans la bibliothèque
 *  - useAISearch       : recherche en langage naturel (filtres déduits par l'IA)
 *  - useDiscoverLookup : titres AJOUTABLES (lookup Radarr + Sonarr)
 * `keepPreviousData` garde les résultats affichés pendant la frappe :
 * pas de « flash » de squelettes à chaque lettre.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
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
        placeholderData: keepPreviousData,
        staleTime: 30_000,
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
    /** Vrai ID TMDB (films ; séries quand Sonarr v4 le connaît). */
    tmdb_id: number | null;
    /**
     * ID TVDB (séries). Absent des anciennes versions du backend, qui
     * renvoyaient l'ID TVDB d'une série… dans `tmdb_id` (voir `fromLookup`).
     */
    tvdb_id?: number | null;
    overview: string;
    poster_url: string | null;
    type: "movie" | "series";
    in_library: boolean;
    arr_id: number | null;
}

/**
 * Titres ajoutables (films ET séries) correspondant à la requête.
 * Chaque service est interrogé en parallèle ; si l'un des deux est absent
 * ou en panne, on garde quand même les résultats de l'autre.
 */
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
        placeholderData: keepPreviousData,
    });
}
