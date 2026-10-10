"use client";

/**
 * Hooks d'accès à la médiathèque (liste, recherche, fiche détail, édition).
 * ----------------------------------------------------------------
 * ATTENTION : `useMedia`, `useMediaFacets`, `useMediaSearch`, `MediaItem` et
 * `MediaFilters` sont utilisés par d'autres pages (médiathèque, manquants,
 * palette de commandes, badges de navigation) : leurs signatures ne doivent
 * pas changer.
 */
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { EpisodeSubtitleInfo, MovieSubtitleInfo } from "@/hooks/use-subtitles";

export interface MediaItem {
    external_id: string;
    tmdb_id: number | null;
    title: string;
    type: "movie" | "series";
    year: number | null;
    genres: string[];
    quality: string | null;
    size_bytes: number;
    poster_url: string | null;
    source_service: string;
    has_file: boolean;
    monitored: boolean;
    status: string;
    added: string | null;
    rating: number | null;
    runtime: number | null;
    overview: string;
    seasons?: number;
    episodes_total?: number;
    episodes_have?: number;
}

export interface MediaResponse {
    items: MediaItem[];
    pagination: {
        page: number;
        per_page: number;
        total: number;
        total_pages: number;
    };
}

export interface SearchResponse {
    items: MediaItem[];
    total: number;
}

export interface MediaFilters {
    type?: string;
    search?: string;
    sort?: string;
    order?: string;
    genre?: string;
    quality?: string;
    availability?: "available" | "missing";
    monitored?: boolean;
    page?: number;
    per_page?: number;
}

export function useMedia(params: MediaFilters) {
    const searchParams = new URLSearchParams();
    if (params.type) searchParams.set("type", params.type);
    if (params.search) searchParams.set("search", params.search);
    if (params.sort) searchParams.set("sort", params.sort);
    if (params.order) searchParams.set("order", params.order);
    if (params.genre) searchParams.set("genre", params.genre);
    if (params.quality) searchParams.set("quality", params.quality);
    if (params.availability) searchParams.set("availability", params.availability);
    if (params.monitored !== undefined) searchParams.set("monitored", String(params.monitored));
    if (params.page) searchParams.set("page", String(params.page));
    if (params.per_page) searchParams.set("per_page", String(params.per_page));

    const qs = searchParams.toString();

    return useQuery<MediaResponse>({
        queryKey: ["media", params],
        queryFn: () => apiFetch(`/api/media${qs ? `?${qs}` : ""}`),
        // Garde la page précédente affichée pendant le chargement de la
        // suivante (évite le « flash » de squelettes à chaque filtre/page).
        placeholderData: keepPreviousData,
    });
}

export interface MediaFacets {
    genres: string[];
    qualities: string[];
    total: number;
    missing_count: number;
    missing_monitored_count: number;
}

/** Genres / qualités distincts + compteurs de manquants sur toute la médiathèque. */
export function useMediaFacets() {
    return useQuery<MediaFacets>({
        queryKey: ["media", "facets"],
        queryFn: () => apiFetch("/api/media/facets"),
        staleTime: 5 * 60_000,
    });
}

export function useMediaSearch(query: string) {
    return useQuery<SearchResponse>({
        queryKey: ["media", "search", query],
        queryFn: () => apiFetch(`/api/media/search?q=${encodeURIComponent(query)}`),
        enabled: query.length >= 2,
    });
}

// ── Types de la fiche détail ─────────────────────────────────

export interface FileInfo {
    id: number;
    relative_path: string;
    path: string;
    size_bytes: number;
    quality: string;
    quality_source: string;
    /** Radarr/Sonarr renvoient un nombre (1080, 2160…) même si l'ancien typage disait string. */
    resolution: string | number;
    video_codec: string;
    video_dynamic_range: string;
    video_dynamic_range_type: string;
    audio_codec: string;
    audio_channels: number;
    audio_languages: string;
    subtitle_languages: string;
    run_time: string;
    release_group: string;
    edition: string;
    languages: string[];
    date_added: string | null;
}

export interface CastMember {
    name: string;
    character: string;
    /** "cast" pour les acteurs ; pour l'équipe : director, writer… (ou job TMDb). */
    type: string;
    job?: string;
    photo?: string;
    tmdb_id?: number | null;
    order?: number;
}

/* ── Filmographie d'un acteur (clic sur le casting) ─────────── */

export interface PersonInfo {
    tmdb_id: number;
    name: string;
    photo: string | null;
    biography: string;
    known_for: string;
    birthday: string | null;
    place_of_birth: string | null;
}

export interface PersonMovie {
    tmdb_id: number;
    title: string;
    year: number | null;
    character: string;
    poster: string | null;
    vote_average: number;
    popularity: number;
    /** Présent uniquement pour les films déjà dans la médiathèque. */
    radarr_id?: number;
    has_file?: boolean;
}

export interface PersonFilmography {
    person: PersonInfo | null;
    in_library: PersonMovie[];
    discover: PersonMovie[];
    counts: { in_library: number; discover: number };
    error?: string;
}

export function usePersonFilmography(personId: number | null, enabled: boolean) {
    return useQuery<PersonFilmography>({
        queryKey: ["media", "person", personId],
        queryFn: () => apiFetch(`/api/media/person/${personId}`),
        enabled: enabled && !!personId,
        staleTime: 5 * 60_000,
    });
}

export interface EpisodeDetail {
    id: number;
    episode_number: number;
    season_number: number;
    title: string;
    overview: string;
    /** Date de diffusion « jour » (YYYY-MM-DD), null si inconnue. */
    air_date: string | null;
    has_file: boolean;
    monitored: boolean;
    file: FileInfo | null;
}

export interface SeasonDetail {
    season_number: number;
    episode_count: number;
    episodes_have: number;
    monitored?: boolean;
    episodes: EpisodeDetail[];
}

/**
 * Notes : un film expose tmdb / imdb / metacritic / rotten_tomatoes,
 * une série expose seulement `value` (+ `votes`).
 */
export interface MediaRatings {
    tmdb?: number | null;
    imdb?: number | null;
    metacritic?: number | null;
    rotten_tomatoes?: number | null;
    value?: number | null;
    votes?: number | null;
}

export interface MediaDetail {
    id: number;
    type: "movie" | "series";
    title: string;
    original_title: string;
    sort_title?: string;
    year: number | null;
    overview: string;
    studio?: string;
    network?: string;
    genres: string[];
    /** Durée en MINUTES (film) ou durée moyenne d'un épisode (série). */
    runtime: number | null;
    status: string;
    monitored: boolean;
    quality_profile_id?: number | null;
    series_type?: string;
    minimum_availability?: string;
    has_file?: boolean;
    size_on_disk: number;
    added: string | null;
    path: string;
    root_folder_path?: string;
    certification: string;
    website?: string;
    youtube_trailer_id?: string;
    tmdb_id?: number;
    imdb_id?: string;
    tvdb_id?: number;
    ratings: MediaRatings;
    images: { poster: string | null; fanart: string | null; banner: string | null };
    file?: FileInfo | null;
    seasons?: SeasonDetail[];
    season_count?: number;
    total_episodes?: number;
    episodes_have?: number;
    cast?: CastMember[];
    crew?: CastMember[];
    /** Film : un seul bloc MovieSubtitleInfo ; série : un bloc par épisode. */
    subtitles: Array<MovieSubtitleInfo | EpisodeSubtitleInfo>;
    tags: number[];
    error?: string;
}

/**
 * Fiche détail d'un film / d'une série.
 * Le backend répond parfois 200 avec `{ error: "…" }` (service *arr absent ou
 * injoignable) : on le transforme en vraie erreur pour que la page affiche
 * un ErrorState avec le message réel et un bouton « Réessayer ».
 */
export function useMediaDetail(type: "movie" | "series", id: string) {
    return useQuery<MediaDetail>({
        queryKey: ["media", "detail", type, id],
        queryFn: async () => {
            const data = await apiFetch<MediaDetail>(`/api/media/${type}/${id}`);
            if (data?.error) throw new Error(data.error);
            return data;
        },
        enabled: !!id,
        retry: 1,
    });
}

export interface RootFolder {
    path: string;
    accessible: boolean;
    freeSpace: number;
    unmappedFolders: unknown[];
}

/** Dossiers racine Radarr/Sonarr (boîte « Déplacer »). `enabled` évite l'appel tant que la boîte est fermée. */
export function useMediaRootFolders(type: "movie" | "series", id: string, enabled = true) {
    return useQuery<RootFolder[]>({
        queryKey: ["media", "rootfolders", type, id],
        queryFn: () => apiFetch(`/api/media/${type}/${id}/rootfolders`),
        enabled: enabled && !!id,
        staleTime: 60_000,
    });
}

export function useUpdateMediaPath() {
    const queryClient = useQueryClient();
    return useMutation<unknown, Error, { type: "movie" | "series"; id: string; new_path: string }>({
        mutationFn: ({ type, id, new_path }) =>
            apiFetch(`/api/media/${type}/${id}/path`, {
                method: "PUT",
                body: JSON.stringify({ new_path }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", variables.type, variables.id] });
            queryClient.invalidateQueries({ queryKey: ["media"] });
        },
    });
}

// ── Suppression ──────────────────────────────────────────────

/**
 * Supprime un film / une série de Radarr/Sonarr.
 * Avant : appel apiFetch brut dans la page, sans invalidation (la médiathèque
 * affichait encore le média supprimé) et erreur réelle avalée.
 */
export function useDeleteMedia() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { type: "movie" | "series"; id: number | string; deleteFiles: boolean; deleteDownloads: boolean }
    >({
        mutationFn: ({ type, id, deleteFiles, deleteDownloads }) =>
            apiFetch(`/api/media/${type}/${id}?delete_files=${deleteFiles}&delete_downloads=${deleteDownloads}`, {
                method: "DELETE",
            }),
        onSuccess: (_data, variables) => {
            // Toute la médiathèque est marquée périmée SANS refetch immédiat :
            // re-demander la fiche supprimée afficherait une erreur 404 juste
            // avant la redirection. /media se rechargera à l'arrivée.
            queryClient.invalidateQueries({ queryKey: ["media"], refetchType: "none" });
            if (variables.deleteDownloads) queryClient.invalidateQueries({ queryKey: ["downloads"] });
            // Une fois la page quittée (requête inactive), on jette le cache de
            // la fiche pour ne jamais ré-afficher un média qui n'existe plus.
            const detailKey = ["media", "detail", variables.type, String(variables.id)];
            setTimeout(() => queryClient.removeQueries({ queryKey: detailKey, type: "inactive" }), 1500);
        },
    });
}

// ── Scraping NFO / illustrations (Radarr uniquement côté backend) ──

export function useScrapeMedia() {
    return useMutation<
        { status: string; items_count: number },
        Error,
        { movie_id: number; tmdb_id?: number; imdb_id?: string }
    >({
        // Le backend lance une tâche de fond et répond tout de suite :
        // un succès signifie « lancé », pas « terminé ».
        mutationFn: (item) =>
            apiFetch("/api/media/scrape", {
                method: "POST",
                body: JSON.stringify({ items: [{ ...item, source_service: "radarr" }] }),
            }),
    });
}

// ── Édition (surveillance / profil qualité / tags / …) ───────

export interface QualityProfileOption {
    id: number;
    name: string;
}

export interface TagOption {
    id: number;
    label: string;
}

export interface MediaEditOptions {
    quality_profiles: QualityProfileOption[];
    tags: TagOption[];
}

export function useMediaEditOptions(type: "movie" | "series", enabled: boolean) {
    return useQuery<MediaEditOptions>({
        queryKey: ["media", "options", type],
        queryFn: () => apiFetch(`/api/media/options/${type}`),
        enabled,
        staleTime: 300_000,
    });
}

export interface MediaEditPayload {
    monitored?: boolean;
    quality_profile_id?: number;
    tags?: number[];
    minimum_availability?: string;
    series_type?: string;
}

export function useUpdateMedia() {
    const queryClient = useQueryClient();
    return useMutation<unknown, Error, { type: "movie" | "series"; id: string | number; data: MediaEditPayload }>({
        mutationFn: ({ type, id, data }) =>
            apiFetch(`/api/media/${type}/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", variables.type, String(variables.id)] });
            queryClient.invalidateQueries({ queryKey: ["media"] });
        },
    });
}

export function useCreateTag() {
    const queryClient = useQueryClient();
    return useMutation<TagOption, Error, { type: "movie" | "series"; label: string }>({
        mutationFn: ({ type, label }) =>
            apiFetch(`/api/media/tag/${type}`, {
                method: "POST",
                body: JSON.stringify({ label }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "options", variables.type] });
        },
    });
}

/**
 * (Dé)surveillance d'une saison.
 * Mise à jour « optimiste » : l'interrupteur bascule immédiatement dans le
 * cache, et revient en arrière si Sonarr refuse (au lieu d'attendre 1-2 s).
 */
export function useUpdateSeasonMonitoring() {
    const queryClient = useQueryClient();
    return useMutation<
        unknown,
        Error,
        { id: string | number; season: number; monitored: boolean },
        { previous?: MediaDetail }
    >({
        mutationFn: ({ id, season, monitored }) =>
            apiFetch(`/api/media/series/${id}/season/${season}`, {
                method: "PATCH",
                body: JSON.stringify({ monitored }),
            }),
        onMutate: async ({ id, season, monitored }) => {
            const key = ["media", "detail", "series", String(id)];
            await queryClient.cancelQueries({ queryKey: key });
            const previous = queryClient.getQueryData<MediaDetail>(key);
            if (previous?.seasons) {
                queryClient.setQueryData<MediaDetail>(key, {
                    ...previous,
                    seasons: previous.seasons.map((s) => (s.season_number === season ? { ...s, monitored } : s)),
                });
            }
            return { previous };
        },
        onError: (_err, variables, context) => {
            if (context?.previous) {
                queryClient.setQueryData(["media", "detail", "series", String(variables.id)], context.previous);
            }
        },
        onSettled: (_data, _err, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", "series", String(variables.id)] });
        },
    });
}
