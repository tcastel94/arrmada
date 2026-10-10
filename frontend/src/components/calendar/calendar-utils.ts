/**
 * Outils de dates du calendrier — TOUT en heure locale.
 * ----------------------------------------------------------------
 * Bug corrigé : l'ancienne page construisait les jours à minuit LOCAL puis
 * les convertissait en clé avec toISOString() (UTC). À Paris (UTC+1/+2),
 * minuit local = 22 h/23 h la veille en UTC → chaque case affichait les
 * sorties du jour précédent et « aujourd'hui » était faux.
 * Ici, les clés « YYYY-MM-DD » sont construites avec getFullYear/getMonth/
 * getDate, et l'heure UTC de diffusion des épisodes est convertie en heure
 * locale AVANT d'en extraire le jour.
 */
import type { CalendarEntry } from "@/hooks/use-calendar";
import { parseApiDate } from "@/lib/format";
import { addDays, formatTime, localDayKey, parseDayKey } from "@/components/activity/day-groups";

export { addDays, localDayKey, parseDayKey };

export const WEEKDAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
export const WEEKDAYS_LONG = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];

/** « 2026-10 » pour le 1er du mois de `d`. */
export function monthKey(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** « 2026-10 » → 1er octobre 2026 à minuit local (null si invalide). */
export function parseMonthKey(value: string | null | undefined): Date | null {
    const m = /^(\d{4})-(\d{2})$/.exec(value ?? "");
    if (!m) return null;
    const month = Number(m[2]);
    if (month < 1 || month > 12) return null;
    return new Date(Number(m[1]), month - 1, 1);
}

export function startOfMonth(d: Date): Date {
    return new Date(d.getFullYear(), d.getMonth(), 1);
}

/** « octobre 2026 » → « Octobre 2026 ». */
export function monthTitle(d: Date): string {
    const s = d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
    return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Jours affichés dans la grille d'un mois : du lundi qui précède (ou égale)
 * le 1er jusqu'au dimanche qui suit (ou égale) le dernier jour → 5 ou 6
 * semaines complètes, semaines débordantes incluses.
 */
export function monthGrid(month: Date): Date[] {
    const first = startOfMonth(month);
    const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
    const lead = (first.getDay() + 6) % 7; // lundi = 0
    const trail = 6 - ((last.getDay() + 6) % 7);
    const start = addDays(first, -lead);
    const total = lead + last.getDate() + trail;
    return Array.from({ length: total }, (_, i) => addDays(start, i));
}

/** L'élément a-t-il une heure de diffusion précise ? (épisodes Sonarr) */
export function hasAirTime(e: CalendarEntry): boolean {
    return e.type === "episode" && !!e.air_date && e.air_date.includes("T");
}

/**
 * Date LOCALE de sortie d'un élément.
 *  - épisode : « 2026-10-10T01:00:00Z » = 03:00 à Paris → converti en local ;
 *  - film    : date « jour » (cinéma / numérique) envoyée à minuit UTC → on
 *    garde la date telle quelle (la convertir la ferait reculer d'un jour
 *    sur le continent américain).
 */
export function entryDate(e: CalendarEntry): Date | null {
    const raw = e.air_date;
    if (!raw) return null;
    if (e.type === "movie" || /^\d{4}-\d{2}-\d{2}$/.test(raw)) return parseDayKey(raw.slice(0, 10));
    return parseApiDate(raw);
}

export function entryDayKey(e: CalendarEntry): string | null {
    const d = entryDate(e);
    return d ? localDayKey(d) : null;
}

/** Heure locale de diffusion (« 21:00 ») pour les épisodes, sinon null. */
export function entryTime(e: CalendarEntry): string | null {
    if (!hasAirTime(e)) return null;
    const d = entryDate(e);
    return d ? formatTime(d) : null;
}

/** « S01E02 » (calculé si le label est absent). */
export function entryCode(e: CalendarEntry): string {
    if (e.type !== "episode") return e.label;
    if (typeof e.season === "number" && typeof e.episode === "number") {
        return `S${String(e.season).padStart(2, "0")}E${String(e.episode).padStart(2, "0")}`;
    }
    return e.label;
}

/** Lien vers la fiche média (ids Sonarr / Radarr renvoyés par le backend). */
export function entryHref(e: CalendarEntry): string | null {
    if (e.type === "episode" && e.series_id) return `/media/series/${e.series_id}`;
    if (e.type === "movie" && e.movie_id) return `/media/movie/${e.movie_id}`;
    return null;
}

export const RELEASE_LABELS: Record<string, string> = {
    digital: "Sortie numérique",
    physical: "Sortie Blu-ray / DVD",
    cinema: "Sortie cinéma",
};

/**
 * Regroupe les éléments par jour local, triés par heure puis par titre.
 * Remplace le `by_date` du backend, calculé en UTC.
 */
export function groupEntriesByDay(entries: CalendarEntry[]): Map<string, CalendarEntry[]> {
    const map = new Map<string, CalendarEntry[]>();
    for (const e of entries) {
        const key = entryDayKey(e);
        if (!key) continue;
        const list = map.get(key);
        if (list) list.push(e);
        else map.set(key, [e]);
    }
    map.forEach((list) =>
        list.sort((a, b) => {
            const ta = entryDate(a)?.getTime() ?? 0;
            const tb = entryDate(b)?.getTime() ?? 0;
            return ta - tb || a.title.localeCompare(b.title, "fr");
        }),
    );
    return map;
}

export type TypeFilter = "all" | "episode" | "movie";

/** Filtres du calendrier : type (séries / films) et « surveillés seulement ». */
export function matchesFilters(e: CalendarEntry, type: TypeFilter, monitoredOnly: boolean): boolean {
    if (type !== "all" && e.type !== type) return false;
    if (monitoredOnly && !e.monitored) return false;
    return true;
}
