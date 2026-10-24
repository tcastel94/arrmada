"use client";

/**
 * Vu / reprise partagés par les TV, vus depuis la web app (add-on Kodi 1.19.0).
 * ----------------------------------------------------------------
 * Les TV appairées déposent sur le serveur ce qu'elles ont vu et où elles
 * se sont arrêtées (table `watch_states`). La web app en tire :
 *  - les badges « Vu » / « ⏵ 27 % » / « 12 ép. vus » de la médiathèque ;
 *  - la page Reprendre ;
 *  - « Lire sur la TV » : le serveur publie une demande que SEULE la TV
 *    choisie exécute (événement `play_request`, relevé par la TV en 5 s).
 * Rien n'est demandé à Kodi : ça marche même TV éteintes (sauf la lecture !).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { useDevices, type PairedDevice } from "@/hooks/use-devices";

/** Film : clé TMDB. */
export interface WatchMovieState {
    watched: boolean;
    position: number; // secondes
    total: number; // secondes
    /** Avancement 1-99 %, null si pas commencé ou déjà vu. */
    progress: number | null;
    /** TV qui a fait le dernier geste (« Shield Salon »). */
    device: string;
    updated_at: string;
}

/** Dernier épisode touché d'une série. */
export interface WatchEpisodeRef {
    season: number;
    episode: number;
    watched: boolean;
    position: number;
    total: number;
    device: string;
    updated_at: string;
}

/** Série : clé TVDB (celle de Sonarr, aussi dans `MediaItem.tmdb_id` des séries). */
export interface WatchSeriesState {
    watched_episodes: number;
    in_progress: number;
    last: WatchEpisodeRef | null;
}

/** Ligne de la page Reprendre. */
export interface ContinueRow {
    media_type: "movie" | "episode";
    id_type: string;
    id: string;
    season: number | null;
    episode: number | null;
    title: string;
    year: number | null;
    poster_url: string | null;
    fanart_url: string | null;
    /** Fiche : /media/<media_kind>/<media_id> (null si le titre n'est plus dans Radarr / Sonarr). */
    media_kind: "movie" | "series" | null;
    media_id: string | null;
    position: number;
    total: number;
    progress: number | null;
    device: string;
    updated_at: string;
}

export interface WatchSummary {
    movies: Record<string, WatchMovieState>;
    series: Record<string, WatchSeriesState>;
    continue: ContinueRow[];
}

export const WATCH_SUMMARY_KEY = ["kodi", "watch-summary"] as const;

export function useWatchSummary(enabled = true) {
    return useQuery<WatchSummary>({
        queryKey: WATCH_SUMMARY_KEY,
        queryFn: () => apiFetch("/api/kodi/watch-summary"),
        enabled,
        // Rafraîchi aussi en direct par l'événement `watch_state` (use-sse.ts)
        staleTime: 30_000,
    });
}

/* ── Lire sur une TV appairée ───────────────────────────────── */

/** Titre à lancer, désigné comme dans le vu partagé (la TV le cherche dans SA médiathèque). */
export interface PlayTarget {
    /** « file » : vidéo d'une série maison (Naruto Kai…), lue par son jeton. */
    media_type: "movie" | "episode" | "file";
    /** TMDB d'un film, TVDB d'une série ; empreinte (sha1) d'une vidéo. */
    id: string | number;
    id_type?: "tmdb" | "tvdb" | "sha1";
    season?: number | null;
    episode?: number | null;
    title?: string;
    /** Vidéo : jeton du fichier (écran Vidéos), série maison, reprise (s). */
    file?: string;
    local_series?: number;
    start?: number;
}

export interface PlayOnDeviceResult {
    status: "sent";
    device: string;
    /** Faux : la TV ne s'est pas manifestée récemment (éteinte ?). */
    online: boolean;
    request_id: string;
}

export function usePlayOnDevice() {
    return useMutation<PlayOnDeviceResult, Error, PlayTarget & { device_id: number; resume?: boolean }>({
        mutationFn: (body) =>
            apiFetch("/api/kodi/play-on-device", { method: "POST", body: JSON.stringify(body) }),
    });
}

/** TV appairées (pas les écrans d'appoint), triées par nom. */
export function useTvDevices(): PairedDevice[] {
    const { data } = useDevices();
    return (data ?? []).filter((d) => d.kind === "tv").sort((a, b) => a.name.localeCompare(b.name, "fr"));
}

/** « S02E05 » */
export function episodeCode(season?: number | null, episode?: number | null): string {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `S${pad(season ?? 0)}E${pad(episode ?? 0)}`;
}

/** 2530 → « 42:10 », 5025 → « 1:23:45 ». */
export function clockLabel(seconds: number): string {
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
