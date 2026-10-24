"use client";

/**
 * Séries maison : un dossier vidéo affiché comme une série dans l'appli.
 * ----------------------------------------------------------------
 * Pour les montages de fans sans fiche officielle (Naruto Kai, One Pace…) :
 * sous-dossiers = saisons (arcs), vidéos = épisodes. L'affiche, le fond et
 * le résumé viennent de la série officielle choisie sur TMDB, ou des
 * poster.jpg / tvshow.nfo posés dans le dossier.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, getToken } from "@/lib/api-client";
import { API_URL } from "@/lib/constants";

export interface LocalSeries {
    id: number;
    title: string;
    /** Pastille affichée sur la TV (« Kai », « Fan edit »). */
    badge: string;
    year: number | null;
    overview: string | null;
    poster_url: string | null;
    fanart_url: string | null;
    seasons: number;
    episodes: number;
    /** Dossier présent sur le NAS. */
    available: boolean;
    root_id: number;
    /** Chemin du dossier, relatif au dossier vidéo. */
    path: string;
    tmdb_id: number | null;
}

export interface LocalSeriesInput {
    root_id?: number;
    path?: string;
    title?: string;
    badge?: string;
    tmdb_id?: number | null;
}

export interface TmdbSeriesHit {
    tmdb_id: number;
    title: string;
    year: string | null;
    poster_url: string | null;
}

/** Contenu d'un dossier de l'écran Vidéos (sélecteur de dossier). */
export interface VideoListing {
    title: string;
    crumbs: { name: string; token: string }[];
    folders: { name: string; token: string; available?: boolean }[];
    files: { name: string }[];
}

/** Épisode d'une série maison, avec son vu / sa reprise (fiche de la web app). */
export interface LocalEpisode {
    season_number: number;
    episode_number: number;
    title: string;
    overview: string | null;
    air_date: string | null;
    /** Jeton du fichier : la TV le lit avec (« Sur la TV »). */
    token: string;
    /** Empreinte du chemin : clé du vu / de la reprise partagés. */
    watch_id: string;
    image: string | null;
    state?: { watched: boolean; position: number; total: number } | null;
}

export interface LocalSeason {
    season_number: number;
    /** Nom du dossier de l'arc (« Arc 02 - Examen Chunin »). */
    name: string;
    episodes: LocalEpisode[];
}

/** Fiche : comme la grille, mais `seasons` liste les arcs (et non leur nombre). */
export interface LocalSeriesDetail extends Omit<LocalSeries, "seasons"> {
    seasons: LocalSeason[];
}

const LOCAL_SERIES_KEY = ["local-series"] as const;

/**
 * Image d'une série maison : TMDB (adresse complète) telle quelle ; image du
 * NAS (« /api/videos/image/… ») servie par le serveur, jeton dans l'adresse
 * (une balise <img> ne sait pas envoyer d'en-tête, comme le flux temps réel).
 */
export function localImage(url: string | null | undefined): string | null {
    if (!url) return null;
    if (!url.startsWith("/api/")) return url;
    const token = getToken();
    return `${API_URL}${url}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

/** Fiche d'une série maison, avec le vu / la reprise de chaque épisode. */
export function useLocalSeriesDetail(id: number | null) {
    return useQuery<LocalSeriesDetail>({
        queryKey: ["local-series", id],
        queryFn: () => apiFetch(`/api/videos/series/${id}?states=true`),
        enabled: id !== null && id > 0,
    });
}

/**
 * Épisode à proposer : celui commencé, sinon le premier non vu après le
 * dernier vu, sinon le premier (série revue depuis le début).
 */
export function nextLocalEpisode(detail: Pick<LocalSeriesDetail, "seasons">): LocalEpisode | null {
    const episodes = detail.seasons.flatMap((s) => s.episodes);
    const started = episodes.find((e) => e.state && !e.state.watched && e.state.position > 0);
    if (started) return started;
    const lastWatched = episodes.reduce((last, e, i) => (e.state?.watched ? i : last), -1);
    return episodes.slice(lastWatched + 1).find((e) => !e.state?.watched) ?? episodes[0] ?? null;
}

/** Jeton de l'écran Vidéos (« n° du dossier / chemin » en base64 d'URL) → dossier et chemin. */
export function decodeVideoToken(token: string): { rootId: number; path: string } {
    const base64 = token.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (token.length % 4)) % 4);
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const text = new TextDecoder().decode(bytes);
    const slash = text.indexOf("/");
    return { rootId: Number(text.slice(0, slash)), path: text.slice(slash + 1) };
}

export function useLocalSeries() {
    return useQuery<LocalSeries[]>({
        queryKey: LOCAL_SERIES_KEY,
        queryFn: async () => (await apiFetch<{ items: LocalSeries[] }>("/api/videos/series")).items,
    });
}

export function useVideoListing(token: string | null) {
    return useQuery<VideoListing>({
        queryKey: ["video-listing", token ?? ""],
        queryFn: () => apiFetch(`/api/videos/browse${token ? `?path=${encodeURIComponent(token)}` : ""}`),
    });
}

export function useTmdbSeriesSearch(query: string) {
    return useQuery<TmdbSeriesHit[]>({
        queryKey: ["tmdb-series-search", query],
        queryFn: async () =>
            (await apiFetch<{ items: TmdbSeriesHit[] }>(`/api/videos/series/tmdb/search?q=${encodeURIComponent(query)}`)).items,
        enabled: query.trim().length >= 2,
        retry: false,
    });
}

export function useCreateLocalSeries() {
    const qc = useQueryClient();
    return useMutation<LocalSeries, Error, LocalSeriesInput>({
        mutationFn: (body) => apiFetch("/api/videos/series", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: LOCAL_SERIES_KEY }),
    });
}

export function useUpdateLocalSeries() {
    const qc = useQueryClient();
    return useMutation<LocalSeries, Error, { id: number } & LocalSeriesInput>({
        mutationFn: ({ id, ...body }) => apiFetch(`/api/videos/series/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: LOCAL_SERIES_KEY }),
    });
}

export function useDeleteLocalSeries() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/videos/series/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: LOCAL_SERIES_KEY }),
    });
}
