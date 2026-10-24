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
    /** Bazarr disponible pour ce titre (télécharger / resynchroniser). */
    subtitle_tools: boolean;
    /** Bazarr travaille (téléchargement ou resynchro en cours). */
    subtitle_busy: boolean;
    /** Dernier résultat (« Sous-titres ajoutés : Français »). */
    subtitle_note: string;
    /** Décalage manuel en cours (ms). */
    subtitle_shift_ms: number;
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
    /** Identifiant TMDB (films) : sa filmographie au toucher. */
    tmdb_id: number | null;
}

/** GET /api/ambient/person/{id} : filmographie croisée avec la médiathèque. */
export interface PersonFilmography {
    error?: string;
    person: {
        tmdb_id: number;
        name: string;
        photo: string | null;
        biography: string;
        birthday: string | null;
        place_of_birth: string | null;
    } | null;
    /** Ses films présents dans Radarr (`has_file` : téléchargé, prêt à voir). */
    in_library: PersonMovie[];
    /** Ses autres films (TMDB, par popularité). */
    discover: PersonMovie[];
}

export interface PersonMovie {
    tmdb_id: number;
    title: string;
    year: number | null;
    character: string;
    poster: string | null;
    has_file?: boolean;
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
    | { action: "track"; value: { type: "text" | "audio"; index: number } }
    | { action: "subtitle_download" | "subtitle_sync" }
    | { action: "subtitle_shift"; value: number }
    | { action: "volume_step"; value: number }
    | { action: "mute"; value: boolean };

/** « +1,5 s », « −0,5 s » (décalage des sous-titres). */
export function shiftLabel(ms: number): string {
    const sign = ms < 0 ? "−" : "+";
    return `${sign}${(Math.abs(ms) / 1000).toFixed(1).replace(".", ",")} s`;
}

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
    /** Clé de la fiche (GET /api/ambient/download/{key}) ; absente : serveur ancien. */
    key?: string;
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
    /* ── Fiche au toucher (absents avec un serveur ancien) ── */
    overview?: string;
    poster?: string;
    fanart?: string;
    /** Chaîne (série) ou studio (film). */
    network?: string;
    /** Minutes. */
    runtime?: number | null;
    genres?: string[];
    /** « season » / « series » : dernier épisode de la saison / de la série. */
    finale_type?: string;
    monitored?: boolean;
    rating?: number | null;
    rating_source?: "imdb" | "tmdb" | null;
}

/** Fiche d'un téléchargement (GET /api/ambient/download/{key}), relue toutes les 3 s. */
export interface AmbientDownloadDetail {
    key: string;
    title: string;
    /** Nom de la release (« Gladiator.II.2024.2160p… »). */
    release: string;
    poster: string;
    fanart: string;
    kind: "movie" | "series";
    episodes: number;
    season: number | null;
    status: string;
    tracked_state: string;
    progress: number;
    size_bytes: number;
    size_left_bytes: number;
    time_left: string;
    protocol: string;
    client: string;
    indexer: string;
    quality: string;
    error: string;
    detail: string;
    /** En direct du client (Deluge pour un torrent, SABnzbd pour Usenet) ; null si inconnu. */
    live: AmbientDownloadLive | null;
    /** Pourquoi il n'y a pas de direct (« Ajoute Deluge dans Réglages › Services… »). */
    live_hint: string;
}

export interface AmbientDownloadLive {
    state?: string;
    /** Octets par seconde. */
    download_speed?: number;
    upload_speed?: number;
    /* Torrent (Deluge) */
    seeds?: number;
    seeds_total?: number;
    peers?: number;
    peers_total?: number;
    eta_seconds?: number | null;
    ratio?: number | null;
    tracker?: string;
    /* Usenet (SABnzbd) */
    position?: number;
    queue_size?: number;
    priority?: string;
    age?: string;
    paused_all?: boolean;
}

export interface Ambient {
    server_time: number;
    room: string;
    room_label: string;
    playing: AmbientPlaying | null;
    amp: AmbientAmp | null;
    downloads: AmbientDownload[];
    upcoming: AmbientUpcoming[];
    /** « Ce soir » : seulement quand rien ne passe (null pendant une lecture). */
    tonight?: AmbientTonight | null;
}

/** Demande de lecture d'une vignette (renvoyée telle quelle à POST /api/ambient/play). */
export interface AmbientPlay {
    media_type: "movie" | "episode";
    /** TMDB d'un film, TVDB d'une série. */
    id: string;
    season: number | null;
    episode: number | null;
    title: string;
    /** Reprendre où on en était (sinon depuis le début). */
    resume: boolean;
}

export interface AmbientTile {
    kind: "movie" | "episode" | "series";
    title: string;
    /** Année, « S02E03 » ou « Série ». */
    subtitle: string;
    poster: string;
    fanart: string;
    /** Avancement 1-99 (Reprendre), null sinon. */
    progress: number | null;
    /** null : à lancer depuis la TV (série de « Ma liste » jamais commencée). */
    play: AmbientPlay | null;
}

export interface AmbientTonight {
    resume: AmbientTile[];
    watchlist: AmbientTile[];
    fresh: AmbientTile[];
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

/** Débit : « 5,2 Mo/s », « 820 Ko/s » (octets par seconde, unités de 1 024). */
export function formatSpeed(bytesPerSecond: number | null | undefined): string {
    const b = bytesPerSecond ?? 0;
    if (b <= 0) return "—";
    if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo/s`;
    return `${Math.max(1, Math.round(b / 1024))} Ko/s`;
}

/** Taille : « 61,2 Go », « 840 Mo ». */
export function formatSize(bytes: number | null | undefined): string {
    const b = bytes ?? 0;
    if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Go`;
    return `${Math.round(b / 1024 ** 2)} Mo`;
}

/** Durée restante : « 11 min », « 1 h 05 », « 45 s ». */
export function formatEta(seconds: number | null | undefined): string {
    if (!seconds || seconds <= 0) return "";
    if (seconds < 60) return `${Math.round(seconds)} s`;
    const minutes = Math.round(seconds / 60);
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h === 0) return `${m} min`;
    return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

/** « 00:11:42 » (Radarr / Sonarr) → « 11 min » ; texte inchangé sinon. */
export function prettyTimeLeft(value: string): string {
    const match = /^(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})$/.exec(value.trim());
    if (!match) return value;
    const [, days, h, m, sec] = match;
    return formatEta(Number(days ?? 0) * 86_400 + Number(h) * 3600 + Number(m) * 60 + Number(sec)) || "bientôt fini";
}

const DOWNLOAD_STATES: Record<string, string> = {
    downloading: "Téléchargement",
    seeding: "Partage (terminé)",
    paused: "En pause",
    queued: "En file d'attente",
    checking: "Vérification",
    moving: "Déplacement",
    error: "Erreur",
    delay: "En attente (délai)",
    importpending: "Import en attente",
    importing: "Import en cours",
    imported: "Importé",
    failedpending: "Échec, en attente",
    completed: "Terminé",
    fetching: "Récupération",
    grabbing: "Récupération",
    propagating: "Propagation",
    extracting: "Extraction",
    verifying: "Vérification",
    repairing: "Réparation",
};

/** État d'un téléchargement en français (Deluge, SABnzbd, Radarr / Sonarr). */
export function downloadStateLabel(value: string | null | undefined): string {
    if (!value) return "";
    return DOWNLOAD_STATES[value.toLowerCase().replace(/[\s_]/g, "")] ?? value;
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
