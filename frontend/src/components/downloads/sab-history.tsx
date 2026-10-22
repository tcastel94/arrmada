"use client";

/**
 * Historique SABnzbd (onglet Imports).
 * ----------------------------------------------------------------
 * Corrections par rapport à l'ancienne page /fichiers :
 *  - statuts traduits (plus de « Completed / Failed » bruts) ;
 *  - une erreur API affiche une vraie erreur + « Réessayer » (avant :
 *    « vide ou non configuré », trompeur) ;
 *  - pagination « Voir plus » : 25 lignes à la fois, et on demande davantage
 *    au backend seulement quand on arrive au bout (100 lignes animées d'un
 *    coup = saccades) ;
 *  - filtre Terminés / Échecs / Bloqués, journal de traitement dépliable.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FolderInput, FolderOpen, History, Loader2, ScrollText } from "lucide-react";
import { SAB_HISTORY_MAX, useSabnzbdHistory, type HistoryItem } from "@/hooks/use-files";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { StatusDot, type StatusTone } from "@/components/fx/status-dot";
import { Segmented } from "@/components/activity/segmented";
import { Button } from "@/components/ui/button";
import { formatBytes, formatLongDateTime, plural, timeAgo } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { frenchSize } from "./queue-meta";

const PAGE = 25;
const FETCH_STEP = 50;

/** Statuts SABnzbd → libellé FR + teinte. */
const SAB_STATUS: Record<string, { label: string; tone: StatusTone; text: string }> = {
    completed: { label: "Terminé", tone: "success", text: "text-success" },
    failed: { label: "Échec", tone: "error", text: "text-destructive" },
    queued: { label: "En file", tone: "unknown", text: "text-muted-foreground" },
    downloading: { label: "Téléchargement", tone: "primary", text: "text-primary" },
    paused: { label: "En pause", tone: "warning", text: "text-warning" },
    fetching: { label: "Récupération", tone: "primary", text: "text-primary" },
    propagating: { label: "Propagation", tone: "warning", text: "text-warning" },
    quickcheck: { label: "Vérif. rapide", tone: "warning", text: "text-warning" },
    verifying: { label: "Vérification", tone: "warning", text: "text-warning" },
    repairing: { label: "Réparation", tone: "warning", text: "text-warning" },
    extracting: { label: "Extraction", tone: "warning", text: "text-warning" },
    moving: { label: "Déplacement", tone: "warning", text: "text-warning" },
    running: { label: "Script en cours", tone: "warning", text: "text-warning" },
};

function sabStatus(status: string) {
    return SAB_STATUS[(status || "").toLowerCase()] ?? { label: status || "Inconnu", tone: "unknown" as StatusTone, text: "text-muted-foreground" };
}

/** SABnzbd donne des secondes UNIX ; on tolère aussi des millisecondes. */
function completedDate(v: number | null): Date | null {
    if (!v) return null;
    return new Date(v > 1e12 ? v : v * 1000);
}

type HistoryFilter = "all" | "completed" | "failed" | "stuck";

export function SabHistory() {
    const [limit, setLimit] = useState(FETCH_STEP);
    const [shown, setShown] = useState(PAGE);
    const [filter, setFilter] = useState<HistoryFilter>("all");
    const { data, isLoading, isError, error, refetch, isFetching, isPlaceholderData } = useSabnzbdHistory(limit);

    const items = useMemo(() => data?.items ?? [], [data]);
    const counts = useMemo(
        () => ({
            completed: items.filter((i) => i.status.toLowerCase() === "completed").length,
            failed: items.filter((i) => i.status.toLowerCase() === "failed").length,
            stuck: items.filter((i) => i.is_stuck).length,
        }),
        [items],
    );
    const filtered = useMemo(() => {
        switch (filter) {
            case "completed":
                return items.filter((i) => i.status.toLowerCase() === "completed");
            case "failed":
                return items.filter((i) => i.status.toLowerCase() === "failed");
            case "stuck":
                return items.filter((i) => i.is_stuck);
            default:
                return items;
        }
    }, [items, filter]);

    // Le backend peut avoir plus de lignes si on a reçu exactement `limit`.
    const canFetchMore = items.length >= limit && limit < SAB_HISTORY_MAX;
    const hasMore = shown < filtered.length || canFetchMore;
    const loadingMore = isFetching && isPlaceholderData;

    const showMore = () => {
        const next = shown + PAGE;
        setShown(next);
        if (next > items.length && canFetchMore) setLimit((l) => Math.min(l + FETCH_STEP, SAB_HISTORY_MAX));
    };

    if (isLoading) {
        return (
            <SpotlightCard interactive={false} className="space-y-2 p-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Shimmer key={i} className="h-14 w-full" />
                ))}
            </SpotlightCard>
        );
    }
    if (isError) {
        return (
            <SpotlightCard interactive={false}>
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de lire l'historique SABnzbd" />
            </SpotlightCard>
        );
    }
    if (items.length === 0) {
        return (
            <SpotlightCard interactive={false}>
                <EmptyState
                    icon={History}
                    title="Historique vide"
                    description="SABnzbd n'a encore rien terminé, ou il n'est pas déclaré dans les services."
                    action={{ label: "Voir les services", href: "/settings/services" }}
                />
            </SpotlightCard>
        );
    }

    const page = filtered.slice(0, shown);

    return (
        <SpotlightCard interactive={false} className="overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-white/[0.05] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                <p className="text-xs text-muted-foreground">
                    {plural(items.length, "téléchargement")} récent{items.length > 1 ? "s" : ""}
                    {canFetchMore ? " (et plus)" : ""}
                </p>
                <Segmented<HistoryFilter>
                    ariaLabel="Filtrer l'historique"
                    size="sm"
                    value={filter}
                    onChange={(f) => {
                        setFilter(f);
                        setShown(PAGE);
                    }}
                    options={[
                        { value: "all", label: "Tous", count: items.length },
                        { value: "completed", label: "Terminés", count: counts.completed, tone: "text-success" },
                        { value: "failed", label: "Échecs", count: counts.failed, tone: "text-destructive" },
                        { value: "stuck", label: "Bloqués", count: counts.stuck, tone: "text-warning" },
                    ]}
                />
            </div>

            {filtered.length === 0 ? (
                <EmptyState compact icon={FolderOpen} title="Rien dans cette catégorie" action={{ label: "Tout afficher", onClick: () => setFilter("all") }} />
            ) : (
                <ul className="divide-y divide-white/[0.04]">
                    {page.map((item, i) => (
                        <HistoryRow key={item.nzo_id || `${item.name}-${item.completed_at}`} item={item} delay={i < PAGE ? i * 0.025 : 0} />
                    ))}
                </ul>
            )}

            {hasMore && filtered.length > 0 && (
                <div className="flex items-center justify-center gap-3 border-t border-white/[0.05] px-4 py-3">
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                        {Math.min(shown, filtered.length)} sur {filtered.length}
                        {canFetchMore ? "+" : ""}
                    </span>
                    <Button variant="outline" size="sm" onClick={showMore} disabled={loadingMore}>
                        {loadingMore && <Loader2 className="animate-spin" />}
                        Voir plus
                    </Button>
                </div>
            )}
        </SpotlightCard>
    );
}

function HistoryRow({ item, delay }: { item: HistoryItem; delay: number }) {
    const [open, setOpen] = useState(false);
    const st = sabStatus(item.status);
    const done = completedDate(item.completed_at);
    const hasLog = item.stage_log?.length > 0 || !!item.script_log;

    return (
        <motion.li
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: EASE_OUT, delay }}
            className={cn("px-4 py-3 transition-colors hover:bg-white/[0.02] sm:px-5", item.is_stuck && "bg-warning/[0.04]")}
        >
            <div className="flex items-start gap-3">
                <StatusDot tone={st.tone} pulse={false} className="mt-1.5" />
                <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <p className="min-w-0 truncate text-sm font-medium" title={item.name}>
                            {item.name}
                        </p>
                        {item.is_stuck && (
                            <span className="rounded-md bg-warning/15 px-1.5 py-px text-[10px] font-semibold text-warning ring-1 ring-inset ring-warning/25">
                                Bloqué
                            </span>
                        )}
                    </div>
                    {item.storage_path && (
                        <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                            <FolderInput className="h-3 w-3 shrink-0" />
                            <code className="truncate font-mono" title={item.storage_path}>
                                {item.storage_path}
                            </code>
                        </p>
                    )}
                    {item.download_path && item.download_path !== item.storage_path && (
                        <p className="flex items-center gap-1.5 text-[11px] text-orange-300/80" title="Dossier de téléchargement (différent du dossier final)">
                            <FolderOpen className="h-3 w-3 shrink-0" />
                            <code className="truncate font-mono">{item.download_path}</code>
                        </p>
                    )}
                    {item.fail_message && <p className="text-[11px] text-destructive">{item.fail_message}</p>}
                    {hasLog && (
                        <button
                            type="button"
                            onClick={() => setOpen((o) => !o)}
                            aria-expanded={open}
                            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                        >
                            <ScrollText className="h-3 w-3" />
                            Journal de traitement
                            <ChevronDown className={cn("h-3 w-3 transition-transform duration-300", open && "rotate-180")} />
                        </button>
                    )}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1 text-right">
                    <span className={cn("text-xs font-semibold", st.text)}>{st.label}</span>
                    <span className="text-[11px] tabular-nums text-muted-foreground">
                        {item.size_bytes ? formatBytes(item.size_bytes) : frenchSize(item.size_human)}
                    </span>
                    {item.category && <span className="text-[10px] text-muted-foreground/70">{item.category}</span>}
                    {done && (
                        <span className="text-[10px] text-muted-foreground/70" title={formatLongDateTime(done)}>
                            {timeAgo(done)}
                        </span>
                    )}
                </div>
            </div>

            <AnimatePresence initial={false}>
                {open && hasLog && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: EASE_OUT }}
                        className="overflow-hidden"
                    >
                        <div className="ml-5 mt-2 space-y-2 rounded-xl border border-white/[0.06] bg-background/40 p-3 text-[11px]">
                            {item.stage_log?.map((s) => (
                                <div key={s.stage}>
                                    <p className="font-semibold text-foreground/85">{s.stage}</p>
                                    <ul className="mt-0.5 space-y-0.5 text-muted-foreground">
                                        {s.actions.map((a, i) => (
                                            // Lignes de log brutes, sans identifiant : l'index est la seule clé stable.
                                            <li key={i} className="break-words">
                                                {a}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                            {item.script_log && (
                                <pre className="whitespace-pre-wrap break-words font-mono text-[10px] text-muted-foreground">{item.script_log}</pre>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.li>
    );
}
