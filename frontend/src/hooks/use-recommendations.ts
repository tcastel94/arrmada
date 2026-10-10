"use client";

/**
 * Suggestions TMDB (onglet « Découvrir » de /search).
 * ----------------------------------------------------------------
 *  - useRecommendations        : tendances + « Parce que tu as aimé… » +
 *                                titres attendus + liste du sélecteur
 *  - useRecommendationDetail   : fiche TMDB riche (casting, bande-annonce…)
 *                                pour la modale de détail
 *  - useRecommendationsBasedOn : recommandations ciblées « À partir de… »
 *  - useLibraryPicker          : recherche dans TOUTE la bibliothèque pour
 *                                le sélecteur (le backend n'en envoie que 50)
 *
 * Toutes les clés commencent par ["recommendations"] : le flux temps réel
 * (SSE « new_import ») invalide ce préfixe quand un média arrive, ce qui
 * rafraîchit aussi les pastilles « À toi » des fiches et rangées ouvertes.
 * Le backend garde ces réponses 30 min à 1 h en cache : inutile de
 * les redemander plus souvent côté navigateur.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { MediaResponse } from "@/hooks/use-media";

/* ── Types ─────────────────────────────────────────────────── */

export interface TMDBItem {
    /** Vrai ID TMDB (y compris pour les séries — à ne PAS confondre avec TVDB). */
    tmdb_id: number;
    title: string;
    original_title?: string;
    type: "movie" | "series" | string;
    /** Année sous forme de texte ("2024") ou null. */
    year?: string | null;
    release_date?: string | null;
    overview: string;
    rating?: number | null;
    vote_count?: number;
    popularity?: number;
    poster_url?: string | null;
    backdrop_url?: string | null;
    genre_ids?: number[];
    in_library?: boolean;
}

/** « Parce que tu as aimé {base_title} » : un groupe de recommandations par titre de base. */
export interface RecommendationGroup {
    /** ID Radarr/Sonarr du titre de base (→ /media/{base_type}/{base_id}). */
    base_id?: string | null;
    base_title: string;
    base_type?: "movie" | "series" | string;
    base_poster?: string | null;
    recommendations: TMDBItem[];
}

/** Média surveillé encore sans fichier. */
export interface WantedItem {
    /** ID Radarr/Sonarr quand le backend le fournit (sinon null). */
    id?: string | number | null;
    title: string;
    type: string;
    year: number | null;
    poster_url: string | null;
    source_service?: string | null;
    /** Film : ID TMDB ; série : ID TVDB (convention Sonarr). */
    tmdb_id?: number | null;
}

/**
 * Titre de la bibliothèque proposé dans le sélecteur « À partir de… ».
 * ⚠️ Pour une série, `tmdb_id` contient l'ID **TVDB** (Sonarr) : c'est
 * `id_source` qui dit au backend comment l'interpréter.
 */
export interface LibrarySelectItem {
    /** ID Radarr/Sonarr (string). */
    id: string | number | null;
    title: string;
    type: "movie" | "series" | string;
    year?: number | null;
    poster_url?: string | null;
    tmdb_id?: number | null;
    /** "tmdb" (films) | "tvdb" (séries Sonarr). Absent d'un ancien backend. */
    id_source?: "tmdb" | "tvdb" | string;
}

export interface RecommendationsResponse {
    trending_movies: TMDBItem[];
    trending_series: TMDBItem[];
    because_you_have: RecommendationGroup[];
    wanted: WantedItem[];
    /** Optionnel : absent des anciennes versions du backend. */
    library_select_items?: LibrarySelectItem[];
    tmdb_available: boolean;
}

/** Membre du casting renvoyé par /details (photo déjà en URL complète). */
export interface TMDBCastMember {
    name: string;
    character?: string | null;
    profile_path?: string | null;
}

/** Fiche TMDB enrichie pour la modale de détail. */
export interface TMDBDetail {
    tmdb_id: number;
    title: string;
    original_title?: string;
    type: "movie" | "series" | string;
    year: string | null;
    release_date: string | null;
    overview: string;
    rating: number | null;
    vote_count: number;
    popularity?: number;
    /** Durée en minutes (film) ou durée type d'un épisode (série). */
    runtime: number | null;
    poster_url: string | null;
    backdrop_url: string | null;
    /** Genres déjà en français (TMDB interrogé en fr-FR). */
    genres: string[];
    cast: TMDBCastMember[];
    /** Réalisateur (film) ou créateur(s) (série). */
    director: string | null;
    /** Clé YouTube de la bande-annonce. */
    trailer_key: string | null;
    in_library: boolean;
    /** Titre correspondant dans Radarr/Sonarr (id = ID *arr, string). */
    library_item: { id: string | number | null; type: string } | null;
}

/** Type d'ID envoyé à /based_on (voir LibrarySelectItem.id_source). */
export type IdSource = "tmdb" | "tvdb";

/* ── Requêtes ──────────────────────────────────────────────── */

export function useRecommendations() {
    return useQuery<RecommendationsResponse>({
        queryKey: ["recommendations"],
        queryFn: () => apiFetch("/api/recommendations"),
        staleTime: 30 * 60_000,
    });
}

/**
 * Fiche TMDB d'un titre (modale de détail). Ne part qu'à l'ouverture de
 * la modale (`enabled`). Pas de nouvel essai automatique : la seule erreur
 * « normale » est la clé TMDB absente (400), qu'un 2e essai ne corrige pas.
 */
export function useRecommendationDetail(mediaType: string | null | undefined, tmdbId: number | null | undefined, enabled = true) {
    const type = mediaType === "series" ? "series" : "movie";
    return useQuery<TMDBDetail>({
        queryKey: ["recommendations", "detail", type, tmdbId],
        queryFn: () => apiFetch(`/api/recommendations/details/${type}/${tmdbId}`),
        enabled: enabled && !!tmdbId,
        staleTime: 30 * 60_000,
        retry: false,
    });
}

/**
 * Recommandations TMDB à partir d'un titre précis.
 * `source = "tvdb"` pour une série de la bibliothèque (le backend convertit
 * alors l'ID TVDB en ID TMDB) ; "tmdb" pour un film ou un titre TMDB.
 */
export function useRecommendationsBasedOn(
    mediaType: string | null | undefined,
    id: number | null | undefined,
    source: IdSource = "tmdb",
) {
    const type = mediaType === "series" ? "series" : "movie";
    return useQuery<{ items: TMDBItem[] }>({
        queryKey: ["recommendations", "based-on", type, source, id],
        queryFn: () =>
            apiFetch(`/api/recommendations/based_on/${type}/${id}${source === "tvdb" ? "?source=tvdb" : ""}`),
        enabled: !!mediaType && !!id,
        staleTime: 30 * 60_000,
        retry: 1,
    });
}

/**
 * Recherche dans toute la bibliothèque (titres AVEC fichier) pour le
 * sélecteur « À partir de… ». Le backend ne joint que 50 titres à
 * /api/recommendations : sans cette recherche, une grosse médiathèque
 * serait inaccessible au-delà de ces 50. On passe par /api/media (cache
 * serveur 5 min) et non /api/search, qui interroge aussi les indexers.
 */
export function useLibraryPicker(query: string) {
    const q = query.trim();
    return useQuery<LibrarySelectItem[]>({
        queryKey: ["recommendations", "picker", q],
        queryFn: async () => {
            const params = new URLSearchParams({ search: q, availability: "available", sort: "title", per_page: "30" });
            const res = await apiFetch<MediaResponse>(`/api/media?${params.toString()}`);
            return (res?.items ?? []).map((m) => ({
                id: m.external_id,
                title: m.title,
                type: m.type,
                year: m.year,
                poster_url: m.poster_url,
                tmdb_id: m.tmdb_id,
                // Même convention que l'agrégateur : série → ID TVDB.
                id_source: m.type === "series" ? "tvdb" : "tmdb",
            }));
        },
        enabled: q.length >= 2,
        staleTime: 5 * 60_000,
        placeholderData: keepPreviousData,
        retry: false,
    });
}
