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

/** Réponse d'une action (recherche lancée, import lancé). */
export interface MusicActionResult {
    status: string;
    message: string;
}

/** Album resté dans le dossier de téléchargements, vu par Lidarr. */
export interface MusicDownloadAlbum {
    folder: string;
    name: string;
    artist: string | null;
    album: string | null;
    tracks: number;
    size_bytes: number;
    /** Reconnu par Lidarr : peut être importé. */
    ready: boolean;
    /** Sinon, pourquoi (mots de Lidarr). */
    reason: string | null;
}

/** Récupérer un album absent, ou les pistes manquantes d'un album partiel. */
export function useSearchAlbum() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (albumId: number) =>
            apiFetch<MusicActionResult>(`/api/music/albums/${albumId}/search`, { method: "POST" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["music", "artist"] }),
    });
}

/** Chercher tous les albums qui manquent à un artiste. */
export function useSearchArtist() {
    return useMutation({
        mutationFn: (artistId: number) =>
            apiFetch<MusicActionResult>(`/api/music/artists/${artistId}/search`, { method: "POST" }),
    });
}

/**
 * Musique restée dans les téléchargements (Lidarr passe le dossier en revue : lent).
 * `ignored` : dossiers de bonus de films écartés (bande originale rangée avec un film).
 */
export function useMusicDownloads(enabled = true) {
    return useQuery({
        queryKey: ["music", "downloads"],
        queryFn: () =>
            apiFetch<{ folders: string[]; albums: MusicDownloadAlbum[]; ignored?: number }>("/api/music/downloads"),
        enabled,
        staleTime: 60_000,
    });
}

/** Importer dans Lidarr un dossier d'album des téléchargements. */
export function useImportDownload() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (folder: string) =>
            apiFetch<MusicActionResult>("/api/music/downloads/import", {
                method: "POST",
                body: JSON.stringify({ folder }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["music", "downloads"] });
            qc.invalidateQueries({ queryKey: ["music", "artists"] });
        },
    });
}


/** Actualiser un artiste : discographie relue sur MusicBrainz, dossier relu sur le disque. */
export function useRefreshArtist() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (artistId: number) =>
            apiFetch<MusicActionResult>(`/api/music/artists/${artistId}/refresh`, { method: "POST" }),
        // Lidarr met quelques dizaines de secondes : on relit la fiche un peu plus tard
        onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["music", "artist"] }), 20_000),
    });
}

/** Release proposée par un indexeur pour un album (recherche manuelle). */
export interface AlbumRelease {
    guid: string;
    indexer_id: number;
    indexer: string;
    title: string;
    size_bytes: number;
    seeders: number | null;
    age_days: number;
    /** « FLAC », « MP3-320 »… */
    quality: string;
    protocol: string;
    /** Refusée par le profil de Lidarr (raisons dans `rejections`). */
    rejected: boolean;
    rejections: string[];
}

/** Recherche manuelle d'un album : lancée seulement quand on la demande (lente). */
export function useAlbumReleases(albumId: number, enabled: boolean) {
    return useQuery({
        queryKey: ["music", "releases", albumId],
        queryFn: () => apiFetch<{ items: AlbumRelease[]; total: number }>(`/api/music/albums/${albumId}/releases`),
        enabled,
        staleTime: 5 * 60_000,
        retry: false,
    });
}

/** Télécharger la release choisie (Lidarr l'envoie à SABnzbd puis l'importe). */
export function useGrabAlbumRelease() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ albumId, guid, indexerId }: { albumId: number; guid: string; indexerId: number }) =>
            apiFetch<MusicActionResult>(`/api/music/albums/${albumId}/grab`, {
                method: "POST",
                body: JSON.stringify({ guid, indexer_id: indexerId }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["music", "queue"] }),
    });
}
