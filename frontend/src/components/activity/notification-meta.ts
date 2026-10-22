/**
 * Libellés et styles des notifications.
 * ----------------------------------------------------------------
 * Le backend envoie des types techniques (« service_down », « trash_sync »…)
 * que l'ancienne page affichait tels quels (« service down »). Ici : un
 * libellé FR + une icône par type, et un style par sévérité.
 */
import {
    AlertCircle,
    AlertTriangle,
    BookMarked,
    CheckCircle2,
    Download,
    HeartPulse,
    Info,
    PlugZap,
    ServerCrash,
    ServerCog,
    SlidersHorizontal,
    type LucideIcon,
} from "lucide-react";

export const TYPE_META: Record<string, { label: string; icon: LucideIcon }> = {
    service_down: { label: "Service hors ligne", icon: ServerCrash },
    service_recovered: { label: "Service rétabli", icon: PlugZap },
    trash_sync: { label: "Synchro TRaSH", icon: BookMarked },
    trash_apply: { label: "Profil TRaSH appliqué", icon: SlidersHorizontal },
    sabnzbd_config: { label: "Config SABnzbd", icon: ServerCog },
    new_import: { label: "Import", icon: Download },
    health_issue: { label: "Problème de santé", icon: HeartPulse },
};

/** Libellé d'un type inconnu : « some_type » → « Some type ». */
export function typeLabel(type: string): string {
    const meta = TYPE_META[type];
    if (meta) return meta.label;
    const words = type.replace(/[_-]+/g, " ").trim();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Notification";
}

export function typeIcon(type: string, fallback: LucideIcon): LucideIcon {
    return TYPE_META[type]?.icon ?? fallback;
}

export interface SeverityMeta {
    label: string;
    icon: LucideIcon;
    text: string;
    tile: string;
    glow: string;
    dot: "error" | "warning" | "success" | "primary";
}

export const SEVERITY: Record<string, SeverityMeta> = {
    error: {
        label: "Erreur",
        icon: AlertCircle,
        text: "text-destructive",
        tile: "from-red-500/30 to-rose-500/10 ring-destructive/30",
        glow: "hsl(0 84% 62% / 0.5)",
        dot: "error",
    },
    warning: {
        label: "Avertissement",
        icon: AlertTriangle,
        text: "text-warning",
        tile: "from-amber-500/30 to-orange-500/10 ring-warning/30",
        glow: "hsl(38 95% 58% / 0.5)",
        dot: "warning",
    },
    success: {
        label: "Succès",
        icon: CheckCircle2,
        text: "text-success",
        tile: "from-emerald-500/30 to-teal-500/10 ring-success/30",
        glow: "hsl(152 69% 47% / 0.5)",
        dot: "success",
    },
    info: {
        label: "Info",
        icon: Info,
        text: "text-primary",
        tile: "from-sky-500/30 to-primary/10 ring-primary/30",
        glow: "hsl(199 89% 60% / 0.45)",
        dot: "primary",
    },
};

export function severityMeta(severity: string): SeverityMeta {
    return SEVERITY[severity] ?? SEVERITY.info;
}

/** Notifications liées à l'état d'un service → lien « Voir le service ». */
const SERVICE_TYPES = new Set(["service_down", "service_recovered", "health_issue"]);
export function isServiceAlert(type: string): boolean {
    return SERVICE_TYPES.has(type);
}

/**
 * Retire les émojis placés en tête de titre par le backend (« 🎬 Dune »,
 * « ⚠️ Sonarr — … ») : l'icône de la carte joue déjà ce rôle.
 * (Plages Unicode écrites en paires de substitution : la cible ES2017 du
 * projet n'autorise pas les classes \p{…}.)
 */
const LEADING_EMOJI = /^(?:[\u2190-\u2BFF\u2600-\u27BF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|\uD83E[\uDC00-\uDFFF]|\uFE0F|\u200D|\s)+/;
export function cleanTitle(title: string): string {
    const cleaned = title.replace(LEADING_EMOJI, "").trim();
    return cleaned || title;
}

/** « radarr » (type brut renvoyé par certains webhooks) → « Radarr ». */
export function displayServiceName(name: string): string {
    return name === name.toLowerCase() ? name.charAt(0).toUpperCase() + name.slice(1) : name;
}
