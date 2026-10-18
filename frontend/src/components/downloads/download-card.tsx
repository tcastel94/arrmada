"use client";

/**
 * Carte « live » d'un élément de la file de téléchargement.
 * ----------------------------------------------------------------
 * Affiche : affiche du média (si connue), titre cliquable vers la fiche,
 * état (pastille pulsée), client, qualité, indexer, barre de progression
 * animée (rayures tant que ça télécharge), taille faite / totale, débit
 * estimé, temps restant, et l'état de suivi *arr traduit avec le message
 * complet dépliable. Les actions (Relancer, Supprimer + blocklist,
 * Supprimer) sont des boutons icône sur grand écran et un menu sur mobile.
 * Pendant qu'une action tourne sur CETTE ligne, la carte est grisée avec
 * un indicateur — les autres lignes restent utilisables.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { forwardRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    Ban,
    ChevronDown,
    Film,
    Gauge,
    Info,
    Loader2,
    MoreVertical,
    RotateCw,
    Timer,
    Trash2,
    Tv,
    XCircle,
    type LucideIcon,
} from "lucide-react";
import type { DownloadItem } from "@/hooks/use-downloads";
import { ClientBadge } from "@/components/shared/download-client";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatBytes, formatDuration, formatSpeed } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { BUCKET_META, bucketOf, mediaHref, parseTimeLeft, statusMeta, trackedMeta } from "./queue-meta";

export type QueueActionKind = "retry" | "blocklist" | "remove";

interface DownloadCardProps {
    item: DownloadItem;
    posterUrl: string | null;
    /** Débit estimé (octets/s) — undefined si inconnu. */
    speed?: number;
    /** Une action est en cours sur cette ligne. */
    pending: boolean;
    onAction: (kind: QueueActionKind) => void;
    /** Rang dans la liste (pour limiter la cascade d'entrée aux ~20 premiers). */
    index: number;
}

const ACTIONS: Array<{ kind: QueueActionKind; label: string; icon: typeof RotateCw; className: string }> = [
    { kind: "retry", label: "Relancer (blocklist + nouvelle recherche)", icon: RotateCw, className: "hover:text-primary" },
    { kind: "blocklist", label: "Supprimer et blocklister", icon: Ban, className: "hover:text-amber-300" },
    { kind: "remove", label: "Supprimer de la file", icon: Trash2, className: "hover:text-red-400" },
];

const TRACK_TONES = {
    info: "border-white/[0.06] bg-white/[0.03] text-muted-foreground",
    success: "border-emerald-500/20 bg-emerald-500/[0.07] text-emerald-300",
    warning: "border-amber-500/20 bg-amber-500/[0.07] text-amber-300",
    danger: "border-red-500/25 bg-red-500/[0.08] text-red-300",
} as const;

// forwardRef : AnimatePresence en mode « popLayout » doit pouvoir mesurer
// la carte qui sort pour faire glisser les suivantes.
export const DownloadCard = forwardRef<HTMLLIElement, DownloadCardProps>(function DownloadCard(
    { item, posterUrl, speed, pending, onAction, index },
    ref,
) {
    const [open, setOpen] = useState(false);
    const [imgFailed, setImgFailed] = useState(false);

    const bucket = bucketOf(item);
    const bm = BUCKET_META[bucket];
    const status = statusMeta(item.status);
    const tracked = trackedMeta(item.tracked_state);
    const href = mediaHref(item);
    const progress = Math.max(0, Math.min(100, item.progress || 0));
    const done = Math.max(0, (item.size_bytes || 0) - (item.size_left_bytes || 0));
    const eta = parseTimeLeft(item.time_left);
    const isDownloading = bucket === "downloading";
    const MediaIcon = item.series_id ? Tv : Film;

    // Message long (erreur du client ou explication *arr) → zone dépliable.
    const message = item.error || item.detail || "";
    let banner: { label: string; tone: keyof typeof TRACK_TONES; Icon: LucideIcon } | null = null;
    if (item.error) {
        // Vraie erreur du client : toujours en rouge, avec l'état *arr s'il est parlant.
        banner = { label: tracked?.tone === "danger" ? tracked.label : "Erreur de téléchargement", tone: "danger", Icon: XCircle };
    } else if (tracked) {
        banner = { label: tracked.label, tone: tracked.tone, Icon: tracked.icon };
    } else if (message) {
        banner = { label: "Information", tone: "info", Icon: Info };
    }

    return (
        <motion.li
            ref={ref}
            layout
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.45, ease: EASE_OUT, delay: Math.min(index, 20) * 0.04 } }}
            exit={{ opacity: 0, x: 60, scale: 0.96, transition: { duration: 0.3, ease: EASE_OUT } }}
            className={cn(
                "glass glass-hover group relative list-none overflow-hidden rounded-2xl",
                pending && "pointer-events-none",
            )}
            aria-busy={pending}
        >
            {/* Liseré vertical coloré selon la famille d'état */}
            <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b", bm.accent)} />

            <div className={cn("flex gap-3 p-3.5 pl-4 transition-opacity sm:gap-4 sm:p-4 sm:pl-5", pending && "opacity-50")}>
                {/* Affiche (ou tuile d'icône si inconnue) */}
                <div className="relative h-[72px] w-12 shrink-0 overflow-hidden rounded-lg bg-muted/40 ring-1 ring-white/[0.07] sm:h-20 sm:w-[54px]">
                    {posterUrl && !imgFailed ? (
                        <img
                            src={posterUrl}
                            alt={item.title}
                            loading="lazy"
                            onError={() => setImgFailed(true)}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/70 via-muted/30 to-primary/15">
                            <MediaIcon className="h-5 w-5 text-muted-foreground/50" strokeWidth={1.6} />
                        </div>
                    )}
                    {isDownloading && (
                        <span
                            aria-hidden
                            className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-primary/35 to-transparent"
                        />
                    )}
                </div>

                <div className="min-w-0 flex-1">
                    <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1">
                            {href ? (
                                <Link
                                    href={href}
                                    className="block truncate text-sm font-semibold tracking-tight transition-colors hover:text-primary focus-visible:text-primary focus-visible:outline-none"
                                    title={item.title}
                                >
                                    {item.title}
                                </Link>
                            ) : (
                                <p className="truncate text-sm font-semibold tracking-tight" title={item.title}>
                                    {item.title}
                                </p>
                            )}
                            <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                                <span className="inline-flex items-center gap-1.5 font-medium text-foreground/85">
                                    <StatusDot tone={bm.dot} pulse={isDownloading} size="sm" />
                                    {status.label}
                                </span>
                                <ClientBadge client={item.download_client} protocol={item.protocol} />
                                {(item.episode_count ?? 0) > 1 && (
                                    <span className="rounded-md bg-primary/10 px-1.5 py-px text-[10px] font-semibold text-primary ring-1 ring-inset ring-primary/20">
                                        {item.episode_count} épisodes
                                    </span>
                                )}
                                {item.quality && (
                                    <span className="rounded-md bg-white/[0.05] px-1.5 py-px text-[10px] font-semibold text-foreground/80 ring-1 ring-inset ring-white/[0.08]">
                                        {item.quality}
                                    </span>
                                )}
                                {item.indexer && <span className="truncate">via {item.indexer}</span>}
                                <span className="hidden text-muted-foreground/60 sm:inline">· {item.source_service}</span>
                            </div>
                        </div>

                        {/* Pourcentage */}
                        <div className="shrink-0 pl-1 text-right">
                            <span
                                className={cn(
                                    "text-base font-bold tabular-nums sm:text-lg",
                                    isDownloading ? "text-gradient" : "text-foreground/80",
                                )}
                            >
                                {progress.toLocaleString("fr-FR", { maximumFractionDigits: progress < 10 ? 1 : 0 })}
                                <span className="text-xs font-semibold text-muted-foreground"> %</span>
                            </span>
                        </div>

                        {/* Actions — boutons icône (≥ sm) */}
                        <div className="hidden shrink-0 items-center gap-0.5 sm:flex">
                            {pending ? (
                                <span className="flex h-8 w-8 items-center justify-center" role="status" aria-label="Action en cours">
                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                </span>
                            ) : (
                                ACTIONS.map((a) => (
                                    <Tooltip key={a.kind}>
                                        <TooltipTrigger asChild>
                                            <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                aria-label={`${a.label} : ${item.title}`}
                                                className={cn("text-muted-foreground", a.className)}
                                                onClick={() => onAction(a.kind)}
                                            >
                                                <a.icon />
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>{a.label}</TooltipContent>
                                    </Tooltip>
                                ))
                            )}
                        </div>

                        {/* Actions — menu (mobile) */}
                        <div className="shrink-0 sm:hidden">
                            {pending ? (
                                <span className="flex h-8 w-8 items-center justify-center" role="status" aria-label="Action en cours">
                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                </span>
                            ) : (
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button variant="ghost" size="icon-sm" aria-label={`Actions pour ${item.title}`}>
                                            <MoreVertical />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-60">
                                        <DropdownMenuItem onSelect={() => onAction("retry")}>
                                            <RotateCw /> Relancer
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem onSelect={() => onAction("blocklist")} className="text-amber-300 focus:text-amber-200">
                                            <Ban /> Supprimer + blocklist
                                        </DropdownMenuItem>
                                        <DropdownMenuItem onSelect={() => onAction("remove")} className="text-red-400 focus:text-red-300">
                                            <Trash2 /> Supprimer
                                        </DropdownMenuItem>
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            )}
                        </div>
                    </div>

                    {/* Progression */}
                    <GradientProgress value={progress} tone={bm.progress} active={isDownloading} glow={isDownloading} className="mt-3" />

                    <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11px] text-muted-foreground tabular-nums">
                        {done > 0 ? (
                            <span>
                                <span className="font-medium text-foreground/85">{formatBytes(done)}</span> / {formatBytes(item.size_bytes)}
                            </span>
                        ) : (
                            <span>{formatBytes(item.size_bytes)} à télécharger</span>
                        )}
                        <span className="flex items-center gap-3">
                            {speed ? (
                                <span className="inline-flex items-center gap-1 text-primary" title="Débit estimé entre deux rafraîchissements">
                                    <Gauge className="h-3 w-3" />
                                    {formatSpeed(speed)}
                                </span>
                            ) : null}
                            {eta && bucket !== "importing" ? (
                                <span className="inline-flex items-center gap-1" title="Temps restant estimé par le client">
                                    <Timer className="h-3 w-3" />
                                    {formatDuration(eta)}
                                </span>
                            ) : null}
                        </span>
                    </div>

                    {/* État de suivi *arr + message dépliable */}
                    {banner && (
                        <div className={cn("mt-2.5 rounded-xl border text-[11px]", TRACK_TONES[banner.tone])}>
                            {message ? (
                                <button
                                    type="button"
                                    onClick={() => setOpen((o) => !o)}
                                    aria-expanded={open}
                                    className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left"
                                >
                                    <banner.Icon className="h-3.5 w-3.5 shrink-0" />
                                    <span className="font-semibold">{banner.label}</span>
                                    {!open && <span className="min-w-0 flex-1 truncate opacity-75">— {message}</span>}
                                    {open && <span className="flex-1" />}
                                    <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-300", open && "rotate-180")} />
                                    <span className="sr-only">{open ? "Masquer le détail" : "Afficher le détail"}</span>
                                </button>
                            ) : (
                                <p className="flex items-center gap-1.5 px-2.5 py-1.5">
                                    <banner.Icon className="h-3.5 w-3.5 shrink-0" />
                                    <span className="font-semibold">{banner.label}</span>
                                </p>
                            )}
                            <AnimatePresence initial={false}>
                                {open && message && (
                                    <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: "auto", opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.3, ease: EASE_OUT }}
                                        className="overflow-hidden"
                                    >
                                        <p className="whitespace-pre-wrap break-words border-t border-white/[0.06] px-2.5 py-2 leading-relaxed text-foreground/80">
                                            {message}
                                        </p>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
            </div>

            {/* Voile « action en cours » */}
            {pending && (
                <div aria-hidden className="absolute inset-0 overflow-hidden rounded-2xl">
                    <div className="shimmer absolute inset-0 opacity-40" />
                </div>
            )}
        </motion.li>
    );
});
