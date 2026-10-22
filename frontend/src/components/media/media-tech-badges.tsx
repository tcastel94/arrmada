"use client";

/**
 * Badges techniques d'un fichier vidéo : résolution (4K, 1080p…), plage
 * dynamique (Dolby Vision, HDR10…), audio (Atmos, DTS:X… + canaux), source
 * (Remux, Blu-ray…), codec vidéo et édition.
 * ----------------------------------------------------------------
 * Deux présentations :
 *  - "card" : 2-3 pastilles très compactes posées sur une affiche de la
 *             médiathèque. Libellés courts (« 4K », « DV », « Atmos ») et
 *             fond sombre opaque, lisible sur n'importe quelle image.
 *  - "hero" : rangée complète sur la fiche média (fichier principal),
 *             pastilles en verre teinté avec icône et libellé long.
 *
 * La détection est volontairement tolérante : Radarr/Sonarr renvoient des
 * formats variés (2160 en nombre, « Bluray-2160p », « DV HDR10 »,
 * « TrueHD Atmos », « DTS-HD MA »…). On cherche donc des motifs dans le
 * texte plutôt que des valeurs exactes.
 */
import { motion } from "framer-motion";
import { AudioLines, Clapperboard, Cpu, Disc3, Monitor, Sparkles, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { scaleIn, stagger } from "@/lib/motion";
import { audioChannelsLabel } from "@/components/media-detail/labels";

/** Sous-ensemble commun à un `MediaItem` (liste) et à un `FileInfo` (fiche). */
export interface MediaTechSpecs {
    resolution?: string | number | null;
    /** Nom de qualité *arr (« Bluray-2160p », « WEBDL-1080p »…). */
    quality?: string | null;
    video_codec?: string | null;
    video_dynamic_range?: string | null;
    /** Plus précis que `video_dynamic_range` (« DV HDR10 » vs « HDR »). */
    video_dynamic_range_type?: string | null;
    audio_codec?: string | null;
    audio_channels?: number | null;
    edition?: string | null;
}

type TechKind = "resolution" | "hdr" | "audio" | "source" | "codec" | "edition";

/** Familles de couleurs : une teinte par « univers » technique, pas par valeur. */
type TechTone = "premium" | "sky" | "neutral" | "muted" | "dv" | "hdr" | "dolby" | "dts" | "lossless";

export interface TechBadge {
    kind: TechKind;
    /** Libellé court, pour les affiches. */
    short: string;
    /** Libellé complet, pour la fiche et l'infobulle. */
    label: string;
    tone: TechTone;
}

/* ════════════════════════════════════════════════════════════════
   Détection
   ════════════════════════════════════════════════════════════════ */

const lc = (v: unknown) => (v === null || v === undefined ? "" : String(v)).toLowerCase().trim();

function detectResolution(specs: MediaTechSpecs): TechBadge | null {
    // Priorité au nombre de lignes (Radarr : 2160, 1080…) ; sinon on cherche
    // dans le texte de résolution + le nom de qualité (« Bluray-2160p »).
    const n = Number.parseInt(lc(specs.resolution), 10);
    const text = `${lc(specs.resolution)} ${lc(specs.quality)}`;
    const has = Number.isFinite(n) && n > 0;
    if (has ? n >= 2000 : /2160|\b4k\b|\buhd\b/.test(text))
        return { kind: "resolution", short: "4K", label: "4K UHD", tone: "premium" };
    if (has ? n >= 1400 : /1440/.test(text)) return { kind: "resolution", short: "1440p", label: "1440p QHD", tone: "sky" };
    if (has ? n >= 1000 : /1080/.test(text)) return { kind: "resolution", short: "1080p", label: "1080p Full HD", tone: "sky" };
    if (has ? n >= 700 : /720/.test(text)) return { kind: "resolution", short: "720p", label: "720p HD", tone: "neutral" };
    if (has || /480|576|\bsd\b|dvd/.test(text)) return { kind: "resolution", short: "SD", label: "SD", tone: "muted" };
    return null;
}

function detectHdr(specs: MediaTechSpecs): TechBadge | null {
    // Le « type » (DV, HDR10Plus, HLG…) est plus précis que la plage (« HDR »).
    const t = `${lc(specs.video_dynamic_range_type)} ${lc(specs.video_dynamic_range)}`;
    if (/\bdv\b|dolby ?vision|dovi/.test(t)) return { kind: "hdr", short: "DV", label: "Dolby Vision", tone: "dv" };
    if (/hdr10(\+|plus)/.test(t)) return { kind: "hdr", short: "HDR10+", label: "HDR10+", tone: "hdr" };
    if (/\bhlg\b/.test(t)) return { kind: "hdr", short: "HLG", label: "HLG", tone: "hdr" };
    if (/hdr10/.test(t)) return { kind: "hdr", short: "HDR10", label: "HDR10", tone: "hdr" };
    if (/hdr|\bpq\b/.test(t)) return { kind: "hdr", short: "HDR", label: "HDR", tone: "hdr" };
    return null;
}

function detectAudio(specs: MediaTechSpecs): TechBadge | null {
    const a = lc(specs.audio_codec);
    const channels = audioChannelsLabel(specs.audio_channels);
    // Les canaux complètent le libellé long (« Dolby Atmos · 7.1 »), pas le court.
    const withChannels = (label: string) => (channels ? `${label} · ${channels}` : label);

    // L'ordre compte : « TrueHD Atmos » doit sortir en Atmos, « EAC3 » ne
    // doit pas être pris pour de l'AC3, « DTS-HD MA » pour du DTS simple.
    if (a.includes("atmos")) return { kind: "audio", short: "Atmos", label: withChannels("Dolby Atmos"), tone: "dolby" };
    if (/dts[-: ]?x\b/.test(a)) return { kind: "audio", short: "DTS:X", label: withChannels("DTS:X"), tone: "dts" };
    if (a.includes("dts") && (a.includes("hd") || /\bma\b/.test(a)))
        return { kind: "audio", short: "DTS-HD", label: withChannels("DTS-HD MA"), tone: "dts" };
    if (a.includes("dts")) return { kind: "audio", short: "DTS", label: withChannels("DTS"), tone: "dts" };
    if (a.includes("truehd")) return { kind: "audio", short: "TrueHD", label: withChannels("Dolby TrueHD"), tone: "dolby" };
    if (/e-?ac-?3|dd\+|ddp|digital ?(\+|plus)/.test(a))
        return { kind: "audio", short: "DD+", label: withChannels("Dolby Digital+"), tone: "dolby" };
    if (/\bac-?3\b|\bdd\b|dolby digital/.test(a)) return { kind: "audio", short: "DD", label: withChannels("Dolby Digital"), tone: "dolby" };
    if (a.includes("flac")) return { kind: "audio", short: "FLAC", label: withChannels("FLAC"), tone: "lossless" };
    if (/\bl?pcm\b/.test(a)) return { kind: "audio", short: "PCM", label: withChannels("PCM"), tone: "lossless" };
    // Codec courant (AAC, MP3, Opus…) : affiché tel quel, en neutre.
    if (a) return { kind: "audio", short: a.toUpperCase(), label: withChannels(String(specs.audio_codec).trim()), tone: "neutral" };
    // Pas de codec connu mais des canaux : on garde au moins l'info « 5.1 ».
    if (channels) return { kind: "audio", short: channels, label: `Audio ${channels}`, tone: "neutral" };
    return null;
}

function detectSource(specs: MediaTechSpecs): TechBadge | null {
    const q = lc(specs.quality);
    if (q.includes("remux")) return { kind: "source", short: "Remux", label: "Remux Blu-ray", tone: "neutral" };
    if (/blu-?ray|bdrip|brrip/.test(q)) return { kind: "source", short: "Blu-ray", label: "Blu-ray", tone: "neutral" };
    if (/web-?dl/.test(q)) return { kind: "source", short: "WEB-DL", label: "WEB-DL", tone: "neutral" };
    if (q.includes("webrip")) return { kind: "source", short: "WEBRip", label: "WEBRip", tone: "neutral" };
    if (q.includes("hdtv")) return { kind: "source", short: "HDTV", label: "HDTV", tone: "muted" };
    if (q.includes("dvd")) return { kind: "source", short: "DVD", label: "DVD", tone: "muted" };
    return null;
}

function detectCodec(specs: MediaTechSpecs): TechBadge | null {
    const v = lc(specs.video_codec);
    if (/hevc|h\.?265|x265/.test(v)) return { kind: "codec", short: "HEVC", label: "HEVC (H.265)", tone: "muted" };
    if (/avc|h\.?264|x264/.test(v)) return { kind: "codec", short: "AVC", label: "AVC (H.264)", tone: "muted" };
    if (v.includes("av1")) return { kind: "codec", short: "AV1", label: "AV1", tone: "muted" };
    if (v.includes("vp9")) return { kind: "codec", short: "VP9", label: "VP9", tone: "muted" };
    if (/mpeg-?2/.test(v)) return { kind: "codec", short: "MPEG-2", label: "MPEG-2", tone: "muted" };
    if (/xvid|divx/.test(v)) return { kind: "codec", short: "XviD", label: "XviD / DivX", tone: "muted" };
    return null;
}

/**
 * Liste ordonnée des badges reconnus (résolution, HDR, audio, source,
 * codec, édition). Vide si rien n'est exploitable.
 */
export function parseTechSpecs(specs?: MediaTechSpecs | null): TechBadge[] {
    if (!specs) return [];
    const edition = specs.edition?.trim();
    return [
        detectResolution(specs),
        detectHdr(specs),
        detectAudio(specs),
        detectSource(specs),
        detectCodec(specs),
        edition ? ({ kind: "edition", short: edition, label: edition, tone: "neutral" } satisfies TechBadge) : null,
    ].filter((b): b is TechBadge => b !== null);
}

/**
 * Badges retenus pour une affiche : seulement résolution, HDR et un audio
 * « remarquable » (Dolby / DTS / sans perte). Un AAC ou un « 2.0 » n'apporte
 * rien sur une affiche et la surchargerait.
 */
export function cardTechBadges(specs?: MediaTechSpecs | null, max = 3): TechBadge[] {
    return parseTechSpecs(specs)
        .filter((b) => b.kind === "resolution" || b.kind === "hdr" || (b.kind === "audio" && b.tone !== "neutral"))
        .slice(0, max);
}

/* ════════════════════════════════════════════════════════════════
   Styles
   ════════════════════════════════════════════════════════════════ */

/**
 * Affiche : fond sombre quasi opaque (comme PosterBadge) pour rester lisible
 * sur une image claire ; la couleur passe par le texte et le liseré. Seule
 * la 4K a un fond en dégradé de marque (c'est l'info qui « claque »).
 */
const CARD_TONES: Record<TechTone, string> = {
    premium: "bg-gradient-to-r from-primary/90 to-brand/80 text-white ring-white/25",
    sky: "bg-black/65 text-sky-200 ring-sky-300/30",
    neutral: "bg-black/65 text-white/90 ring-white/15",
    muted: "bg-black/65 text-white/60 ring-white/10",
    dv: "bg-black/65 text-fuchsia-200 ring-fuchsia-300/40",
    hdr: "bg-black/65 text-orange-200 ring-orange-300/35",
    dolby: "bg-black/65 text-cyan-200 ring-cyan-300/35",
    dts: "bg-black/65 text-rose-200 ring-rose-300/35",
    lossless: "bg-black/65 text-emerald-200 ring-emerald-300/30",
};

/** Fiche : verre teinté, même grammaire que les pastilles de statut du hero. */
const HERO_TONES: Record<TechTone, string> = {
    premium:
        "border-primary/40 bg-gradient-to-r from-primary/20 to-brand/15 text-sky-100",
    sky: "border-sky-400/30 bg-sky-500/10 text-sky-200",
    neutral: "border-white/10 bg-white/[0.05] text-foreground/85",
    muted: "border-white/[0.08] bg-white/[0.03] text-muted-foreground",
    dv: "border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-200",
    hdr: "border-orange-400/30 bg-orange-500/10 text-orange-200",
    dolby: "border-cyan-400/30 bg-cyan-500/10 text-cyan-200",
    dts: "border-rose-400/30 bg-rose-500/10 text-rose-200",
    lossless: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
};

const KIND_ICONS: Record<TechKind, LucideIcon> = {
    resolution: Monitor,
    hdr: Sparkles,
    audio: AudioLines,
    source: Disc3,
    codec: Cpu,
    edition: Clapperboard,
};

/** Pastille de la fiche (la teinte s'ajoute par-dessus). */
const heroPill = "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold backdrop-blur-md";

/** Léger soulèvement au survol (via framer : le transform CSS serait écrasé par l'animation d'entrée). */
const HOVER_LIFT = { y: -2 };

/** Infobulle : « Résolution : 4K UHD »… */
const KIND_LABELS: Record<TechKind, string> = {
    resolution: "Résolution",
    hdr: "Plage dynamique",
    audio: "Audio",
    source: "Source",
    codec: "Codec vidéo",
    edition: "Édition",
};

/* ════════════════════════════════════════════════════════════════
   Composant
   ════════════════════════════════════════════════════════════════ */

export interface MediaTechBadgesProps {
    specs?: MediaTechSpecs | null;
    variant?: "card" | "hero";
    /** "card" : nombre maximum de pastilles (3 par défaut). */
    max?: number;
    /**
     * "hero" : si aucune résolution n'est reconnue, affiche le nom de
     * qualité brut en premier (ex: « Unknown », profil exotique…).
     */
    fallbackToQuality?: boolean;
    className?: string;
}

export function MediaTechBadges({ specs, variant = "hero", max = 3, fallbackToQuality = false, className }: MediaTechBadgesProps) {
    if (variant === "card") {
        const badges = cardTechBadges(specs, max);
        if (badges.length === 0) return null;
        return (
            <div className={cn("flex flex-wrap items-center gap-1", className)}>
                {badges.map((b) => (
                    <span
                        key={b.kind}
                        title={`${KIND_LABELS[b.kind]} : ${b.label}`}
                        className={cn(
                            "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-bold leading-none tracking-wide ring-1 backdrop-blur-md",
                            CARD_TONES[b.tone],
                        )}
                    >
                        {b.short}
                    </span>
                ))}
            </div>
        );
    }

    const badges = parseTechSpecs(specs);
    const quality = specs?.quality?.trim();
    const showQuality = fallbackToQuality && !!quality && !badges.some((b) => b.kind === "resolution");
    if (badges.length === 0 && !showQuality) return null;

    // Le conteneur orchestre une cascade (scaleIn) ; initial/animate explicites
    // pour que l'animation marche aussi hors d'un parent framer-motion.
    return (
        <motion.div
            variants={stagger(0.1, 0.05)}
            initial="hidden"
            animate="show"
            className={cn("flex flex-wrap items-center gap-1.5", className)}
        >
            {showQuality && (
                <motion.span
                    variants={scaleIn}
                    whileHover={HOVER_LIFT}
                    className={cn(heroPill, HERO_TONES.neutral)}
                    title={`Qualité : ${quality}`}
                >
                    <Monitor className="h-3.5 w-3.5 opacity-80" aria-hidden />
                    {quality}
                </motion.span>
            )}
            {badges.map((b) => {
                const Icon = KIND_ICONS[b.kind];
                return (
                    <motion.span
                        key={b.kind}
                        variants={scaleIn}
                        whileHover={HOVER_LIFT}
                        title={`${KIND_LABELS[b.kind]} : ${b.label}`}
                        className={cn(
                            heroPill,
                            HERO_TONES[b.tone],
                            // Codec et édition sont secondaires : masqués sur mobile
                            // pour garder le hero sur 1-2 lignes.
                            (b.kind === "codec" || b.kind === "edition") && "hidden sm:inline-flex",
                        )}
                    >
                        <Icon className="h-3.5 w-3.5 opacity-80" aria-hidden />
                        {b.label}
                    </motion.span>
                );
            })}
        </motion.div>
    );
}
