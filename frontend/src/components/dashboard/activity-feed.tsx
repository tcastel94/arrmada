"use client";

/**
 * Fil d'activité du Dashboard : les 12 derniers évènements de la timeline
 * unifiée (téléchargements, imports, sous-titres, lectures…), avec lien
 * vers le Journal complet.
 * (Avant : historique Radarr/Sonarr seul, sans lien « Tout voir ».)
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { motion } from "framer-motion";
import {
    Activity,
    Download,
    CheckCircle2,
    XCircle,
    Captions,
    Play,
    Library,
    Send,
    Cpu,
    type LucideIcon,
} from "lucide-react";
import { useActivityTimeline, type TimelineItem } from "@/hooks/use-activity";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { timeAgo, formatBytes } from "@/lib/format";
import { stagger, slideIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

const CATEGORY: Record<string, { icon: LucideIcon; cls: string }> = {
    download: { icon: Download, cls: "text-sky-300 bg-sky-500/10 ring-sky-500/25" },
    subtitle: { icon: Captions, cls: "text-blue-300 bg-blue-500/10 ring-blue-500/25" },
    playback: { icon: Play, cls: "text-violet-300 bg-violet-500/10 ring-violet-500/25" },
    library: { icon: Library, cls: "text-amber-300 bg-amber-500/10 ring-amber-500/25" },
    telegram: { icon: Send, cls: "text-cyan-300 bg-cyan-500/10 ring-cyan-500/25" },
    system: { icon: Cpu, cls: "text-slate-300 bg-slate-500/10 ring-slate-500/25" },
};

const ACTION_LABELS: Record<string, string> = {
    grabbed: "Téléchargement lancé",
    grab: "Téléchargement lancé",
    imported: "Importé",
    downloadFolderImported: "Importé",
    downloadFailed: "Échec du téléchargement",
    failed: "Échec",
    sub_download: "Sous-titre téléchargé",
    sub_sync: "Sous-titre synchronisé",
    kodi_play: "Lecture Kodi",
    cast_play: "Lecture Cast",
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

function hrefOf(it: TimelineItem) {
    return it.media_type && it.media_id ? `/media/${it.media_type}/${it.media_id}` : undefined;
}

export function ActivityFeedCard() {
    const { data, isLoading, isError, error, refetch } = useActivityTimeline({ limit: 12 });
    const items = data?.items ?? [];

    return (
        <Panel title="Activité récente" icon={Activity} iconClassName="text-emerald-300" href="/activity" hrefLabel="Journal complet" bodyClassName="p-2">
            {isLoading ? (
                <div className="space-y-2 p-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Shimmer key={i} className="h-12" />
                    ))}
                </div>
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} />
            ) : items.length === 0 ? (
                <EmptyState compact icon={Activity} title="Calme plat" description="Les téléchargements, imports et lectures apparaîtront ici." />
            ) : (
                <motion.ol variants={stagger(0.05, 0.04)} initial="hidden" animate="show" className="relative">
                    {/* Ligne de temps */}
                    <span aria-hidden className="absolute bottom-6 left-[27px] top-6 w-px bg-gradient-to-b from-primary/40 via-white/10 to-transparent" />
                    {items.map((it) => {
                        const cat = CATEGORY[it.category] ?? CATEGORY.system;
                        const Icon = cat.icon;
                        const label = ACTION_LABELS[it.action] ?? it.action;
                        const href = hrefOf(it);
                        const inner = (
                            <>
                                <span className={cn("relative z-[1] flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ring-1 backdrop-blur", cat.cls)}>
                                    <Icon className="h-3.5 w-3.5" />
                                    {it.status !== "info" && (
                                        <span className="absolute -bottom-1 -right-1 rounded-full bg-background">
                                            {it.status === "ok" ? (
                                                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                                            ) : (
                                                <XCircle className="h-3 w-3 text-red-400" />
                                            )}
                                        </span>
                                    )}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-medium">{it.title ?? label}</p>
                                    <p className="truncate text-[11px] text-muted-foreground">
                                        <span className={it.status === "ko" ? "text-red-400" : ""}>{label}</span>
                                        {it.subtitle ? ` · ${it.subtitle}` : ""}
                                        {it.size_bytes ? ` · ${formatBytes(it.size_bytes)}` : ""}
                                        {it.device ? ` · ${it.device}` : ""}
                                    </p>
                                </div>
                                <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground/70">{timeAgo(it.ts * 1000, { short: true })}</span>
                            </>
                        );
                        return (
                            <motion.li key={it.id} variants={slideIn}>
                                {href ? (
                                    <Link href={href} className="flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-white/[0.04]">
                                        {inner}
                                    </Link>
                                ) : (
                                    <div className="flex items-center gap-3 px-3 py-2">{inner}</div>
                                )}
                            </motion.li>
                        );
                    })}
                </motion.ol>
            )}
        </Panel>
    );
}
