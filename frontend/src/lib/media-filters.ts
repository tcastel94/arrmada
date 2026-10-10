/**
 * Persistence helpers for the media library filters.
 *
 * - Session storage keeps the *current* filter set alive across navigation
 *   (click a media → back → filters still applied). Cleared when the tab/session
 *   ends, so a fresh visit later starts clean.
 * - Local storage holds named presets the user explicitly saves.
 */

export interface MediaFilters {
    type: string;
    search: string;
    sort: string;
    order: string;
    subFilter: string;
    genre: string;
    quality: string;
    availability: string;
    monitored: string;
    watchFilter: string;
}

export interface FilterPreset {
    name: string;
    filters: MediaFilters;
}

const SESSION_KEY = "arrmada:media-filters";
const PRESETS_KEY = "arrmada:media-filter-presets";

export function loadSessionFilters(): Partial<MediaFilters> {
    if (typeof window === "undefined") return {};
    try {
        return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "{}");
    } catch {
        return {};
    }
}

export function saveSessionFilters(f: MediaFilters): void {
    if (typeof window === "undefined") return;
    try {
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(f));
    } catch {
        /* storage full / disabled — ignore */
    }
}

export function loadPresets(): FilterPreset[] {
    if (typeof window === "undefined") return [];
    try {
        const p = JSON.parse(localStorage.getItem(PRESETS_KEY) || "[]");
        return Array.isArray(p) ? p : [];
    } catch {
        return [];
    }
}

export function savePresets(presets: FilterPreset[]): void {
    if (typeof window === "undefined") return;
    try {
        localStorage.setItem(PRESETS_KEY, JSON.stringify(presets));
    } catch {
        /* ignore */
    }
}
