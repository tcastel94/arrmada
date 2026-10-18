"use client";

/**
 * Enrichissement des médias avec des infos venant d'AUTRES services :
 *  - Bazarr : sous-titres français présents / manquants
 *  - TV     : vu / en cours, partagés par les TV appairées (appli Kodi 1.19) :
 *             films (clé TMDB) ET séries (clé TVDB = `tmdb_id` d'une série) ;
 *             repli sur l'ancienne lecture directe d'un Kodi (films seulement)
 * Ces cartes couvrent toute la bibliothèque et sont mises en cache 30 s à
 * 1 min : on les télécharge une fois, puis chaque carte poster les consulte.
 */
import { useCallback } from "react";
import type { MediaItem } from "@/hooks/use-media";
import { useSubtitleStatus } from "@/hooks/use-subtitles";
import { useKodiWatchedStatus } from "@/hooks/use-kodi";
import { useWatchSummary } from "@/hooks/use-watch";

/** État des sous-titres FR d'un média (undefined = inconnu / Bazarr absent). */
export type SubState = "present" | "missing" | undefined;

/**
 * État de lecture (undefined = inconnu). `episodes` : épisodes vus d'une
 * série (badge « 12 ép. vus » tant qu'elle n'est pas finie).
 */
export type WatchState = { watched: boolean; progress: number | null; episodes?: number } | undefined;

export function useLibraryEnrichment() {
    const { data: subStatus } = useSubtitleStatus("fr");
    const { data: kodiWatched } = useKodiWatchedStatus();
    const { data: shared } = useWatchSummary();

    const subStateFor = useCallback(
        (item: MediaItem): SubState => {
            // Bazarr non configuré : les cartes sont vides. Avant, toutes les
            // séries avec fichier étaient alors marquées « ST FR ✓ » à tort.
            if (!subStatus?.available) return undefined;
            if (item.type === "movie") return subStatus.movies[item.external_id];
            // La carte des séries ne liste QUE celles à qui il manque des ST FR.
            if (subStatus.series[item.external_id]) return "missing";
            return item.has_file ? "present" : undefined;
        },
        [subStatus],
    );

    const watchStateFor = useCallback(
        (item: MediaItem): WatchState => {
            if (!item.tmdb_id) return undefined;
            const key = String(item.tmdb_id);
            // 1. Vu partagé par les TV (films et séries)
            if (item.type === "series") {
                const series = shared?.series[key];
                if (!series || (!series.watched_episodes && !series.in_progress)) return undefined;
                const have = item.episodes_have ?? 0;
                const done = have > 0 && series.watched_episodes >= have;
                return { watched: done, progress: null, episodes: done ? undefined : series.watched_episodes };
            }
            const movie = shared?.movies[key];
            if (movie) return { watched: movie.watched, progress: movie.watched ? null : movie.progress };
            // 2. Repli : lecture directe d'un Kodi configuré (films seulement)
            if (!kodiWatched) return undefined;
            const entry = kodiWatched[key];
            if (!entry) return undefined;
            const progress =
                entry.resume_position > 0 && entry.resume_total > 0
                    ? Math.round((entry.resume_position / entry.resume_total) * 100)
                    : null;
            return { watched: entry.playcount > 0, progress };
        },
        [kodiWatched, shared],
    );

    return {
        subStateFor,
        watchStateFor,
        /** Bazarr répond : le filtre « ST FR » a un sens. */
        subtitlesAvailable: !!subStatus?.available,
        /** Vu partagé ou Kodi lisible : le filtre « Vu » a un sens. */
        kodiAvailable: !!kodiWatched || !!shared,
    };
}
