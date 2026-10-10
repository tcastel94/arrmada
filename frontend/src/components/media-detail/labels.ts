/**
 * Libellés FR et petites fonctions utilitaires de la fiche média.
 * ----------------------------------------------------------------
 * Radarr / Sonarr / Bazarr renvoient des codes anglais (continuing, inCinemas,
 * director, forced…) : on les traduit ici, à un seul endroit, pour que toute
 * la fiche parle le même français.
 */
import type { CastMember, EpisodeDetail, FileInfo, SeasonDetail } from "@/hooks/use-media";
import type { SubtitleTrack } from "@/hooks/use-subtitles";

export type MediaType = "movie" | "series";

/* ── Statut du média ─────────────────────────────────────────── */

export type StatusTone = "success" | "warning" | "primary" | "muted" | "danger";

const MOVIE_STATUS: Record<string, { label: string; tone: StatusTone }> = {
    tba: { label: "À annoncer", tone: "muted" },
    announced: { label: "Annoncé", tone: "warning" },
    incinemas: { label: "Au cinéma", tone: "primary" },
    released: { label: "Sorti", tone: "success" },
    deleted: { label: "Retiré de TMDb", tone: "danger" },
};

const SERIES_STATUS: Record<string, { label: string; tone: StatusTone }> = {
    continuing: { label: "En cours", tone: "success" },
    ended: { label: "Terminée", tone: "muted" },
    upcoming: { label: "À venir", tone: "warning" },
    deleted: { label: "Supprimée", tone: "danger" },
};

/** Statut traduit (« continuing » → « En cours »…) + teinte sémantique. */
export function statusInfo(status: string | null | undefined, type: MediaType): { label: string; tone: StatusTone } | null {
    if (!status) return null;
    const key = status.toLowerCase();
    const map = type === "movie" ? MOVIE_STATUS : SERIES_STATUS;
    return map[key] ?? { label: status.charAt(0).toUpperCase() + status.slice(1), tone: "muted" };
}

/* ── Options d'édition ───────────────────────────────────────── */

export const MOVIE_AVAILABILITY = [
    { value: "announced", label: "Annoncé" },
    { value: "inCinemas", label: "Au cinéma" },
    { value: "released", label: "Sorti" },
] as const;

export const SERIES_TYPES = [
    { value: "standard", label: "Standard" },
    { value: "daily", label: "Quotidienne (daily)" },
    { value: "anime", label: "Anime" },
] as const;

export function availabilityLabel(value?: string | null): string {
    return MOVIE_AVAILABILITY.find((o) => o.value.toLowerCase() === (value ?? "").toLowerCase())?.label ?? (value || "—");
}

export function seriesTypeLabel(value?: string | null): string {
    return SERIES_TYPES.find((o) => o.value === value)?.label ?? (value || "—");
}

/* ── Équipe technique ────────────────────────────────────────── */

const CREW_LABELS: Record<string, string> = {
    director: "Réalisation",
    writer: "Scénario",
    screenplay: "Scénario",
    story: "Histoire",
    novel: "Œuvre originale",
    author: "Œuvre originale",
    characters: "Personnages",
    creator: "Création",
    producer: "Production",
    "executive producer": "Production exécutive",
    "original music composer": "Musique",
    composer: "Musique",
    music: "Musique",
    "director of photography": "Image",
    cinematography: "Image",
    editor: "Montage",
    "casting director": "Casting",
};

/** Métier traduit : director → Réalisation, writer → Scénario… */
export function crewLabel(member: Pick<CastMember, "type" | "job">): string {
    const raw = (member.job || member.type || "").trim();
    const label = CREW_LABELS[raw.toLowerCase()];
    if (label) return label;
    return raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : "Équipe";
}

/** Département TMDb d'une personne (Acting, Directing…) → FR. */
export function departmentLabel(dep?: string | null): string {
    const map: Record<string, string> = {
        acting: "Interprétation",
        directing: "Réalisation",
        writing: "Scénario",
        production: "Production",
        sound: "Musique & son",
        camera: "Image",
        editing: "Montage",
        art: "Décors",
        "costume & make-up": "Costumes & maquillage",
        crew: "Équipe technique",
        "visual effects": "Effets visuels",
        lighting: "Lumière",
    };
    if (!dep) return "";
    return map[dep.toLowerCase()] ?? dep;
}

/* ── Épisodes ────────────────────────────────────────────────── */

export const pad2 = (n: number | null | undefined) => String(n ?? 0).padStart(2, "0");

/** S01E02 */
export function episodeCode(season: number, episode: number): string {
    return `S${pad2(season)}E${pad2(episode)}`;
}

/**
 * Date « jour » (YYYY-MM-DD) lue en heure LOCALE.
 * (new Date("2025-03-12") la lirait en UTC → décalage d'un jour le soir.)
 */
export function parseDay(value: string | null | undefined): Date | null {
    if (!value) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    if (!m) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return Number.isNaN(d.getTime()) ? null : d;
}

/** Début de la journée en cours (heure locale). */
function todayStart(): Date {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/**
 * Épisode pas encore diffusé : date future, ou date inconnue (TBA).
 * Ces épisodes ne sont ni « manquants » ni recherchables.
 */
export function isUpcoming(ep: Pick<EpisodeDetail, "air_date">): boolean {
    const d = parseDay(ep.air_date);
    if (!d) return true;
    return d.getTime() > todayStart().getTime();
}

export type EpisodeState = "present" | "missing" | "upcoming";

export function episodeState(ep: EpisodeDetail): EpisodeState {
    if (ep.has_file) return "present";
    return isUpcoming(ep) ? "upcoming" : "missing";
}

/** "12 mars 2024" (date jour locale). */
export function formatDay(value: string | null | undefined, opts: { withYear?: boolean } = {}): string {
    const d = parseDay(value);
    if (!d) return "";
    const sameYear = d.getFullYear() === new Date().getFullYear();
    return d.toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "long",
        ...(opts.withYear || !sameYear ? { year: "numeric" } : {}),
    });
}

export interface SeasonStats {
    total: number;
    have: number;
    aired: number;
    missing: number;
    upcoming: number;
    /** % d'épisodes diffusés présents (0 si rien n'est encore sorti). */
    pct: number;
}

export function seasonStats(season: Pick<SeasonDetail, "episodes">): SeasonStats {
    let have = 0;
    let missing = 0;
    let upcoming = 0;
    for (const ep of season.episodes) {
        const s = episodeState(ep);
        if (s === "present") have++;
        else if (s === "missing") missing++;
        else upcoming++;
    }
    // Un épisode « à venir » déjà téléchargé (fuite / date erronée) compte comme diffusé.
    const aired = have + missing;
    return {
        total: season.episodes.length,
        have,
        aired,
        missing,
        upcoming,
        pct: aired > 0 ? Math.round((have / aired) * 100) : 0,
    };
}

/** Totaux de la série, spéciaux (saison 0) exclus comme le fait Sonarr. */
export function seriesStats(seasons: SeasonDetail[] | undefined): SeasonStats {
    const regular = (seasons ?? []).filter((s) => s.season_number > 0);
    return seasonStats({ episodes: regular.flatMap((s) => s.episodes) });
}

/** Saisons triées : 1, 2, 3… puis les spéciaux (saison 0) en dernier. */
export function sortSeasons<T extends { season_number: number }>(seasons: T[]): T[] {
    return [...seasons].sort((a, b) => {
        if (a.season_number === 0) return 1;
        if (b.season_number === 0) return -1;
        return a.season_number - b.season_number;
    });
}

export function seasonLabel(n: number): string {
    return n === 0 ? "Épisodes spéciaux" : `Saison ${n}`;
}

/* ── Fichiers ────────────────────────────────────────────────── */

/** 2160 → « 4K », 1080 → « 1080p »… */
export function resolutionLabel(res: FileInfo["resolution"] | null | undefined): string {
    const n = typeof res === "number" ? res : parseInt(String(res ?? ""), 10);
    if (!n || Number.isNaN(n)) return typeof res === "string" && res ? res : "";
    if (n >= 2000) return "4K";
    if (n >= 1400) return "1440p";
    if (n >= 1000) return "1080p";
    if (n >= 700) return "720p";
    return "SD";
}

/** Source *arr lisible : bluray → « Blu-ray », webdl → « WEB-DL »… */
export function sourceLabel(src: string | null | undefined): string {
    const map: Record<string, string> = {
        bluray: "Blu-ray",
        web: "WEB",
        webdl: "WEB-DL",
        webrip: "WEBRip",
        television: "TV",
        tv: "TV",
        dvd: "DVD",
        remux: "Remux",
        cam: "CAM",
    };
    if (!src) return "";
    return map[src.toLowerCase().replace(/[^a-z]/g, "")] ?? src;
}

/** 6 → « 5.1 », 8 → « 7.1 », 2 → « 2.0 », 5.1 → « 5.1 ». */
export function audioChannelsLabel(ch: number | null | undefined): string {
    if (!ch) return "";
    if (!Number.isInteger(ch)) return ch.toFixed(1);
    const map: Record<number, string> = { 1: "1.0", 2: "2.0", 3: "2.1", 6: "5.1", 7: "6.1", 8: "7.1" };
    return map[ch] ?? `${ch} canaux`;
}

/** HDR lisible : « HDR10 », « Dolby Vision »… (null si SDR). */
export function hdrLabel(file: Pick<FileInfo, "video_dynamic_range" | "video_dynamic_range_type">): string | null {
    const t = (file.video_dynamic_range_type || file.video_dynamic_range || "").trim();
    if (!t || t.toUpperCase() === "SDR") return null;
    return t.replace(/^DV/i, "Dolby Vision").replace(/HDR10Plus/i, "HDR10+");
}

/** Dernier segment d'un chemin (nom du dossier). */
export function basename(path: string): string {
    const parts = path.replace(/[\\/]+$/, "").split(/[\\/]/);
    return parts[parts.length - 1] || "";
}

/* ── Releases ────────────────────────────────────────────────── */

/** Âge d'une release : « aujourd'hui », « 3 j », « 2 mois », « 1 an ». */
export function ageLabel(days: number | null | undefined): string {
    const d = Math.max(0, Math.round(days ?? 0));
    if (d < 1) return "aujourd'hui";
    if (d < 30) return `${d} j`;
    if (d < 365) return `${Math.round(d / 30)} mois`;
    const y = Math.round(d / 365);
    return `${y} an${y > 1 ? "s" : ""}`;
}

/* ── Sous-titres ─────────────────────────────────────────────── */

export function subLangLabel(t: Pick<SubtitleTrack, "language" | "code2">): string {
    return t.language || (t.code2 ? t.code2.toUpperCase() : "?");
}

/** Clé stable d'une piste (le chemin s'il existe, sinon langue + variantes). */
export function subTrackKey(t: SubtitleTrack): string {
    return t.path || `${t.code2}:${t.forced ? "f" : ""}:${t.hi ? "h" : ""}`;
}

/* ── Divers ──────────────────────────────────────────────────── */

/** Initiales pour les avatars sans photo : « Tom Hanks » → « TH ». */
export function initials(name: string): string {
    return name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((p) => p[0]?.toUpperCase() ?? "")
        .join("");
}

/**
 * Copie dans le presse-papiers, avec repli pour les contextes non sécurisés
 * (ArrMada est souvent servi en http:// sur le LAN, où navigator.clipboard
 * n'existe pas).
 */
export async function copyText(text: string): Promise<boolean> {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch {
        /* on tente le repli ci-dessous */
    }
    try {
        const el = document.createElement("textarea");
        el.value = text;
        el.setAttribute("readonly", "");
        el.style.position = "fixed";
        el.style.opacity = "0";
        document.body.appendChild(el);
        el.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(el);
        return ok;
    } catch {
        return false;
    }
}
