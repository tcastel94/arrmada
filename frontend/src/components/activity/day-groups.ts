/**
 * Regroupement par JOUR LOCAL (« Aujourd'hui », « Hier », « mardi 7 oct. »).
 * ----------------------------------------------------------------
 * Partagé par le Journal, les Notifications et le Calendrier.
 * Point clé : les clés de jour sont construites en HEURE LOCALE
 * (getFullYear/getMonth/getDate) et jamais avec toISOString(), qui renvoie
 * la date UTC — à Paris, tout ce qui se passe entre minuit et 2 h du matin
 * tombait sinon dans la journée de la veille.
 */

/** Clé « YYYY-MM-DD » d'une date, en heure locale. */
export function localDayKey(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

/** Inverse de localDayKey : « 2026-10-10 » → Date à minuit LOCAL. */
export function parseDayKey(key: string): Date {
    const [y, m, d] = key.split("-").map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
}

/** Décale une date d'un nombre de jours (en restant à minuit local). */
export function addDays(d: Date, n: number): Date {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Libellé humain d'un jour : « Aujourd'hui », « Hier », « Demain », sinon
 * « Mardi 7 octobre » (+ l'année si ce n'est pas l'année en cours).
 */
export function dayLabel(d: Date, now = new Date()): string {
    const key = localDayKey(d);
    if (key === localDayKey(now)) return "Aujourd'hui";
    if (key === localDayKey(addDays(now, -1))) return "Hier";
    if (key === localDayKey(addDays(now, 1))) return "Demain";
    const sameYear = d.getFullYear() === now.getFullYear();
    return capitalize(
        d.toLocaleDateString("fr-FR", {
            weekday: "long",
            day: "numeric",
            month: "long",
            ...(sameYear ? {} : { year: "numeric" }),
        }),
    );
}

export interface DayGroup<T> {
    key: string;
    date: Date;
    label: string;
    items: T[];
}

/**
 * Regroupe une liste (déjà triée) par jour local, en conservant l'ordre.
 * Les éléments sans date valide sont ignorés.
 */
export function groupByDay<T>(items: T[], getDate: (item: T) => Date | null): DayGroup<T>[] {
    const groups: DayGroup<T>[] = [];
    const index = new Map<string, DayGroup<T>>();
    const now = new Date();
    for (const item of items) {
        const d = getDate(item);
        if (!d) continue;
        const key = localDayKey(d);
        let g = index.get(key);
        if (!g) {
            g = { key, date: d, label: dayLabel(d, now), items: [] };
            index.set(key, g);
            groups.push(g);
        }
        g.items.push(item);
    }
    return groups;
}

/** Heure locale « 21:05 ». */
export function formatTime(d: Date): string {
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
