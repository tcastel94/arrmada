"use client";

/**
 * Onglet « Suivi » de /search : les titres ajoutés et leur avancement
 * (En attente → Recherche → Téléchargement → Disponible, ou Échec).
 * ----------------------------------------------------------------
 * Le backend resynchronise les statuts avec Radarr/Sonarr à chaque lecture ;
 * la liste se rafraîchit seule toutes les 15 s. Nouveautés : filtres par
 * statut, lien vers la fiche, relance d'une demande en échec, suppression
 * confirmée (avant : un clic sur la corbeille supprimait sans prévenir).
 */
import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, ListChecks, Loader2, PenLine, RotateCcw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useCreateRequest, useDeleteRequest, useRequests, type MediaRequestItem } from "@/hooks/use-requests";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { timeAgo, formatLongDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EASE_OUT, SPRING } from "@/lib/motion";
import { MediaThumb } from "./media-thumb";
import { REQUEST_STATUS, REQUEST_STATUS_ORDER, requestStatusMeta } from "./request-status";

type Filter = "all" | (typeof REQUEST_STATUS_ORDER)[number];

export function TrackingTab({ onOpenManual, onGoSearch }: { onOpenManual: () => void; onGoSearch: () => void }) {
    const { data, isLoading, isError, error, refetch, isFetching } = useRequests();
    const { mutateAsync: deleteRequest } = useDeleteRequest();
    const { mutateAsync: createRequest } = useCreateRequest();
    const [filter, setFilter] = useState<Filter>("all");
    const [toDelete, setToDelete] = useState<MediaRequestItem | null>(null);
    const [retrying, setRetrying] = useState<number | null>(null);

    const items = useMemo(() => data?.items ?? [], [data]);
    const counts = useMemo(() => {
        const c: Record<string, number> = {};
        for (const r of items) c[r.status] = (c[r.status] ?? 0) + 1;
        return c;
    }, [items]);
    const visible = filter === "all" ? items : items.filter((r) => r.status === filter);

    /**
     * Relance d'une demande en échec : on recrée la demande (mêmes infos),
     * puis on retire l'ancienne. Pour une série, la colonne `tmdb_id` contient
     * l'ID TVDB (convention backend) → on la renvoie comme `tvdb_id`.
     */
    const retry = async (req: MediaRequestItem) => {
        setRetrying(req.id);
        try {
            const res = await createRequest({
                title: req.title,
                type: req.type,
                tmdb_id: req.type === "series" ? null : req.tmdb_id,
                tvdb_id: req.type === "series" ? req.tmdb_id : null,
                year: req.year,
                poster_url: req.poster_url,
            });
            await deleteRequest(req.id).catch(() => undefined);
            if (res.status === "failed") {
                toast.error(`« ${req.title} » est toujours en échec`, {
                    description: "Le service ne trouve pas ce titre. Essaie l'ajout manuel avec l'ID exact.",
                });
            } else {
                toast.success(`« ${req.title} » relancé`, { description: "Recherche en cours sur tes indexers." });
            }
        } catch (e) {
            toast.error("Relance impossible", { description: e instanceof Error ? e.message : undefined });
        } finally {
            setRetrying(null);
        }
    };

    const confirmDelete = async () => {
        if (!toDelete) return;
        try {
            await deleteRequest(toDelete.id);
            toast.success(`« ${toDelete.title} » retiré du suivi`);
        } catch (e) {
            toast.error("Suppression impossible", { description: e instanceof Error ? e.message : undefined });
            throw e; // garde la boîte ouverte
        }
    };

    if (isLoading) {
        return (
            <div className="glass rounded-2xl p-3">
                <TableSkeleton rows={6} />
            </div>
        );
    }
    if (isError) {
        return (
            <div className="glass rounded-2xl">
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger le suivi" />
            </div>
        );
    }
    if (items.length === 0) {
        return (
            <div className="glass rounded-2xl">
                <EmptyState
                    icon={ListChecks}
                    title="Rien à suivre pour l'instant"
                    description="Chaque titre que tu ajoutes apparaît ici, avec son statut en direct jusqu'à ce qu'il soit disponible."
                    action={{ label: "Chercher un titre", onClick: onGoSearch }}
                />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* ── Filtres par statut ── */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="-mx-1 flex max-w-full items-center gap-1.5 overflow-x-auto px-1 py-0.5 scrollbar-none" role="radiogroup" aria-label="Filtrer par statut">
                    <FilterChip active={filter === "all"} onClick={() => setFilter("all")} label="Toutes" count={items.length} />
                    {REQUEST_STATUS_ORDER.filter((s) => counts[s]).map((s) => (
                        <FilterChip
                            key={s}
                            active={filter === s}
                            onClick={() => setFilter(s)}
                            label={REQUEST_STATUS[s].label}
                            count={counts[s]}
                            dot={<StatusDot tone={REQUEST_STATUS[s].tone} pulse={REQUEST_STATUS[s].pulse} size="sm" />}
                        />
                    ))}
                </div>
                <div className="flex items-center gap-2">
                    <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex" title="Statuts resynchronisés avec Radarr / Sonarr">
                        <StatusDot tone={isFetching ? "primary" : "success"} pulse={isFetching} size="sm" />
                        {isFetching ? "Synchronisation…" : "À jour · toutes les 15 s"}
                    </span>
                    <Button variant="outline" size="sm" onClick={onOpenManual}>
                        <PenLine /> Ajout manuel
                    </Button>
                </div>
            </div>

            {/* ── Liste ── */}
            <div className="glass rounded-2xl p-1.5 sm:p-2">
                {visible.length === 0 ? (
                    <EmptyState compact icon={Search} title="Aucune demande avec ce statut" action={{ label: "Tout afficher", onClick: () => setFilter("all") }} />
                ) : (
                    <div className="space-y-0.5">
                        <AnimatePresence initial={false}>
                            {visible.map((req, i) => {
                                const service = req.target_service === "sonarr" ? "Sonarr" : req.target_service === "radarr" ? "Radarr" : req.target_service;
                                const canOpen = !!req.arr_id && req.status !== "failed";
                                return (
                                    <motion.div
                                        key={req.id}
                                        layout
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE_OUT, delay: Math.min(i, 12) * 0.03 } }}
                                        exit={{ opacity: 0, x: 60, transition: { duration: 0.25 } }}
                                        className="group flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-white/[0.04]"
                                    >
                                        <MediaThumb src={req.poster_url} alt="" type={req.type} className="h-16 w-11" />
                                        <div className="min-w-0 flex-1">
                                            {canOpen ? (
                                                <Link
                                                    href={`/media/${req.type === "series" ? "series" : "movie"}/${req.arr_id}`}
                                                    className="block truncate text-sm font-semibold transition-colors hover:text-primary"
                                                >
                                                    {req.title}
                                                    {req.year && <span className="ml-1.5 font-normal text-muted-foreground">{req.year}</span>}
                                                </Link>
                                            ) : (
                                                <p className="truncate text-sm font-semibold">
                                                    {req.title}
                                                    {req.year && <span className="ml-1.5 font-normal text-muted-foreground">{req.year}</span>}
                                                </p>
                                            )}
                                            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                                                <span>{req.type === "series" ? "Série" : "Film"}</span>
                                                <span aria-hidden className="opacity-40">
                                                    ·
                                                </span>
                                                <span>→ {service}</span>
                                                {req.requested_at && (
                                                    <>
                                                        <span aria-hidden className="opacity-40">
                                                            ·
                                                        </span>
                                                        <span title={formatLongDateTime(req.requested_at)}>
                                                            {/* timeAgo renvoie « À l'instant » (majuscule) : on l'insère en milieu de phrase. */}
                                                            demandé {timeAgo(req.requested_at).replace(/^À/, "à")}
                                                        </span>
                                                    </>
                                                )}
                                            </p>
                                            {/* Statut sous le titre sur mobile */}
                                            <StatusBadge className="mt-1.5 sm:hidden" status={req.status} />
                                        </div>

                                        <StatusBadge className="hidden sm:inline-flex" status={req.status} />

                                        <div className="flex shrink-0 items-center gap-0.5">
                                            {req.status === "failed" && (
                                                <Button
                                                    variant="ghost"
                                                    size="icon-sm"
                                                    onClick={() => retry(req)}
                                                    disabled={retrying === req.id}
                                                    aria-label={`Relancer « ${req.title} »`}
                                                    title="Relancer"
                                                >
                                                    {retrying === req.id ? <Loader2 className="animate-spin" /> : <RotateCcw />}
                                                </Button>
                                            )}
                                            {canOpen && (
                                                <Button variant="ghost" size="icon-sm" asChild title="Ouvrir la fiche">
                                                    <Link href={`/media/${req.type === "series" ? "series" : "movie"}/${req.arr_id}`} aria-label={`Ouvrir la fiche de « ${req.title} »`}>
                                                        <ArrowUpRight />
                                                    </Link>
                                                </Button>
                                            )}
                                            <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                onClick={() => setToDelete(req)}
                                                aria-label={`Retirer « ${req.title} » du suivi`}
                                                title="Retirer du suivi"
                                                className="text-muted-foreground hover:text-destructive"
                                            >
                                                <Trash2 />
                                            </Button>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>

            <ConfirmDialog
                open={!!toDelete}
                onOpenChange={(o) => !o && setToDelete(null)}
                destructive
                title={`Retirer « ${toDelete?.title ?? ""} » du suivi ?`}
                description={`Le média reste dans ${toDelete?.target_service === "sonarr" ? "Sonarr" : "Radarr"} : seul ce suivi est supprimé.`}
                confirmLabel="Retirer"
                onConfirm={confirmDelete}
            />
        </div>
    );
}

/** Badge de statut avec pastille pulsée pour les états en cours. */
function StatusBadge({ status, className }: { status: string; className?: string }) {
    const meta = requestStatusMeta(status);
    return (
        <span className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1", meta.badge, className)}>
            <StatusDot tone={meta.tone} pulse={meta.pulse} size="sm" />
            {meta.label}
        </span>
    );
}

/** Chip de filtre avec surbrillance animée (layoutId). */
function FilterChip({
    active,
    onClick,
    label,
    count,
    dot,
}: {
    active: boolean;
    onClick: () => void;
    label: string;
    count: number;
    dot?: ReactNode;
}) {
    return (
        <button
            type="button"
            role="radio"
            aria-checked={active}
            onClick={onClick}
            className={cn(
                "relative inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
        >
            {active && (
                <motion.span
                    layoutId="tracking-filter-pill"
                    transition={SPRING}
                    aria-hidden
                    className="absolute inset-0 rounded-full bg-primary/15"
                />
            )}
            {!active && <span aria-hidden className="absolute inset-0 rounded-full border border-white/[0.06] bg-muted/40" />}
            <span className="relative z-[1] inline-flex items-center gap-1.5">
                {dot}
                {label}
                <span className="tabular-nums opacity-70">{count}</span>
            </span>
        </button>
    );
}
