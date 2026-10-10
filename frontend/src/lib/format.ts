/**
 * Helpers de formatage partagés (FR).
 * ----------------------------------------------------------------
 * Avant : chaque page redéfinissait sa propre fonction formatBytes /
 * timeAgo, avec des résultats différents ("1.5 GB" vs "1,5 Go", "2h" vs
 * "Il y a 2h"…). Tout passe désormais par ce module unique.
 */

const NUMBER_FR = new Intl.NumberFormat("fr-FR");

/** Nombre formaté à la française : 12 345. */
export function formatNumber(n: number | null | undefined): string {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    return NUMBER_FR.format(n);
}

/** Taille lisible en unités binaires : 1,5 Go, 820 Mo… ("—" si vide). */
export function formatBytes(bytes: number | null | undefined, decimals = 1): string {
    if (!bytes || bytes <= 0) return "—";
    const k = 1024;
    const units = ["o", "Ko", "Mo", "Go", "To", "Po"];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1);
    const value = bytes / Math.pow(k, i);
    return `${value.toLocaleString("fr-FR", { maximumFractionDigits: i < 2 ? 0 : decimals })} ${units[i]}`;
}

/** Débit lisible : 12,4 Mo/s. */
export function formatSpeed(bytesPerSecond: number | null | undefined): string {
    if (!bytesPerSecond || bytesPerSecond <= 0) return "—";
    return `${formatBytes(bytesPerSecond)}/s`;
}

/** Durée en secondes → "1 h 42" / "12 min" / "45 s". */
export function formatDuration(seconds: number | null | undefined): string {
    if (!seconds || seconds <= 0) return "—";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h} h ${String(m).padStart(2, "0")}`;
    if (m > 0) return `${m} min`;
    return `${s} s`;
}

/** Position de lecture "1:02:33" / "42:07". */
export function formatClock(seconds: number | null | undefined): string {
    if (!seconds || seconds < 0) return "0:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
    return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

/**
 * Parse une date venant de l'API.
 * Le backend renvoie parfois des ISO « naïfs » (sans fuseau) qui sont en
 * réalité de l'UTC : sans correction, le navigateur les lit en heure locale
 * et tout est décalé d'1-2 h ("il y a 2 h" pour un événement d'il y a 2 min).
 */
export function parseApiDate(value: string | number | Date | null | undefined): Date | null {
    if (value === null || value === undefined || value === "") return null;
    if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
    if (typeof value === "number") return new Date(value);
    let v = value.trim();
    // "2025-01-02 10:00:00" → "2025-01-02T10:00:00"
    if (/^\d{4}-\d{2}-\d{2} \d/.test(v)) v = v.replace(" ", "T");
    // Date+heure sans Z ni offset → on la considère UTC.
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(v)) v += "Z";
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? null : d;
}

/** "À l'instant", "il y a 5 min", "il y a 3 h", "hier", "il y a 4 j", "12 mars". */
export function timeAgo(value: string | number | Date | null | undefined, opts: { short?: boolean } = {}): string {
    const d = parseApiDate(value);
    if (!d) return "";
    const diff = Math.round((Date.now() - d.getTime()) / 1000);
    const short = opts.short ?? false;
    if (diff < 0) return formatShortDate(d);
    if (diff < 45) return "À l'instant";
    if (diff < 3600) {
        const m = Math.max(1, Math.round(diff / 60));
        return short ? `${m} min` : `il y a ${m} min`;
    }
    if (diff < 86400) {
        const h = Math.round(diff / 3600);
        return short ? `${h} h` : `il y a ${h} h`;
    }
    const days = Math.floor(diff / 86400);
    if (days === 1) return "hier";
    if (days < 7) return short ? `${days} j` : `il y a ${days} j`;
    return formatShortDate(d);
}

/** "12 mars" (ou "12 mars 2023" si autre année). */
export function formatShortDate(value: string | number | Date | null | undefined): string {
    const d = parseApiDate(value);
    if (!d) return "";
    const sameYear = d.getFullYear() === new Date().getFullYear();
    return d.toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        ...(sameYear ? {} : { year: "numeric" }),
    });
}

/** "mardi 12 mars à 21:00". */
export function formatLongDateTime(value: string | number | Date | null | undefined): string {
    const d = parseApiDate(value);
    if (!d) return "";
    return d.toLocaleString("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
    });
}

/** Pluriel simple : plural(3, "film") → "3 films". */
export function plural(n: number, singular: string, pluralForm?: string): string {
    return `${formatNumber(n)} ${n > 1 ? pluralForm ?? `${singular}s` : singular}`;
}

/** Pourcentage borné 0-100 (protège les divisions par zéro). */
export function percent(part: number | null | undefined, total: number | null | undefined): number {
    if (!part || !total || total <= 0) return 0;
    return Math.max(0, Math.min(100, (part / total) * 100));
}

/** Salutation selon l'heure : Bonjour / Bon après-midi / Bonsoir / Bonne nuit. */
export function greeting(date = new Date()): string {
    const h = date.getHours();
    if (h < 5) return "Bonne nuit";
    if (h < 12) return "Bonjour";
    if (h < 18) return "Bon après-midi";
    return "Bonsoir";
}
