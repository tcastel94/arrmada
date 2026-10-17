/**
 * Filtres de la médiathèque (/media) et « filtres enregistrés ».
 * ----------------------------------------------------------------
 * L'état COURANT des filtres vit dans l'URL (?type=…&genre=…, voir
 * components/library/use-param-state) : le retour arrière depuis une fiche
 * et les liens partagés fonctionnent sans rien stocker. L'ancienne
 * persistance en sessionStorage n'a donc plus lieu d'être.
 *
 * Ce module apporte :
 *  1. les valeurs autorisées de chaque filtre et leurs libellés FR, partagés
 *     par la page (listes, chips) et par le menu des préréglages ;
 *  2. les PRÉRÉGLAGES nommés (« Films 4K non vus »…), enregistrés dans le
 *     navigateur (localStorage) : un préréglage n'est qu'un instantané des
 *     paramètres d'URL ; l'appliquer réécrit l'URL.
 *
 * Tous les accès au stockage sont protégés (navigation privée, quota plein,
 * stockage désactivé) : au pire, la liste est vide et rien n'est enregistré.
 */
import { translateGenre } from "@/lib/genres";

/* ════════════════════════════════════════════════════════════════
   Valeurs autorisées + libellés
   ════════════════════════════════════════════════════════════════ */

export const MEDIA_TYPES = ["all", "movie", "series"] as const;
export const MEDIA_SORTS = ["title", "year", "added", "size_bytes"] as const;
export const MEDIA_ORDERS = ["asc", "desc"] as const;
export const MEDIA_AVAILS = ["all", "available", "missing"] as const;
export const MEDIA_MONITORS = ["all", "yes", "no"] as const;
export const MEDIA_SUBS = ["all", "missing", "present"] as const;
export const MEDIA_WATCHES = ["all", "watched", "unwatched", "inprogress"] as const;

export type MediaTypeFilter = (typeof MEDIA_TYPES)[number];
export type MediaSort = (typeof MEDIA_SORTS)[number];
export type MediaAvail = (typeof MEDIA_AVAILS)[number];
export type MediaMonitor = (typeof MEDIA_MONITORS)[number];
export type MediaSub = (typeof MEDIA_SUBS)[number];
export type MediaWatch = (typeof MEDIA_WATCHES)[number];

export const TYPE_LABELS: Record<MediaTypeFilter, string> = { all: "Tout", movie: "Films", series: "Séries" };
export const SORT_LABELS: Record<MediaSort, string> = {
    title: "Titre",
    year: "Année",
    added: "Date d'ajout",
    size_bytes: "Taille",
};
export const AVAIL_LABELS: Record<MediaAvail, string> = { all: "Tous", available: "Présents", missing: "Manquants" };
export const MONITOR_LABELS: Record<MediaMonitor, string> = { all: "Tous", yes: "Surveillés", no: "Non surveillés" };
export const SUB_LABELS: Record<MediaSub, string> = { all: "Tous", missing: "Sans ST FR", present: "Avec ST FR" };
export const WATCH_LABELS: Record<MediaWatch, string> = {
    all: "Tous",
    watched: "Vus",
    unwatched: "Non vus",
    inprogress: "En cours",
};

/** `[{ value, label }]` pour une liste déroulante, dans l'ordre des valeurs. */
export function choicesOf<T extends string>(values: readonly T[], labels: Record<T, string>) {
    return values.map((value) => ({ value, label: labels[value] }));
}

/* ════════════════════════════════════════════════════════════════
   Jeu de filtres = paramètres d'URL
   ════════════════════════════════════════════════════════════════ */

/**
 * Paramètres d'URL qui composent un jeu de filtres. La page (`page`) et
 * l'affichage (`view` grille/liste) n'en font volontairement pas partie :
 * appliquer un préréglage ne doit pas changer ta façon de regarder la liste.
 */
export const PRESET_KEYS = ["q", "type", "sort", "order", "genre", "quality", "avail", "mon", "sub", "watch"] as const;
export type PresetKey = (typeof PRESET_KEYS)[number];

/** Jeu de filtres « compact » : seules les valeurs différentes du défaut sont présentes. */
export type PresetParams = Partial<Record<PresetKey, string>>;

const DEFAULTS: Record<PresetKey, string> = {
    q: "",
    type: "all",
    sort: "title",
    order: "asc",
    genre: "all",
    quality: "all",
    avail: "all",
    mon: "all",
    sub: "all",
    watch: "all",
};

/** Listes fermées ; genre, qualité et recherche sont libres (dépendent de ta bibliothèque). */
const ALLOWED: Partial<Record<PresetKey, readonly string[]>> = {
    type: MEDIA_TYPES,
    sort: MEDIA_SORTS,
    order: MEDIA_ORDERS,
    avail: MEDIA_AVAILS,
    mon: MEDIA_MONITORS,
    sub: MEDIA_SUBS,
    watch: MEDIA_WATCHES,
};

/** Retire les valeurs vides, par défaut ou inconnues (préréglage ancien ou modifié à la main). */
export function normalizeParams(raw: Partial<Record<string, unknown>>): PresetParams {
    const out: PresetParams = {};
    for (const key of PRESET_KEYS) {
        const value = raw[key];
        if (typeof value !== "string") continue;
        const v = value.trim();
        if (!v || v === DEFAULTS[key]) continue;
        const allowed = ALLOWED[key];
        if (allowed && !allowed.includes(v)) continue;
        out[key] = v;
    }
    return out;
}

/**
 * Instantané des filtres courants à partir de l'URL. Accepte
 * `useSearchParams()` comme `URLSearchParams`. `?search=` (ancien lien de
 * la palette ⌘K) compte comme la recherche `q`.
 */
export function paramsFromSearch(search: { get(name: string): string | null }): PresetParams {
    const raw: Record<string, string> = {};
    for (const key of PRESET_KEYS) {
        const v = search.get(key);
        if (v !== null) raw[key] = v;
    }
    if (!raw.q) raw.q = search.get("search") ?? "";
    return normalizeParams(raw);
}

/**
 * Mises à jour d'URL (pour `writeParams`) qui appliquent un jeu de filtres :
 * CHAQUE clé est réécrite (absente du préréglage = remise à zéro), l'ancien
 * `?search=` est retiré et on revient en page 1.
 */
export function presetUpdates(params: PresetParams): Record<string, string | null> {
    const updates: Record<string, string | null> = { search: null, page: null };
    for (const key of PRESET_KEYS) updates[key] = params[key] ?? null;
    return updates;
}

/** Deux jeux de filtres identiques ? (sert à repérer le préréglage actif). */
export function sameParams(a: PresetParams, b: PresetParams): boolean {
    return PRESET_KEYS.every((key) => (a[key] ?? "") === (b[key] ?? ""));
}

export function isEmptyParams(p: PresetParams): boolean {
    return PRESET_KEYS.every((key) => !p[key]);
}

/** Morceaux du résumé (un par filtre actif), pour des chips ou une ligne de texte. */
export function describeParts(p: PresetParams): string[] {
    const parts: string[] = [];
    if (p.q) parts.push(`“${p.q}”`);
    if (p.type) parts.push(TYPE_LABELS[p.type as MediaTypeFilter] ?? p.type);
    if (p.genre) parts.push(translateGenre(p.genre));
    if (p.quality) parts.push(p.quality);
    if (p.avail) parts.push(AVAIL_LABELS[p.avail as MediaAvail] ?? p.avail);
    if (p.mon) parts.push(MONITOR_LABELS[p.mon as MediaMonitor] ?? p.mon);
    if (p.sub) parts.push(SUB_LABELS[p.sub as MediaSub] ?? p.sub);
    if (p.watch) parts.push(WATCH_LABELS[p.watch as MediaWatch] ?? p.watch);
    if (p.sort || p.order) {
        const sort = SORT_LABELS[(p.sort ?? "title") as MediaSort] ?? p.sort;
        parts.push(`Tri : ${sort} ${p.order === "desc" ? "↓" : "↑"}`);
    }
    return parts;
}

/** Résumé sur une ligne : « “marvel” · Films · Action · Non vus · Tri : Année ↓ ». */
export function describeParams(p: PresetParams): string {
    const parts = describeParts(p);
    return parts.length > 0 ? parts.join(" · ") : "Aucun filtre";
}

/* ════════════════════════════════════════════════════════════════
   Préréglages enregistrés (localStorage)
   ════════════════════════════════════════════════════════════════ */

export interface FilterPreset {
    id: string;
    name: string;
    params: PresetParams;
    createdAt: number;
}

/**
 * Même clé que l'ancienne interface : les préréglages déjà créés sur le
 * serveur sont repris (et convertis) au premier affichage.
 */
export const PRESETS_STORAGE_KEY = "arrmada:media-filter-presets";

/** Garde-fou : au-delà, le menu deviendrait illisible. */
export const MAX_PRESETS = 30;

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/**
 * Format de l'ancienne interface : `{ name, filters: { type, search, sort,
 * order, subFilter, genre, quality, availability, monitored, watchFilter } }`
 * (mêmes valeurs, noms différents) → paramètres d'URL actuels.
 */
function fromLegacy(name: string, filters: Record<string, unknown>): FilterPreset {
    return {
        id: `legacy-${name}`,
        name,
        createdAt: 0,
        params: normalizeParams({
            q: filters.search,
            type: filters.type,
            sort: filters.sort,
            order: filters.order,
            genre: filters.genre,
            quality: filters.quality,
            avail: filters.availability,
            mon: filters.monitored,
            sub: filters.subFilter,
            watch: filters.watchFilter,
        }),
    };
}

/** Valide une entrée lue du stockage (format actuel ou ancien), sinon null. */
function parsePreset(entry: unknown): FilterPreset | null {
    if (!isObject(entry) || typeof entry.name !== "string" || !entry.name.trim()) return null;
    const name = entry.name.trim();
    if (isObject(entry.params) && typeof entry.id === "string") {
        return {
            id: entry.id,
            name,
            params: normalizeParams(entry.params),
            createdAt: typeof entry.createdAt === "number" ? entry.createdAt : 0,
        };
    }
    if (isObject(entry.filters)) return fromLegacy(name, entry.filters);
    return null;
}

/** Préréglages enregistrés (liste vide si rien, illisible ou stockage indisponible). */
export function loadPresets(): FilterPreset[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = JSON.parse(window.localStorage.getItem(PRESETS_STORAGE_KEY) || "[]");
        if (!Array.isArray(raw)) return [];
        const seen = new Set<string>();
        return raw
            .map(parsePreset)
            .filter((p): p is FilterPreset => {
                if (!p || seen.has(p.id)) return false;
                seen.add(p.id);
                return true;
            })
            .slice(0, MAX_PRESETS);
    } catch {
        return [];
    }
}

/** Enregistre la liste ; `false` si le navigateur refuse (quota, mode privé…). */
export function savePresets(presets: FilterPreset[]): boolean {
    if (typeof window === "undefined") return false;
    try {
        window.localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets.slice(0, MAX_PRESETS)));
        return true;
    } catch {
        return false;
    }
}

/**
 * Identifiant unique. Pas de `crypto.randomUUID()` : il n'existe qu'en
 * contexte sécurisé, or ArrMada est souvent servi en http:// sur le LAN.
 */
export function newPresetId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
