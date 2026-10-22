/**
 * Écran d'appoint du salon (tablette sous la TV) — logique sans affichage.
 * ----------------------------------------------------------------
 * La page /ecran interroge `GET /api/ambient` toutes les 10 s. Entre deux
 * réponses, elle avance elle-même la position de lecture chaque seconde :
 * comme `uptime` qu'on recalcule à partir de l'heure de démarrage plutôt
 * que de redemander au serveur.
 *
 * Horloges : la tablette et le serveur peuvent avoir quelques secondes
 * d'écart. On mesure l'écart à chaque réponse (`server_time`) et on le
 * corrige, sinon l'heure de fin « bougerait » d'une réponse à l'autre.
 *
 * Luminosité : Fully Kiosk Browser (licence PLUS, « Enable JavaScript
 * Interface » coché) expose `window.fully.setScreenBrightness(0-255)`. Sans
 * Fully, la page assombrit simplement son contenu (le rétroéclairage, lui,
 * reste au réglage d'Android).
 */

/* ── Format de GET /api/ambient ─────────────────────────────── */

export interface AmbientPlaying {
    title: string;
    /** « S02E10 · Cold Harbor » (épisode) ou l'année (film). */
    subtitle: string;
    kind: "movie" | "episode";
    poster: string;
    fanart: string;
    state: "playing" | "paused";
    /** Secondes, au moment `updated_at`. */
    position: number;
    duration: number;
    /** Horodatages Unix (secondes) du serveur. */
    updated_at: number;
    started_at: number;
    device: string;
    /* ── Appli Android (vides avec Kodi) ── */
    /** « 4K · Dolby Vision », « 1080p · SDR (converti) » */
    video: string;
    /** « Français · TrueHD Atmos · 7.1 » */
    audio: string;
    /** Sous-titres affichés (« Français (forcés) »), vide si aucun. */
    subtitle_track: string;
    chapter: string;
    /** Début du générique de fin (s), 0 si inconnu. */
    credits_at: number;
    /** « S02E04 · Titre » */
    next_up: string;
    /** Passages à sauter : « Passer l'intro » pendant [start, end[. */
    skips: AmbientSkip[];
    overview: string;
    meta_line: string;
    cast: AmbientCast[];
    subtitle_tracks: AmbientTrack[];
    audio_tracks: AmbientTrack[];
    /** La TV accepte la télécommande tactile. */
    remote: boolean;
}

export interface AmbientSkip {
    kind: string;
    label: string;
    start: number;
    end: number;
}

export interface AmbientCast {
    name: string;
    character: string;
    photo: string;
}

export interface AmbientTrack {
    index: number;
    label: string;
    detail: string;
    selected: boolean;
}

/** Commande de la télécommande tactile (POST /api/ambient/command). */
export type RemoteAction =
    | { action: "toggle" | "play" | "pause" | "skip" | "next" }
    | { action: "seek"; value: number }
    | { action: "track"; value: { type: "text" | "audio"; index: number } };

/** Passage à sauter en cours à cette position, s'il y en a un. */
export function activeSkip(playing: AmbientPlaying, position: number): AmbientSkip | null {
    return (playing.skips ?? []).find((s) => position >= s.start && position < s.end) ?? null;
}

/** Secondes avant le générique de fin, ou null (inconnu, ou déjà commencé). */
export function untilCredits(playing: AmbientPlaying, position: number): number | null {
    const at = playing.credits_at ?? 0;
    return at > 0 && at > position ? at - position : null;
}

export interface AmbientAmp {
    name: string;
    power: string;
    volume_pct: number | null;
    mute: boolean;
    input: string;
    sound_program: string;
}

export interface AmbientDownload {
    title: string;
    progress: number;
    time_left: string;
    paused: boolean;
}

export interface AmbientUpcoming {
    title: string;
    label: string;
    subtitle: string;
    air_date: string;
    kind: "movie" | "episode";
    release_type: string;
}

export interface Ambient {
    server_time: number;
    room: string;
    room_label: string;
    playing: AmbientPlaying | null;
    amp: AmbientAmp | null;
    downloads: AmbientDownload[];
    upcoming: AmbientUpcoming[];
}

/* ── Séance en cours : position, début, fin ─────────────────── */

export interface Session {
    /** Position estimée maintenant (s). */
    position: number;
    /** Reste à voir (s), 0 si la durée est inconnue. */
    remaining: number;
    /** 0 → 1 */
    progress: number;
    /** Début de la séance (heure locale de la tablette). */
    startedAt: Date | null;
    /** Fin prévue si on ne met plus en pause. */
    endsAt: Date | null;
    paused: boolean;
}

/**
 * Où en est la lecture à l'instant `nowMs` (horloge de la tablette).
 * `offsetS` = heure du serveur − heure de la tablette (s), mesuré à la
 * dernière réponse.
 */
export function sessionAt(playing: AmbientPlaying, nowMs: number, offsetS: number): Session {
    const serverNow = nowMs / 1000 + offsetS;
    const paused = playing.state === "paused";
    const elapsed = paused ? 0 : Math.max(0, serverNow - playing.updated_at);
    const duration = Math.max(0, playing.duration);
    let position = Math.max(0, playing.position + elapsed);
    if (duration > 0) position = Math.min(position, duration);
    const remaining = duration > 0 ? Math.max(0, duration - position) : 0;
    const toLocal = (serverSeconds: number) => new Date((serverSeconds - offsetS) * 1000);
    return {
        position,
        remaining,
        progress: duration > 0 ? position / duration : 0,
        startedAt: playing.started_at > 0 ? toLocal(playing.started_at) : null,
        endsAt: duration > 0 ? new Date(nowMs + remaining * 1000) : null,
        paused,
    };
}

/* ── Mise en forme ──────────────────────────────────────────── */

const TIME = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const DAY = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" });

/** « 21:04 » */
export function hhmm(date: Date | null): string {
    return date ? TIME.format(date) : "--:--";
}

/** « samedi 10 octobre » */
export function longDay(date: Date): string {
    return DAY.format(date);
}

/** « 1 h 12 », « 8 min », « moins d'une minute » */
export function remainingLabel(seconds: number): string {
    const minutes = Math.round(seconds / 60);
    if (minutes < 1) return "moins d'une minute";
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h === 0) return `${m} min`;
    return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

/** Jour relatif d'une sortie : « ce soir 21:00 », « demain », « lundi ». */
export function releaseWhen(value: string, now: Date, kind: "movie" | "episode"): string {
    // Radarr donne parfois une date seule (« 2026-10-11 ») : c'est un jour, pas une heure.
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
    const date = dateOnly ? new Date(`${value}T12:00:00`) : new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const days = Math.round((startOfDay(date) - startOfDay(now)) / 86_400_000);
    const time = !dateOnly && kind === "episode" ? ` ${hhmm(date)}` : "";
    if (days <= 0) return date.getHours() >= 18 && time ? `ce soir${time}` : `aujourd'hui${time}`;
    if (days === 1) return `demain${time}`;
    return `${new Intl.DateTimeFormat("fr-FR", { weekday: "long" }).format(date)}${time}`;
}

const RELEASE_TYPES: Record<string, string> = {
    digital: "sortie numérique",
    physical: "Blu-ray",
    cinema: "au cinéma",
};

export function releaseTypeLabel(value: string): string {
    return RELEASE_TYPES[value] ?? "";
}

const INPUTS: Record<string, string> = {
    hdmi1: "HDMI 1",
    hdmi2: "HDMI 2",
    hdmi3: "HDMI 3",
    hdmi4: "HDMI 4",
    av1: "AV 1",
    audio1: "Audio 1",
    optical: "Optique",
    coaxial: "Coaxial",
    tuner: "Radio",
    net_radio: "Radio Internet",
    spotify: "Spotify",
    airplay: "AirPlay",
    bluetooth: "Bluetooth",
    tv: "TV (ARC)",
};

/** « hdmi1 » → « HDMI 1 » ; « surr_decoder » → « Surr Decoder ». */
export function prettyName(value: string): string {
    if (!value) return "";
    if (INPUTS[value]) return INPUTS[value];
    return value
        .split(/[_\s]+/)
        .filter(Boolean)
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

/* ── Réglages passés dans l'adresse de la page ──────────────── */

export interface ScreenOptions {
    /** Luminosité Fully pendant une lecture (0-255). */
    dim: number;
    /** Luminosité Fully au repos (0-255). */
    rest: number;
    /** Pièce choisie pour l'aperçu admin (la tablette appairée garde la sienne). */
    room: string;
}

function level(value: string | null, fallback: number): number {
    if (value === null || value.trim() === "") return fallback;
    const n = Number(value);
    return Number.isFinite(n) ? Math.max(0, Math.min(255, Math.round(n))) : fallback;
}

/**
 * `/ecran?seance=6&repos=40` : luminosités 0-255 (défauts : 6 pendant un
 * film, 40 au repos). Bornées : une faute de frappe ne met pas l'écran à fond.
 */
export function readOptions(search: string): ScreenOptions {
    const params = new URLSearchParams(search);
    return {
        dim: level(params.get("seance"), 6),
        rest: level(params.get("repos"), 40),
        room: ["cinema", "bureau"].includes(params.get("piece") ?? "") ? (params.get("piece") as string) : "salon",
    };
}

/* ── Fully Kiosk Browser ────────────────────────────────────── */

interface FullyBridge {
    setScreenBrightness?: (value: number) => void;
}

function fully(): FullyBridge | null {
    if (typeof window === "undefined") return null;
    const bridge = (window as unknown as { fully?: FullyBridge }).fully;
    return bridge && typeof bridge.setScreenBrightness === "function" ? bridge : null;
}

/** La page tourne-t-elle dans Fully Kiosk avec l'interface JavaScript active ? */
export function hasFully(): boolean {
    return fully() !== null;
}

/** Règle le rétroéclairage (Fully seulement) ; true si c'est fait. */
export function setBrightness(value: number): boolean {
    const bridge = fully();
    if (!bridge?.setScreenBrightness) return false;
    try {
        bridge.setScreenBrightness(Math.max(0, Math.min(255, Math.round(value))));
        return true;
    } catch {
        return false; // option désactivée entre-temps : la page reste utilisable
    }
}

/* ── Jeton de l'écran (appairage) ───────────────────────────── */

const SCREEN_TOKEN_KEY = "arrmada_screen_token";

export function getScreenToken(): string | null {
    if (typeof window === "undefined") return null;
    try {
        return localStorage.getItem(SCREEN_TOKEN_KEY);
    } catch {
        return null;
    }
}

export function setScreenToken(token: string | null): void {
    try {
        if (token) localStorage.setItem(SCREEN_TOKEN_KEY, token);
        else localStorage.removeItem(SCREEN_TOKEN_KEY);
    } catch {
        // stockage bloqué : il faudra réappairer au prochain chargement
    }
}

/** « Pixel Tablet · Fully Kiosk » (montré dans la liste des appareils). */
export function platformName(userAgent: string): string {
    const browser = /fully/i.test(userAgent) ? "Fully Kiosk" : "Navigateur";
    const model = /Android [\d.]+; ([^;)]+?)(?: Build|\))/.exec(userAgent)?.[1]?.trim();
    return `${model && model !== "K" ? model : "Écran"} · ${browser}`.slice(0, 100);
}
