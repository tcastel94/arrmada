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
import { apiFetch } from "@/lib/api-client";

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

const LOCAL_SERIES_KEY = ["local-series"] as const;

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
