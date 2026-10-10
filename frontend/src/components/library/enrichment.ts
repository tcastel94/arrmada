"use client";

/**
 * Enrichissement des médias avec des infos venant d'AUTRES services :
 *  - Bazarr : sous-titres français présents / manquants
 *  - Kodi   : vu / en cours de lecture (films uniquement, clé = ID TMDB)
 * Ces deux cartes couvrent toute la bibliothèque et sont mises en cache
 * 1 min : on les télécharge une fois, puis chaque carte poster les consulte.
 */
import { useCallback } from "react";
import type { MediaItem } from "@/hooks/use-media";
import { useSubtitleStatus } from "@/hooks/use-subtitles";
import { useKodiWatchedStatus } from "@/hooks/use-kodi";

/** État des sous-titres FR d'un média (undefined = inconnu / Bazarr absent). */
export type SubState = "present" | "missing" | undefined;

/** État de lecture Kodi (undefined = inconnu ou série). */
export type WatchState = { watched: boolean; progress: number | null } | undefined;

export function useLibraryEnrichment() {
    const { data: subStatus } = useSubtitleStatus("fr");
    const { data: kodiWatched } = useKodiWatchedStatus();

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
            if (!kodiWatched || item.type !== "movie" || !item.tmdb_id) return undefined;
            const entry = kodiWatched[String(item.tmdb_id)];
            if (!entry) return undefined;
            const progress =
                entry.resume_position > 0 && entry.resume_total > 0
                    ? Math.round((entry.resume_position / entry.resume_total) * 100)
                    : null;
            return { watched: entry.playcount > 0, progress };
        },
        [kodiWatched],
    );

    return {
        subStateFor,
        watchStateFor,
        /** Bazarr répond : le filtre « ST FR » a un sens. */
        subtitlesAvailable: !!subStatus?.available,
        /** Kodi répond : le filtre « Vu » a un sens. */
        kodiAvailable: !!kodiWatched,
    };
}
