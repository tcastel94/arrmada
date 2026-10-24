/**
 * Libellés et couleurs du Journal d'activité.
 * ----------------------------------------------------------------
 * Une seule source pour : les catégories (chips de filtre + pastilles de la
 * timeline), les actions (« Téléchargement lancé », « Importé »…) et les
 * sources (Radarr, Kodi…). Avant, « grab » donnait « Grab lancé » et
 * « grabbed » « Téléchargement lancé » ; la catégorie `system` et l'action
 * `cast_play` n'avaient pas de libellé.
 */
import {
    Activity,
    Captions,
    CheckCircle2,
    Cog,
    Download,
    Library,
    MonitorPlay,
    PenLine,
    Play,
    Plus,
    Search,
    Send,
    Trash2,
    XCircle,
    Cast,
    type LucideIcon,
} from "lucide-react";
import type { TimelineItem } from "@/hooks/use-activity";

export interface CategoryMeta {
    key: string;
    label: string;
    icon: LucideIcon;
    /** Couleur du texte / de l'icône. */
    text: string;
    /** Tuile de la pastille (fond dégradé + liseré). */
    tile: string;
    /** Couleur du halo lumineux (CSS). */
    glow: string;
}

export const CATEGORIES: CategoryMeta[] = [
    {
        key: "download",
        label: "Téléchargements",
        icon: Download,
        text: "text-primary",
        tile: "from-sky-500/30 to-cyan-500/10 ring-primary/30",
        glow: "hsl(199 89% 60% / 0.55)",
    },
    {
        key: "subtitle",
        label: "Sous-titres",
        icon: Captions,
        text: "text-indigo-300",
        tile: "from-indigo-500/30 to-blue-500/10 ring-indigo-400/30",
        glow: "hsl(234 89% 70% / 0.5)",
    },
    {
        key: "playback",
        label: "Lectures",
        icon: Play,
        text: "text-primary",
        tile: "from-violet-500/30 to-fuchsia-500/10 ring-primary/30",
        glow: "hsl(262 83% 65% / 0.55)",
    },
    {
        key: "library",
        label: "Bibliothèque",
        icon: Library,
        text: "text-warning",
        tile: "from-amber-500/30 to-orange-500/10 ring-warning/30",
        glow: "hsl(38 95% 58% / 0.5)",
    },
    {
        key: "telegram",
        label: "Telegram",
        icon: Send,
        text: "text-primary",
        tile: "from-cyan-500/30 to-teal-500/10 ring-cyan-400/30",
        glow: "hsl(187 85% 53% / 0.5)",
    },
    {
        key: "system",
        label: "Système",
        icon: Cog,
        text: "text-slate-300",
        tile: "from-slate-400/25 to-slate-500/10 ring-slate-400/30",
        glow: "hsl(215 20% 60% / 0.45)",
    },
];

const FALLBACK_CATEGORY: CategoryMeta = {
    key: "other",
    label: "Autre",
    icon: Activity,
    text: "text-muted-foreground",
    tile: "from-slate-500/20 to-slate-500/5 ring-white/10",
    glow: "hsl(215 20% 60% / 0.35)",
};

export function categoryMeta(key: string | null | undefined): CategoryMeta {
    return CATEGORIES.find((c) => c.key === key) ?? FALLBACK_CATEGORY;
}

/** Actions → libellé FR. « grab » (ArrMada) et « grabbed » (*arr) sont unifiés. */
const ACTION_LABELS: Record<string, string> = {
    grabbed: "Téléchargement lancé",
    grab: "Téléchargement lancé",
    imported: "Importé",
    downloadFolderImported: "Importé",
    downloadFailed: "Échec du téléchargement",
    failed: "Échec",
    sub_download: "Sous-titre téléchargé",
    sub_sync: "Sous-titre synchronisé",
    kodi_play: "Lecture sur Kodi",
    cast_play: "Lecture sur Chromecast",
    search: "Recherche lancée",
    delete: "Supprimé",
    add: "Ajouté",
    episodeFileDeleted: "Fichier supprimé",
    movieFileDeleted: "Fichier supprimé",
    movieDeleted: "Film supprimé",
    seriesDeleted: "Série supprimée",
    episodeFileRenamed: "Renommé",
    movieFileRenamed: "Renommé",
};

/** Action inconnue : « someAction_name » → « Some action name ». */
function humanize(action: string): string {
    const words = action
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/[_-]+/g, " ")
        .trim()
        .toLowerCase();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Évènement";
}

export function actionLabel(action: string, status?: TimelineItem["status"]): string {
    const base = ACTION_LABELS[action] ?? humanize(action);
    // Un « grab » en échec (côté ArrMada) n'a rien d'un « téléchargement lancé ».
    if (status === "ko" && (action === "grab" || action === "grabbed")) return "Échec du lancement";
    return base;
}

export const SOURCE_LABELS: Record<string, string> = {
    arrmada: "ArrMada",
    kodi: "Kodi",
    radarr: "Radarr",
    sonarr: "Sonarr",
    bazarr: "Bazarr",
    telegram: "Telegram",
    external: "Externe",
};

export function sourceLabel(source: string): string {
    return SOURCE_LABELS[source] ?? source;
}

/** Icône précise d'une ligne (plus parlante que l'icône de catégorie). */
export function actionIcon(item: TimelineItem): LucideIcon {
    if (item.status === "ko") return XCircle;
    switch (item.action) {
        case "imported":
        case "downloadFolderImported":
            return CheckCircle2;
        case "grabbed":
        case "grab":
            return Download;
        case "sub_download":
        case "sub_sync":
            return Captions;
        case "kodi_play":
            return MonitorPlay;
        case "cast_play":
            return Cast;
        case "search":
            return Search;
        case "delete":
        case "movieDeleted":
        case "seriesDeleted":
        case "episodeFileDeleted":
        case "movieFileDeleted":
            return Trash2;
        case "episodeFileRenamed":
        case "movieFileRenamed":
            return PenLine;
        case "add":
            return item.source === "telegram" ? Send : Plus;
        default:
            return categoryMeta(item.category).icon;
    }
}

/** Lien vers la fiche média, si l'évènement en porte l'identifiant. */
export function timelineHref(item: Pick<TimelineItem, "media_type" | "media_id">): string | null {
    if (!item.media_type || !item.media_id) return null;
    if (item.media_type !== "movie" && item.media_type !== "series") return null;
    return `/media/${item.media_type}/${item.media_id}`;
}
