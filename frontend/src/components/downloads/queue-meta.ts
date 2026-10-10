/**
 * Traductions et classement des états de la file *arr.
 * ----------------------------------------------------------------
 * Radarr/Sonarr exposent deux notions :
 *   - `status`        : ce que fait le CLIENT (downloading, queued, paused…)
 *   - `tracked_state` : où en est l'*arr (importPending, importBlocked…)
 * L'interface les combine en 4 « familles » pour le filtre et les couleurs :
 * en cours / en attente / import / problème.
 */
import {
    AlertTriangle,
    ArrowDownToLine,
    CheckCircle2,
    Clock,
    Hourglass,
    PackageCheck,
    Pause,
    Unplug,
    XCircle,
    type LucideIcon,
} from "lucide-react";
import type { DownloadItem } from "@/hooks/use-downloads";
import type { StatusTone } from "@/components/fx/status-dot";
import type { ProgressTone } from "@/components/fx/gradient-progress";

export type QueueBucket = "downloading" | "waiting" | "importing" | "problem";

const PROBLEM_STATUSES = new Set(["warning", "failed", "downloadclientunavailable"]);
const PROBLEM_TRACKED = new Set(["importblocked", "failedpending", "failed"]);
const IMPORT_TRACKED = new Set(["importpending", "importing", "imported"]);

/** Famille d'un élément de la file (un problème l'emporte sur le reste). */
export function bucketOf(item: DownloadItem): QueueBucket {
    const s = (item.status || "").toLowerCase();
    const t = (item.tracked_state || "").toLowerCase();
    if (item.error || PROBLEM_STATUSES.has(s) || PROBLEM_TRACKED.has(t)) return "problem";
    if (IMPORT_TRACKED.has(t) || s === "completed") return "importing";
    if (s === "downloading") return "downloading";
    return "waiting"; // queued, paused, delay, fallback…
}

export const BUCKET_META: Record<
    QueueBucket,
    { label: string; dot: StatusTone; progress: ProgressTone; accent: string }
> = {
    downloading: { label: "En cours", dot: "primary", progress: "primary", accent: "from-primary/80 to-brand/40" },
    waiting: { label: "En attente", dot: "unknown", progress: "slate", accent: "from-slate-400/50 to-slate-500/10" },
    importing: { label: "Import", dot: "success", progress: "emerald", accent: "from-emerald-400/70 to-teal-400/20" },
    problem: { label: "Problème", dot: "error", progress: "rose", accent: "from-rose-500/80 to-orange-400/30" },
};

/** Statut client traduit (+ icône). */
const STATUS_META: Record<string, { label: string; icon: LucideIcon }> = {
    downloading: { label: "Téléchargement", icon: ArrowDownToLine },
    queued: { label: "En file", icon: Clock },
    paused: { label: "En pause", icon: Pause },
    delay: { label: "Différé", icon: Hourglass },
    completed: { label: "Terminé", icon: CheckCircle2 },
    warning: { label: "Avertissement", icon: AlertTriangle },
    failed: { label: "Échec", icon: XCircle },
    downloadclientunavailable: { label: "Client injoignable", icon: Unplug },
    fallback: { label: "Repli", icon: Clock },
};

export function statusMeta(status: string): { label: string; icon: LucideIcon } {
    return STATUS_META[(status || "").toLowerCase()] ?? { label: status || "Inconnu", icon: Clock };
}

/** État de suivi *arr traduit — explique pourquoi un élément reste à 100 %. */
const TRACKED_META: Record<string, { label: string; tone: "info" | "warning" | "danger" | "success"; icon: LucideIcon }> = {
    importpending: { label: "Import en attente", tone: "warning", icon: Hourglass },
    importing: { label: "Import en cours", tone: "success", icon: PackageCheck },
    imported: { label: "Importé", tone: "success", icon: PackageCheck },
    importblocked: { label: "Import bloqué", tone: "danger", icon: AlertTriangle },
    failedpending: { label: "Échec — en attente de traitement", tone: "danger", icon: XCircle },
    failed: { label: "Échec du téléchargement", tone: "danger", icon: XCircle },
    ignored: { label: "Ignoré", tone: "info", icon: Clock },
};

export function trackedMeta(state?: string | null) {
    if (!state) return null;
    return TRACKED_META[state.toLowerCase()] ?? null;
}

/**
 * Temps restant *arr → secondes.
 * Formats rencontrés : « 00:12:34 », « 1.02:03:04 » (jours.heures:min:s).
 */
export function parseTimeLeft(value: string | null | undefined): number | null {
    if (!value) return null;
    const m = /^(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})/.exec(value.trim());
    if (!m) return null;
    const [, d, h, min, s] = m;
    const total = Number(d || 0) * 86400 + Number(h) * 3600 + Number(min) * 60 + Number(s);
    return total > 0 ? total : null;
}

/** Lien vers la fiche média (si l'*arr a renvoyé l'id du film / de la série). */
export function mediaHref(item: Pick<DownloadItem, "movie_id" | "series_id">): string | null {
    if (item.movie_id) return `/media/movie/${item.movie_id}`;
    if (item.series_id) return `/media/series/${item.series_id}`;
    return null;
}

/**
 * Taille « humaine » renvoyée par SABnzbd (« 6.4 GB ») → format FR
 * (« 6,4 Go »), pour rester cohérent avec formatBytes ailleurs.
 */
export function frenchSize(human: string | null | undefined): string {
    if (!human) return "—";
    const units: Record<string, string> = { B: "o", KB: "Ko", K: "Ko", MB: "Mo", M: "Mo", GB: "Go", G: "Go", TB: "To", T: "To" };
    const m = /^\s*([\d.,]+)\s*([KMGT]?B?)\s*$/i.exec(human);
    if (!m) return human;
    const value = Number(m[1].replace(",", "."));
    const unit = units[m[2].toUpperCase()] ?? m[2];
    return Number.isFinite(value) ? `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${unit}` : human;
}
