"use client";

/**
 * Onglet « File » de /downloads.
 * ----------------------------------------------------------------
 * 1. Barre résumé : jauge de progression globale, volumes, répartition par
 *    client (barre empilée lumineuse).
 * 2. Filtres : client (chips) + famille d'état (sélecteur segmenté).
 * 3. Liste de cartes « live » : quand un élément quitte la file (terminé,
 *    supprimé), il sort en glissant et les suivantes remontent en douceur
 *    (AnimatePresence + layout).
 * 4. Actions confirmées par ConfirmDialog, exécutées en arrière-plan : la
 *    boîte se ferme tout de suite, la ligne concernée affiche son propre
 *    indicateur et un toast suit l'opération.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowDownToLine, CheckCircle2, Clock, Download, FilterX, Layers, PackageCheck } from "lucide-react";
import { toast } from "sonner";
import {
    queueItemKey,
    usePendingQueueKeys,
    useRemoveQueueItem,
    useRetryQueueItem,
    type DownloadItem,
    type DownloadsResponse,
} from "@/hooks/use-downloads";
import { getClientMeta } from "@/components/shared/download-client";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { RingGauge } from "@/components/fx/ring-gauge";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Segmented } from "@/components/activity/segmented";
import { formatBytes, percent, plural } from "@/lib/format";
import { EASE_OUT, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { DownloadCard, type QueueActionKind } from "./download-card";
import { bucketOf, type QueueBucket } from "./queue-meta";
import { posterFor, type Throughput } from "./use-queue-insights";

type StatusFilter = "all" | QueueBucket;

interface QueueTabProps {
    data: DownloadsResponse | undefined;
    isLoading: boolean;
    isError: boolean;
    error: unknown;
    refetch: () => void;
    throughput: Throughput;
    posters: Record<string, string>;
    onShowImports: () => void;
}

const ACTION_COPY: Record<
    QueueActionKind,
    { title: string; description: string; confirm: string; destructive: boolean; loading: string; success: string }
> = {
    retry: {
        title: "Relancer ce téléchargement ?",
        description:
            "La release actuelle sera blocklistée et retirée de la file, puis une nouvelle recherche automatique sera lancée.",
        confirm: "Relancer",
        destructive: false,
        loading: "Relance en cours…",
        success: "Relancé — nouvelle recherche lancée.",
    },
    blocklist: {
        title: "Supprimer et blocklister ?",
        description:
            "Le téléchargement est retiré du client et la release est blocklistée : elle ne sera plus jamais récupérée.",
        confirm: "Supprimer + blocklist",
        destructive: true,
        loading: "Suppression en cours…",
        success: "Supprimé et blocklisté.",
    },
    remove: {
        title: "Supprimer de la file ?",
        description:
            "Le téléchargement est retiré du client et de la file. La release n'est pas blocklistée : elle pourra être récupérée à nouveau.",
        confirm: "Supprimer",
        destructive: true,
        loading: "Suppression en cours…",
        success: "Supprimé de la file.",
    },
};

export function QueueTab({ data, isLoading, isError, error, refetch, throughput, posters, onShowImports }: QueueTabProps) {
    const removeItem = useRemoveQueueItem();
    const retryItem = useRetryQueueItem();
    const pendingKeys = usePendingQueueKeys();

    const [clientFilter, setClientFilter] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [confirm, setConfirm] = useState<{ kind: QueueActionKind; item: DownloadItem } | null>(null);

    const items = useMemo(() => data?.items ?? [], [data]);

    // Répartition par client (pour les chips et la barre empilée).
    const clients = useMemo(() => {
        const counts = new Map<string, number>();
        for (const it of items) {
            const key = it.download_client || "?";
            counts.set(key, (counts.get(key) ?? 0) + 1);
        }
        return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    }, [items]);

    // Si le client filtré disparaît de la file, on retombe sur « Tous ».
    const activeClient = clientFilter && clients.some(([c]) => c === clientFilter) ? clientFilter : null;

    const byClient = useMemo(
        () => items.filter((it) => !activeClient || (it.download_client || "?") === activeClient),
        [items, activeClient],
    );

    const bucketCounts = useMemo(() => {
        const counts: Record<QueueBucket, number> = { downloading: 0, waiting: 0, importing: 0, problem: 0 };
        for (const it of byClient) counts[bucketOf(it)] += 1;
        return counts;
    }, [byClient]);

    const visible = useMemo(
        () => (statusFilter === "all" ? byClient : byClient.filter((it) => bucketOf(it) === statusFilter)),
        [byClient, statusFilter],
    );

    // Totaux globaux (toute la file, indépendamment des filtres).
    const totals = useMemo(() => {
        let size = 0;
        let left = 0;
        for (const it of items) {
            size += it.size_bytes || 0;
            left += it.size_left_bytes || 0;
        }
        return { size, left, done: Math.max(0, size - left) };
    }, [items]);

    const runAction = (kind: QueueActionKind, item: DownloadItem) => {
        const copy = ACTION_COPY[kind];
        const type = item.service_type; // "radarr" | "sonarr"
        const promise: Promise<unknown> =
            kind === "retry"
                ? retryItem.mutateAsync({ type, id: item.id, movie_id: item.movie_id, series_id: item.series_id })
                : removeItem.mutateAsync({ type, id: item.id, removeFromClient: true, blocklist: kind === "blocklist" });
        toast.promise(promise, {
            loading: copy.loading,
            success: copy.success,
            error: (e: unknown) => `Échec : ${e instanceof Error ? e.message : "erreur inconnue"}`,
        });
    };

    if (isLoading) return <QueueSkeleton />;
    if (isError) {
        return (
            <SpotlightCard interactive={false}>
                <ErrorState error={error} onRetry={refetch} title="Impossible de charger la file" />
            </SpotlightCard>
        );
    }

    if (items.length === 0) {
        return (
            <SpotlightCard interactive={false}>
                <EmptyState
                    icon={Download}
                    title="La file est vide"
                    description="Aucun téléchargement en cours. Les nouveaux téléchargements Radarr et Sonarr apparaîtront ici en direct."
                    action={{ label: "Voir les imports", onClick: onShowImports }}
                />
            </SpotlightCard>
        );
    }

    const globalPct = percent(totals.done, totals.size);
    const filtersActive = activeClient !== null || statusFilter !== "all";

    return (
        <div className="space-y-4">
            {/* ── Barre résumé ─────────────────────────────────── */}
            <motion.div variants={fadeUp} initial="hidden" animate="show">
                <SpotlightCard interactive={false} className="relative overflow-hidden p-4 sm:p-5">
                    <div
                        aria-hidden
                        className="pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full opacity-30"
                        style={{ background: "radial-gradient(closest-side, hsl(var(--primary) / 0.6), transparent)" }}
                    />
                    <div className="relative flex flex-col gap-5 md:flex-row md:items-center">
                        <div className="flex items-center gap-4">
                            <RingGauge value={globalPct} size={84} stroke={7} tone="primary">
                                <div className="text-center leading-none">
                                    <AnimatedNumber value={Math.round(globalPct)} suffix=" %" className="text-base font-bold" />
                                </div>
                            </RingGauge>
                            <div>
                                <p className="eyebrow">Progression globale</p>
                                <p className="mt-1 text-lg font-semibold tabular-nums">
                                    {formatBytes(totals.done)}
                                    <span className="text-sm font-normal text-muted-foreground"> / {formatBytes(totals.size)}</span>
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    {totals.left > 0 ? `${formatBytes(totals.left)} restants` : "Tout est téléchargé"}
                                    {throughput.total > 0 && " · débit estimé en direct"}
                                </p>
                            </div>
                        </div>

                        <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4">
                            <MiniStat icon={ArrowDownToLine} label="En cours" value={bucketCounts.downloading} tone="text-primary" />
                            <MiniStat icon={Clock} label="En attente" value={bucketCounts.waiting} tone="text-slate-300" />
                            <MiniStat icon={PackageCheck} label="Import" value={bucketCounts.importing} tone="text-emerald-300" />
                            <MiniStat icon={AlertTriangle} label="Problèmes" value={bucketCounts.problem} tone="text-rose-300" />
                        </div>
                    </div>

                    {/* Répartition par client */}
                    {clients.length > 0 && (
                        <div className="relative mt-5">
                            <div className="flex h-2 w-full gap-0.5 overflow-hidden rounded-full bg-muted/50">
                                {clients.map(([client, count], i) => {
                                    const m = getClientMeta(client === "?" ? null : client);
                                    return (
                                        <motion.span
                                            key={client}
                                            className={cn("h-full first:rounded-l-full last:rounded-r-full", m.solid)}
                                            style={{ boxShadow: `0 0 12px ${m.glow}` }}
                                            initial={{ width: 0 }}
                                            animate={{ width: `${(count / items.length) * 100}%` }}
                                            transition={{ duration: 0.9, ease: EASE_OUT, delay: 0.2 + i * 0.08 }}
                                        />
                                    );
                                })}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                                {clients.map(([client, count]) => {
                                    const m = getClientMeta(client === "?" ? null : client);
                                    return (
                                        <span key={client} className="inline-flex items-center gap-1.5">
                                            <span className={cn("h-2 w-2 rounded-full", m.solid)} />
                                            <span className="text-foreground/85">{m.label}</span>
                                            <span className="tabular-nums">{count}</span>
                                        </span>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </SpotlightCard>
            </motion.div>

            {/* ── Filtres ───────────────────────────────────────── */}
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="-mx-1 flex items-center gap-2 overflow-x-auto px-1 pb-1 scrollbar-none" role="group" aria-label="Filtrer par client">
                    <button
                        type="button"
                        className="chip shrink-0"
                        data-active={activeClient === null}
                        aria-pressed={activeClient === null}
                        onClick={() => setClientFilter(null)}
                    >
                        <Layers className="h-3.5 w-3.5" />
                        Tous les clients
                        <span className="tabular-nums opacity-70">{items.length}</span>
                    </button>
                    {clients.map(([client, count]) => {
                        const m = getClientMeta(client === "?" ? null : client);
                        const active = activeClient === client;
                        return (
                            <button
                                key={client}
                                type="button"
                                className="chip shrink-0"
                                data-active={active}
                                aria-pressed={active}
                                onClick={() => setClientFilter(active ? null : client)}
                            >
                                <m.icon className={cn("h-3.5 w-3.5", !active && m.color)} />
                                {m.label}
                                <span className="tabular-nums opacity-70">{count}</span>
                            </button>
                        );
                    })}
                </div>
                <Segmented<StatusFilter>
                    ariaLabel="Filtrer par état"
                    value={statusFilter}
                    onChange={setStatusFilter}
                    size="sm"
                    options={[
                        { value: "all", label: "Tous", count: byClient.length },
                        { value: "downloading", label: "En cours", count: bucketCounts.downloading, icon: ArrowDownToLine },
                        { value: "waiting", label: "En attente", count: bucketCounts.waiting, icon: Clock, tone: "text-slate-300" },
                        { value: "importing", label: "Import", count: bucketCounts.importing, icon: CheckCircle2, tone: "text-emerald-300" },
                        { value: "problem", label: "Problèmes", count: bucketCounts.problem, icon: AlertTriangle, tone: "text-rose-300" },
                    ]}
                />
            </div>

            {/* ── Liste ─────────────────────────────────────────── */}
            {visible.length === 0 ? (
                <SpotlightCard interactive={false}>
                    <EmptyState
                        compact
                        icon={FilterX}
                        title="Aucun élément pour ces filtres"
                        description={`${plural(items.length, "élément")} dans la file au total.`}
                        action={
                            filtersActive
                                ? {
                                      label: "Réinitialiser les filtres",
                                      onClick: () => {
                                          setClientFilter(null);
                                          setStatusFilter("all");
                                      },
                                  }
                                : undefined
                        }
                    />
                </SpotlightCard>
            ) : (
                <ul className="space-y-2.5" aria-label="File de téléchargement">
                    <AnimatePresence initial={true} mode="popLayout">
                        {visible.map((item, i) => {
                            const key = queueItemKey(item);
                            return (
                                <DownloadCard
                                    key={key}
                                    item={item}
                                    index={i}
                                    posterUrl={posterFor(item, posters)}
                                    speed={throughput.byKey[key]}
                                    pending={pendingKeys.has(key)}
                                    onAction={(kind) => setConfirm({ kind, item })}
                                />
                            );
                        })}
                    </AnimatePresence>
                </ul>
            )}

            {/* ── Confirmation ──────────────────────────────────── */}
            <ConfirmDialog
                open={!!confirm}
                onOpenChange={(o) => !o && setConfirm(null)}
                title={confirm ? ACTION_COPY[confirm.kind].title : ""}
                description={confirm ? ACTION_COPY[confirm.kind].description : undefined}
                confirmLabel={confirm ? ACTION_COPY[confirm.kind].confirm : undefined}
                destructive={confirm ? ACTION_COPY[confirm.kind].destructive : false}
                onConfirm={() => {
                    // Exécution en arrière-plan : la boîte se ferme, la ligne
                    // affiche son indicateur et le toast suit l'opération.
                    if (confirm) runAction(confirm.kind, confirm.item);
                }}
            >
                {confirm && (
                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
                        <p className="break-words text-sm font-medium">{confirm.item.title}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                            {confirm.item.source_service} · {getClientMeta(confirm.item.download_client, confirm.item.protocol).label}
                        </p>
                    </div>
                )}
            </ConfirmDialog>
        </div>
    );
}

function MiniStat({
    icon: Icon,
    label,
    value,
    tone,
}: {
    icon: typeof Clock;
    label: string;
    value: number;
    tone: string;
}) {
    return (
        <div className="rounded-xl border border-white/[0.05] bg-background/40 px-3 py-2">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <Icon className={cn("h-3.5 w-3.5", tone)} />
                {label}
            </p>
            <AnimatedNumber value={value} className={cn("mt-0.5 block text-xl font-bold", value > 0 ? tone : "text-muted-foreground/60")} />
        </div>
    );
}

/** Squelette calqué sur la vraie mise en page (résumé + cartes). */
export function QueueSkeleton() {
    return (
        <div className="space-y-4" aria-busy aria-label="Chargement de la file">
            <div className="glass flex items-center gap-4 rounded-2xl p-5">
                <Shimmer className="h-[84px] w-[84px] rounded-full" />
                <div className="flex-1 space-y-2">
                    <Shimmer className="h-3 w-28 rounded-md" />
                    <Shimmer className="h-5 w-44 rounded-md" />
                </div>
                <div className="hidden flex-1 grid-cols-4 gap-2 md:grid">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Shimmer key={i} className="h-14 rounded-xl" />
                    ))}
                </div>
            </div>
            <Shimmer className="h-9 w-full max-w-lg rounded-xl" />
            {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="glass flex gap-4 rounded-2xl p-4">
                    <Shimmer className="h-20 w-[54px] rounded-lg" />
                    <div className="flex-1 space-y-2.5">
                        <Shimmer className="h-4 w-2/3 rounded-md" />
                        <Shimmer className="h-3 w-1/2 rounded-md" />
                        <Shimmer className="h-1.5 w-full rounded-full" />
                        <Shimmer className="h-3 w-1/3 rounded-md" />
                    </div>
                </div>
            ))}
        </div>
    );
}
