"use client";

/**
 * Calendrier des sorties (épisodes Sonarr + films Radarr).
 * ----------------------------------------------------------------
 * Deux usages :
 *   - `useCalendar(14)`                     → aujourd'hui → +14 j (dashboard)
 *   - `useCalendar(30, { start, end })`     → une fenêtre précise (mois affiché)
 * Avant, la page appelait toujours `useCalendar(90)` : le backend partait
 * d'aujourd'hui, donc tous les mois passés étaient vides.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Calendar ──────────────────────────────────────────────── */

export interface CalendarEntry {
    id: string;
    title: string;
    subtitle: string;
    type: "episode" | "movie";
    season?: number;
    episode?: number;
    label: string;
    /**
     * Épisode : date+heure de diffusion en UTC (« 2026-10-10T01:00:00Z ») →
     * à convertir en heure locale. Film : date « jour » (minuit UTC).
     */
    air_date: string;
    has_file: boolean;
    monitored: boolean;
    /** Peut valoir null côté API (type gardé tel quel pour ne pas casser les usages). */
    poster_url?: string;
    overview: string;
    service: string;
    service_type: string;
    /** Id Sonarr de la série (lien vers /media/series/{id}). */
    series_id?: number | null;
    /** Id Radarr du film (lien vers /media/movie/{id}). */
    movie_id?: number | null;
    /** Films : quelle sortie est affichée (numérique, physique, cinéma). */
    release_type?: "digital" | "physical" | "cinema" | null;
    genres?: string[];
    network?: string | null;
}

export interface CalendarResponse {
    start?: string;
    end?: string;
    items: CalendarEntry[];
    /** Regroupement par jour UTC (compat) — préférer un regroupement local. */
    by_date: Record<string, CalendarEntry[]>;
    total: number;
}

export interface CalendarRange {
    /** YYYY-MM-DD (date locale). */
    start: string;
    /** YYYY-MM-DD (date locale). */
    end: string;
    /** Inclure les éléments non surveillés (filtre « surveillés seulement »). */
    unmonitored?: boolean;
}

/**
 * Options de requête partagées (hook + préchargement du mois suivant /
 * précédent au survol des flèches) : même clé de cache, même URL.
 */
export function calendarQueryOptions(days = 30, range?: CalendarRange) {
    const qs = new URLSearchParams();
    if (range) {
        qs.set("start", range.start);
        qs.set("end", range.end);
        if (range.unmonitored) qs.set("unmonitored", "true");
    } else {
        qs.set("days", String(days));
    }
    return {
        queryKey: range ? ["calendar", "range", range.start, range.end, !!range.unmonitored] : ["calendar", days],
        queryFn: () => apiFetch<CalendarResponse>(`/api/calendar?${qs.toString()}`),
        staleTime: 300_000,
    };
}

export function useCalendar(days = 30, range?: CalendarRange) {
    return useQuery<CalendarResponse>({
        ...calendarQueryOptions(days, range),
        // Navigation de mois en mois : on garde l'ancien mois affiché pendant
        // le chargement du suivant (pas de « flash » de squelette).
        placeholderData: range ? keepPreviousData : undefined,
    });
}
