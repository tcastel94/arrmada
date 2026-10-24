/**
 * Données de l'assistant TRaSH : étapes et choix proposés.
 * ----------------------------------------------------------------
 * Séparées du composant pour rester lisibles. Les icônes lucide
 * remplacent les anciens emojis (rendu inégal selon l'OS, drapeaux
 * affichés en lettres sous Windows).
 */
import {
    AudioLines,
    Captions,
    Clapperboard,
    Eye,
    Flag,
    Gauge,
    Gem,
    Globe,
    Headphones,
    Languages,
    Monitor,
    MonitorPlay,
    Smartphone,
    Sparkles,
    Speaker,
    Sun,
    SunMoon,
    Swords,
    Trophy,
    Tv,
    Volume2,
    type LucideIcon,
} from "lucide-react";
import type { MediaPreferences } from "@/hooks/use-trash-guides";

export interface WizardOption<V extends string> {
    value: V;
    label: string;
    desc: string;
    icon: LucideIcon;
    /** Petit ruban « Recommandé ». */
    recommended?: boolean;
}

export const STEPS = [
    { id: "display", title: "Écran", icon: Monitor, question: "Quel type d'écran utilises-tu ?", help: "Détermine les formats HDR à privilégier." },
    { id: "audio", title: "Audio", icon: Volume2, question: "Quel système audio as-tu ?", help: "Détermine les codecs audio à favoriser." },
    { id: "language", title: "Langue", icon: Languages, question: "En quelle langue regardes-tu ?", help: "Les formats personnalisés de langue seront ajustés." },
    { id: "quality", title: "Qualité", icon: Gauge, question: "Quelle qualité préfères-tu ?", help: "Le profil qualité sera adapté à ton choix." },
    { id: "content", title: "Contenu", icon: Tv, question: "Quel contenu regardes-tu ?", help: "Active des formats spécifiques à certains contenus." },
    { id: "review", title: "Résumé", icon: Eye, question: "Tes recommandations TRaSH Guides", help: "La configuration optimale pour tes réponses." },
] as const;

export const DISPLAY_OPTIONS: WizardOption<MediaPreferences["display_type"]>[] = [
    { value: "sdr", label: "SDR", desc: "Écran standard, sans HDR", icon: Monitor },
    { value: "hdr10", label: "HDR10", desc: "HDR standard : la plupart des TV 4K", icon: Sun },
    { value: "hdr10plus", label: "HDR10+", desc: "HDR dynamique (Samsung…)", icon: SunMoon },
    { value: "dolby_vision", label: "Dolby Vision", desc: "HDR premium : LG OLED, Apple TV…", icon: Clapperboard },
    {
        value: "dv_hdr10_fallback",
        label: "Dolby Vision + HDR10",
        desc: "Dolby Vision, avec repli HDR10 sur les appareils non compatibles",
        icon: Trophy,
    },
];

export const AUDIO_OPTIONS: WizardOption<MediaPreferences["audio_type"]>[] = [
    { value: "stereo", label: "Stéréo", desc: "TV, casque, enceintes 2.0", icon: Headphones },
    { value: "surround_51", label: "5.1", desc: "Home cinéma classique", icon: Speaker },
    { value: "surround_71", label: "7.1", desc: "Home cinéma avancé", icon: AudioLines },
    { value: "atmos", label: "Dolby Atmos", desc: "Son immersif, barre de son Atmos", icon: Sparkles },
];

export const LANGUAGE_OPTIONS: WizardOption<MediaPreferences["language"]>[] = [
    { value: "multi", label: "Multi", desc: "Français + version originale : le meilleur choix", icon: Sparkles, recommended: true },
    { value: "vf", label: "VF", desc: "Version française uniquement", icon: Languages },
    { value: "vo", label: "VO", desc: "Version originale uniquement", icon: Globe },
    { value: "vostfr", label: "VOSTFR", desc: "VO avec sous-titres français", icon: Captions },
];

export const QUALITY_OPTIONS: WizardOption<MediaPreferences["quality"]>[] = [
    { value: "720p", label: "720p", desc: "Léger, pour les connexions limitées", icon: Smartphone },
    { value: "1080p", label: "1080p", desc: "Full HD : le standard", icon: MonitorPlay },
    { value: "2160p", label: "4K", desc: "Ultra HD : la meilleure image", icon: Tv },
    { value: "best", label: "Meilleure dispo", desc: "Prend la meilleure qualité disponible", icon: Gem },
];

export const CONTENT_TOGGLES: {
    key: "watches_anime" | "watches_french_series";
    label: string;
    desc: string;
    icon: LucideIcon;
}[] = [
    {
        key: "watches_anime",
        label: "Anime",
        desc: "Formats anime : niveaux de fansub, double audio, groupes BD/Web",
        icon: Swords,
    },
    {
        key: "watches_french_series",
        label: "Séries françaises",
        desc: "Formats français : groupes FR, scène française, MyCanal, ADN",
        icon: Flag,
    },
];

/**
 * Valeurs par défaut. Langue = Multi (présentée comme « meilleur choix » ;
 * l'ancien défaut « vo » contredisait l'interface).
 */
export const DEFAULT_PREFS: MediaPreferences = {
    display_type: "dv_hdr10_fallback",
    audio_type: "atmos",
    language: "multi",
    quality: "1080p",
    watches_anime: false,
    watches_french_series: false,
};

/** Couleurs (statiques) des catégories de formats personnalisés. */
export const CF_CATEGORY: Record<string, { label: string; cls: string }> = {
    hdr: { label: "HDR", cls: "border-warning/30 bg-warning/10 text-warning" },
    audio: { label: "Audio", cls: "border-sky-400/30 bg-primary/10 text-primary" },
    language: { label: "Langue", cls: "border-success/30 bg-success/10 text-success" },
    anime: { label: "Anime", cls: "border-pink-400/30 bg-pink-500/10 text-pink-300" },
    unwanted: { label: "Indésirable", cls: "border-destructive/30 bg-destructive/10 text-destructive" },
    quality: { label: "Qualité", cls: "border-primary/30 bg-primary/10 text-primary" },
};

export const CF_FALLBACK = { label: "Autre", cls: "border-white/10 bg-white/[0.04] text-muted-foreground" };
