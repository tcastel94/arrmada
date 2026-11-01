"use client";

/**
 * Musique (Lidarr + Jellyfin), voir docs/adr/015-musique-lidarr.md.
 * ----------------------------------------------------------------
 * Lidarr tient la bibliothèque (artistes suivis, albums présents ou
 * manquants, téléchargements) ; Jellyfin sert l'écoute. Les mêmes routes
 * /api/music servent la web app et l'appli TV.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Ce qui est prêt : Lidarr déclaré, bibliothèque « Musique » dans Jellyfin. */
export interface MusicStatus {
    lidarr: boolean;
    jellyfin: boolean;
    jellyfin_libraries: string[];
    ready: boolean;
    /** Conseil en clair quand quelque chose manque (null : tout est prêt). */
    hint: string | null;
}

export interface Artist {
    id: number;
    /** Identifiant MusicBrainz (lien avec Jellyfin). */
    mbid: string | null;
    name: string;
    overview: string | null;
    genres: string[];
    poster: string | null;
    fanart: string | null;
    albums: number;
    tracks_have: number;
    tracks_total: number;
    size_bytes: number;
    monitored: boolean;
}

export interface Album {
    id: number;
    mbid: string | null;
    title: string;
    year: number | null;
    /** « Album », « EP », « Single »… */
    type: string;
    cover: string | null;
    tracks_have: number;
    tracks_total: number;
    status: "complete" | "partial" | "missing";
    monitored: boolean;
}

export interface ArtistDetail extends Artist {
    album_list: Album[];
}

export interface ArtistHit {
    mbid: string;
    name: string;
    overview: string | null;
    /** « Person », « Group »… */
    type: string | null;
    genres: string[];
    poster: string | null;
    in_library: boolean;
}

export interface MusicDownload {
    id: number;
    title: string;
    status: string;
    /** 0 à 1. */
    progress: number;
    time_left: string | null;
}

export function useMusicStatus() {
    return useQuery({
        queryKey: ["music", "status"],
        queryFn: () => apiFetch<MusicStatus>("/api/music/status"),
        staleTime: 60_000,
    });
}

/** Artistes suivis ; rien n'est demandé tant que Lidarr n'est pas déclaré. */
export function useArtists(enabled = true) {
    return useQuery({
        queryKey: ["music", "artists"],
        queryFn: () => apiFetch<{ artists: Artist[]; total: number }>("/api/music/artists"),
        enabled,
    });
}

export function useArtist(id: number) {
    return useQuery({
        queryKey: ["music", "artist", id],
        queryFn: () => apiFetch<ArtistDetail>(`/api/music/artists/${id}`),
        enabled: Number.isFinite(id) && id > 0,
    });
}

/** Recherche d'artiste (MusicBrainz via Lidarr), à partir de 2 lettres. */
export function useArtistLookup(term: string) {
    const clean = term.trim();
    return useQuery({
        queryKey: ["music", "lookup", clean],
        queryFn: () =>
            apiFetch<{ results: ArtistHit[] }>(`/api/music/lookup?term=${encodeURIComponent(clean)}`),
        enabled: clean.length >= 2,
        staleTime: 5 * 60_000,
    });
}

/** Suivre un artiste : Lidarr cherche aussitôt ses albums. */
export function useAddArtist() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (mbid: string) =>
            apiFetch<Artist>("/api/music/artists", { method: "POST", body: JSON.stringify({ mbid }) }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["music", "artists"] });
            qc.invalidateQueries({ queryKey: ["music", "lookup"] });
            qc.invalidateQueries({ queryKey: ["music", "queue"] });
        },
    });
}

/** Albums en téléchargement, relus toutes les 15 s. */
export function useMusicQueue(enabled = true) {
    return useQuery({
        queryKey: ["music", "queue"],
        queryFn: () => apiFetch<{ items: MusicDownload[] }>("/api/music/queue"),
        refetchInterval: 15_000,
        enabled,
    });
}
