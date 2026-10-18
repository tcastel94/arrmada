/**
 * Vocabulaire audio Yamaha partagé par la télécommande (Salon) et
 * l'éditeur de profils (Paramètres → Ampli Yamaha).
 * ----------------------------------------------------------------
 * - programmes sonores (DSP) : identifiants de l'API YamahaExtendedControl
 *   et libellés français, regroupés par usage ;
 * - pièces (Salon / Salle de cinéma) : libellé et icône ;
 * - contexte de lecture Kodi → paramètres du préréglage (le backend
 *   choisit le programme films / séries / musique selon le média).
 */
import { Clapperboard, Sofa, type LucideIcon } from "lucide-react";
import type { KodiNowPlaying } from "@/hooks/use-kodi";
import type { RoomProfile, YamahaPresetApplied, YamahaPresetVars, YamahaRoom } from "@/hooks/use-yamaha";

/** Volume maximal brut de la plupart des amplis Yamaha (0..161, pas de 0,5 dB). */
export const YAMAHA_MAX_VOLUME = 161;
/** Le backend plafonne le volume d'un préréglage à cette valeur (sécurité). */
export const PRESET_VOLUME_CAP = 140;

/** Pourcentage affiché pour un volume brut. */
export function volumePct(raw: number, max = YAMAHA_MAX_VOLUME): number {
    return Math.round((raw / (max || YAMAHA_MAX_VOLUME)) * 100);
}

/**
 * Volume brut → dB affichés par l'ampli. Sur les modèles 0..161, chaque
 * pas vaut 0,5 dB à partir de −80,5 dB. C'est l'unité que les amateurs
 * de home cinéma connaissent (« je regarde à −30 dB »).
 */
export function volumeDb(raw: number): string {
    const db = -80.5 + raw * 0.5;
    return `${db > 0 ? "+" : db < 0 ? "−" : ""}${Math.abs(db).toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} dB`;
}

/* ── Programmes sonores ─────────────────────────────────────── */

export interface SoundProgramGroup {
    label: string;
    items: { id: string; label: string }[];
}

/**
 * Sélection des programmes les plus courants sur les RX-A / RX-V. Un
 * ampli donné n'en supporte qu'une partie : s'il refuse, il garde son
 * programme actuel (sans erreur bloquante).
 */
export const SOUND_PROGRAM_GROUPS: SoundProgramGroup[] = [
    {
        label: "Cinéma",
        items: [
            { id: "straight", label: "Straight (direct, sans effet)" },
            { id: "surr_decoder", label: "Décodeur surround" },
            { id: "standard", label: "Standard" },
            { id: "spectacle", label: "Spectacle" },
            { id: "sci-fi", label: "Science-fiction" },
            { id: "adventure", label: "Aventure" },
            { id: "drama", label: "Drame" },
            { id: "mono_movie", label: "Film mono" },
            { id: "enhanced", label: "Enhanced" },
        ],
    },
    {
        label: "TV & jeux",
        items: [
            { id: "tv_program", label: "Programme TV" },
            { id: "talk_show", label: "Talk-show" },
            { id: "sports", label: "Sport" },
            { id: "music_video", label: "Clip musical" },
            { id: "action_game", label: "Jeu d'action" },
            { id: "roleplaying_game", label: "Jeu de rôle" },
        ],
    },
    {
        label: "Musique",
        items: [
            { id: "2ch_stereo", label: "Stéréo 2 canaux" },
            { id: "5ch_stereo", label: "Stéréo 5 canaux" },
            { id: "7ch_stereo", label: "Stéréo 7 canaux" },
            { id: "9ch_stereo", label: "Stéréo 9 canaux" },
            { id: "11ch_stereo", label: "Stéréo 11 canaux" },
            { id: "munich", label: "Salle de Munich" },
            { id: "vienna", label: "Salle de Vienne" },
            { id: "chamber", label: "Musique de chambre" },
            { id: "cellar_club", label: "Cellar Club (jazz)" },
            { id: "roxy_theatre", label: "The Roxy Theatre" },
            { id: "bottom_line", label: "The Bottom Line" },
            { id: "recital_opera", label: "Récital / opéra" },
        ],
    },
];

const PROGRAM_LABELS: Record<string, string> = Object.fromEntries(
    SOUND_PROGRAM_GROUPS.flatMap((g) => g.items.map((i) => [i.id, i.label] as const)),
);
// Identifiant utilisé par les profils par défaut du backend (l'API YXC
// documente plutôt « surr_decoder ») : libellé lisible malgré tout.
PROGRAM_LABELS.surround_decoder = "Décodeur surround";

export const KNOWN_PROGRAM_IDS = new Set(SOUND_PROGRAM_GROUPS.flatMap((g) => g.items.map((i) => i.id)));

/** Libellé lisible d'un programme (« sci-fi » → « Science-fiction »). */
export function soundProgramLabel(id?: string | null): string {
    if (!id) return "—";
    const known = PROGRAM_LABELS[id];
    if (known) return known;
    const raw = id.replace(/_/g, " ");
    return raw.charAt(0).toUpperCase() + raw.slice(1);
}

/* ── Pièces ─────────────────────────────────────────────────── */

export const ROOMS: YamahaRoom[] = ["salon", "cinema"];

export const ROOM_META: Record<YamahaRoom, { label: string; short: string; icon: LucideIcon; tile: string }> = {
    salon: {
        label: "Salon",
        short: "Salon",
        icon: Sofa,
        tile: "from-orange-500/30 to-amber-500/10 text-orange-300 ring-orange-400/25",
    },
    cinema: {
        label: "Salle de cinéma",
        short: "Cinéma",
        icon: Clapperboard,
        tile: "from-violet-500/30 to-fuchsia-500/10 text-violet-300 ring-violet-400/25",
    },
};

/* ── Contexte de lecture Kodi ───────────────────────────────── */

export type MediaKind = "movie" | "episode" | "music";

const MEDIA_LABELS: Record<MediaKind, string> = { movie: "film", episode: "série", music: "musique" };

/** Type Kodi (movie, episode, song, channel…) → type compris par le backend. */
function mediaKind(kodiType?: string | null): MediaKind | null {
    switch ((kodiType ?? "").toLowerCase()) {
        case "movie":
            return "movie";
        case "episode":
        case "tvshow":
        case "channel": // TV en direct : même programme que les séries
            return "episode";
        case "song":
        case "musicvideo":
        case "audio":
            return "music";
        default:
            return null;
    }
}

/** « 6 » canaux → « 5.1 », « 2 » → « 2.0 ». */
function channelsLabel(n: number): string {
    const map: Record<number, string> = { 1: "mono", 2: "2.0", 3: "2.1", 6: "5.1", 7: "6.1", 8: "7.1" };
    return map[n] ?? `${n} canaux`;
}

export interface PresetContext {
    vars: Pick<YamahaPresetVars, "media_type" | "audio_codec" | "audio_channels">;
    kind: MediaKind;
    /** Ex : « série · EAC3 5.1 ». */
    label: string;
}

/**
 * Ce que Kodi lit en ce moment, traduit en paramètres de préréglage : le
 * backend choisit alors le bon programme (séries ≠ films ≠ musique) et,
 * au Salon, bascule sur le décodeur surround pour une source stéréo.
 * Sans lecture en cours : null (le backend applique le programme « films »).
 */
export function presetContext(np?: KodiNowPlaying | null): PresetContext | null {
    if (!np?.playing) return null;
    const kind = mediaKind(np.type ?? np.media_type);
    if (!kind) return null;
    const channels = np.audio_channels ?? undefined;
    const codec = np.audio_codec ?? undefined;
    const tech = [codec, channels ? channelsLabel(channels) : null].filter(Boolean).join(" ");
    return {
        kind,
        vars: { media_type: kind, audio_codec: codec, audio_channels: channels },
        label: [MEDIA_LABELS[kind], tech].filter(Boolean).join(" · "),
    };
}

/** Programme que le profil appliquera pour ce type de média. */
export function programFor(profile: RoomProfile, kind: MediaKind | null): string {
    if (kind === "episode") return profile.series_sound_program;
    if (kind === "music") return profile.music_sound_program;
    return profile.movie_sound_program;
}

/** Résumé lisible de ce que l'ampli a réellement reçu (pour le toast). */
export function describeApplied(applied?: YamahaPresetApplied, inputLabel?: (id: string) => string): string | undefined {
    if (!applied) return undefined;
    const parts = [
        applied.power === "on" ? "ampli allumé" : null,
        applied.input ? (inputLabel ? inputLabel(applied.input) : applied.input) : null,
        applied.sound_program ? soundProgramLabel(applied.sound_program) : null,
        applied.volume !== undefined ? `volume ${volumePct(applied.volume)} %` : null,
        applied.dialog_lift !== undefined ? `voix ${applied.dialog_lift}/5` : null,
        applied.adaptive_drc ? "mode nuit" : null,
    ].filter(Boolean);
    return parts.length ? parts.join(" · ") : undefined;
}

/** Libellé court (sans précision entre parenthèses), pour les résumés. */
export function soundProgramShortLabel(id?: string | null): string {
    return soundProgramLabel(id).replace(/\s*\(.*\)$/, "");
}
