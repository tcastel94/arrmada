"use client";

/**
 * Onglet « Nettoyage » du hub Santé médiathèque.
 * ----------------------------------------------------------------
 * Quatre catégories (sélecteur synchronisé à l'URL : ?tab=cleanup&cat=…) :
 *  - Non surveillés        : présents sur disque mais plus suivis.
 *  - Basse qualité         : films SD/DVD sortis avant 2020.
 *  - Surdimensionnés       : films > 50 Go, séries > 100 Go.
 *  - Séries terminées < 50 % : séries finies dont on a moins de la moitié.
 * Nouveauté : chaque ligne propose des actions (ouvrir la fiche, ne plus
 * surveiller, supprimer avec confirmation) — l'ancienne page n'en avait
 * aucune.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    ArrowDownCircle,
    Check,
    ChevronRight,
    DiscAlbum,
    EyeOff,
    HardDrive,
    Loader2,
    Maximize2,
    Recycle,
    Trash2,
    type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
    cleanupItemKey,
    useCleanupScan,
    useDeleteMedia,
    useUnmonitorMedia,
    type CleanupCategory,
    type CleanupItem,
} from "@/hooks/use-cleanup";
import { useUrlState } from "@/hooks/use-url-state";
import { formatBytes } from "@/lib/format";
import { fadeUp, stagger, EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Segmented } from "@/components/maintenance/segmented";
import { localizeSizes } from "@/components/maintenance/size";
import { HealthTabHeader, ShownCount } from "./tab-header";
import { MediaRow } from "./media-row";
import { qualityBadgeClass, qualityLabel } from "./quality-utils";
import { usePrimaryInstance } from "./use-primary-instance";

const CATEGORIES: {
    key: CleanupCategory;
    label: string;
    icon: LucideIcon;
    iconClassName: string;
    explain: string;
    empty: string;
}[] = [
    {
        key: "unmonitored",
        label: "Non surveillés",
        icon: EyeOff,
        iconClassName: "text-amber-300",
        explain: "Médias encore sur le disque mais que Radarr/Sonarr ne suivent plus : souvent oubliés, c'est la place la plus facile à récupérer.",
        empty: "Tout ce qui est sur ton disque est encore surveillé.",
    },
    {
        key: "low_quality",
        label: "Basse qualité",
        icon: ArrowDownCircle,
        iconClassName: "text-rose-300",
        explain: "Films en SD ou DVD sortis avant 2020 : à remplacer par une meilleure version ou à supprimer.",
        empty: "Aucun vieux film en SD ou DVD.",
    },
    {
        key: "oversized",
        label: "Surdimensionnés",
        icon: Maximize2,
        iconClassName: "text-violet-300",
        explain: "Films de plus de 50 Go (souvent des Remux) et séries de plus de 100 Go : vérifie que cette qualité est vraiment utile.",
        empty: "Aucun fichier anormalement volumineux.",
    },
    {
        key: "incomplete_ended",
        label: "Séries terminées < 50 %",
        icon: DiscAlbum,
        iconClassName: "text-sky-300",
        explain: "Séries terminées dont tu as moins de la moitié des épisodes : à compléter ou à libérer.",
        empty: "Aucune série terminée à moitié vide.",
    },
];

const SORT_HINT = "les plus volumineux d'abord";

export function CleanupTab() {
    const { data, isLoading, isError, error, refetch, rescan, isFetching, dataUpdatedAt } = useCleanupScan();
    const [cat, setCat] = useUrlState<CleanupCategory>("cat", "unmonitored");
    const unmonitor = useUnmonitorMedia();
    const remove = useDeleteMedia();
    const { isActionable, primaryName } = usePrimaryInstance();

    // Action en cours par ligne (clé média → libellé), au lieu d'un
    // `isPending` global qui gelait toute la liste.
    const [pending, setPending] = useState<Record<string, "unmonitor" | "delete">>({});
    // `toDelete` est conservé après fermeture pour que le titre de la boîte
    // ne se vide pas pendant l'animation de sortie.
    const [toDelete, setToDelete] = useState<CleanupItem | null>(null);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [deleteFiles, setDeleteFiles] = useState(true);

    const current = CATEGORIES.find((c) => c.key === cat) ?? CATEGORIES[0];
    const bucket = data?.[current.key];
    const items = useMemo(() => bucket?.items ?? [], [bucket]);

    const setRowPending = (key: string, action?: "unmonitor" | "delete") =>
        setPending((p) => {
            const next = { ...p };
            if (action) next[key] = action;
            else delete next[key];
            return next;
        });

    const handleUnmonitor = (item: CleanupItem) => {
        const key = cleanupItemKey(item);
        setRowPending(key, "unmonitor");
        unmonitor.mutate(item, {
            onSuccess: () =>
                toast.success(`« ${item.title} » n'est plus surveillé`, {
                    description: "Il reste sur le disque ; Radarr/Sonarr ne chercheront plus de nouvelle version.",
                }),
            onError: (e) => toast.error(`Impossible de modifier « ${item.title} »`, { description: e.message }),
            onSettled: () => setRowPending(key),
        });
    };

    const confirmDelete = async () => {
        if (!toDelete) return;
        const item = toDelete;
        const key = cleanupItemKey(item);
        setRowPending(key, "delete");
        try {
            await remove.mutateAsync({ item, deleteFiles });
            toast.success(`« ${item.title} » supprimé`, {
                description: deleteFiles ? `${formatBytes(item.size_bytes)} libérés sur le disque.` : "Retiré de Radarr/Sonarr, fichiers conservés.",
            });
        } catch (e) {
            toast.error(`Suppression de « ${item.title} » impossible`, {
                description: e instanceof Error ? e.message : undefined,
            });
            throw e; // garde la boîte ouverte
        } finally {
            setRowPending(key);
        }
    };

    if (isLoading) return <CleanupSkeleton />;
    if (isError || !data) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Analyse de nettoyage indisponible" />
            </Panel>
        );
    }

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            <motion.div variants={fadeUp}>
                <HealthTabHeader
                    icon={Recycle}
                    title="Nettoyage"
                    description="Ce qui occupe de la place pour pas grand-chose, classé du plus gros au plus petit."
                    updatedAt={dataUpdatedAt}
                    isFetching={isFetching}
                    onRescan={() => rescan()}
                />
            </motion.div>

            <motion.div variants={fadeUp}>
                <Segmented<CleanupCategory>
                    layoutId="cleanup-cat"
                    ariaLabel="Catégorie de nettoyage"
                    value={current.key}
                    onChange={setCat}
                    options={CATEGORIES.map((c) => ({
                        value: c.key,
                        label: c.label,
                        icon: c.icon,
                        iconClassName: c.iconClassName,
                        count: data[c.key].total,
                        hint: c.explain,
                    }))}
                />
            </motion.div>

            <motion.div variants={fadeUp}>
                <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                        key={current.key}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.3, ease: EASE_OUT }}
                    >
                        <Panel
                            title={current.label}
                            icon={current.icon}
                            iconClassName={current.iconClassName}
                            bodyClassName="p-0"
                            action={
                                <div className="flex items-center gap-2">
                                    {current.key === "unmonitored" && (data.unmonitored.reclaimable_bytes ?? 0) > 0 && (
                                        <span className="hidden items-center gap-1 rounded-lg bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300 sm:inline-flex">
                                            <HardDrive className="h-3 w-3" />
                                            {formatBytes(data.unmonitored.reclaimable_bytes)} récupérables
                                        </span>
                                    )}
                                    <ShownCount shown={items.length} total={bucket?.total ?? 0} sortHint={SORT_HINT} />
                                </div>
                            }
                        >
                            <p className="border-b border-white/[0.05] px-4 py-2.5 text-xs text-muted-foreground sm:px-5">
                                {current.explain}
                            </p>
                            {items.length === 0 ? (
                                <EmptyState compact tone="success" icon={Check} title="Rien à signaler" description={current.empty} />
                            ) : (
                                <ul className="divide-y divide-white/[0.04]">
                                    <AnimatePresence mode="popLayout" initial={false}>
                                        {items.map((item) => {
                                            const key = cleanupItemKey(item);
                                            const rowPending = pending[key];
                                            const actionable = isActionable(item.service, item.type);
                                            const href = actionable ? `/media/${item.type}/${item.external_id}` : undefined;
                                            return (
                                                <MediaRow
                                                    key={key}
                                                    title={item.title}
                                                    type={item.type}
                                                    posterUrl={item.poster_url}
                                                    href={href}
                                                    busy={!!rowPending}
                                                    meta={[item.year || "·", item.type === "series" ? "Série" : "Film", item.service]}
                                                    badges={<CleanupBadges item={item} />}
                                                    description={localizeSizes(item.suggestion)}
                                                    extra={
                                                        item.reason === "incomplete_ended" && item.episodes_total ? (
                                                            <div className="flex max-w-xs items-center gap-2">
                                                                <GradientProgress
                                                                    value={item.completion_percent ?? ((item.episodes_have ?? 0) / item.episodes_total) * 100}
                                                                    tone="amber"
                                                                    glow={false}
                                                                />
                                                                <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                                                                    {item.episodes_have ?? 0}/{item.episodes_total} ép.
                                                                </span>
                                                            </div>
                                                        ) : undefined
                                                    }
                                                    size={formatBytes(item.size_bytes)}
                                                    sizeClassName="text-amber-300"
                                                    actions={
                                                        <RowActions
                                                            item={item}
                                                            href={href}
                                                            actionable={actionable}
                                                            primary={primaryName(item.type)}
                                                            pending={rowPending}
                                                            onUnmonitor={() => handleUnmonitor(item)}
                                                            onDelete={() => {
                                                                setDeleteFiles(true);
                                                                setToDelete(item);
                                                                setDeleteOpen(true);
                                                            }}
                                                        />
                                                    }
                                                />
                                            );
                                        })}
                                    </AnimatePresence>
                                </ul>
                            )}
                        </Panel>
                    </motion.div>
                </AnimatePresence>
            </motion.div>

            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                destructive
                title={`Supprimer « ${toDelete?.title ?? ""} » ?`}
                description={
                    toDelete?.type === "series"
                        ? "La série sera retirée de Sonarr, ainsi que ses téléchargements en cours."
                        : "Le film sera retiré de Radarr, ainsi que ses téléchargements en cours."
                }
                confirmLabel="Supprimer"
                onConfirm={confirmDelete}
            >
                <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl bg-white/[0.03] p-3 ring-1 ring-white/[0.06]">
                    <span className="text-sm">
                        Supprimer aussi les fichiers du disque
                        <span className="block text-xs text-muted-foreground">
                            {deleteFiles ? `Libère ${toDelete ? formatBytes(toDelete.size_bytes) : ""}. Irréversible.` : "Les fichiers resteront sur le disque."}
                        </span>
                    </span>
                    <Switch checked={deleteFiles} onCheckedChange={setDeleteFiles} aria-label="Supprimer aussi les fichiers" />
                </label>
            </ConfirmDialog>
        </motion.div>
    );
}

/* ── Sous-composants ───────────────────────────────────────── */

function CleanupBadges({ item }: { item: CleanupItem }) {
    return (
        <>
            {item.type === "movie" && item.quality && (
                <span className={cn("rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold", qualityBadgeClass(item.quality))}>
                    {qualityLabel(item.quality)}
                </span>
            )}
            {!item.monitored && (
                <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                    <EyeOff className="h-3 w-3" /> Non surveillé
                </span>
            )}
            {item.type === "series" && item.status === "ended" && (
                <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Terminée</span>
            )}
        </>
    );
}

function RowActions({
    item,
    href,
    actionable,
    primary,
    pending,
    onUnmonitor,
    onDelete,
}: {
    item: CleanupItem;
    href?: string;
    actionable: boolean;
    primary?: string;
    pending?: "unmonitor" | "delete";
    onUnmonitor: () => void;
    onDelete: () => void;
}) {
    if (!actionable) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>
                    <span tabIndex={0} className="cursor-help rounded-lg bg-white/[0.04] px-2 py-1 text-[11px] text-muted-foreground">
                        Actions indisponibles
                    </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-64 text-xs">
                    Les actions ArrMada ne visent que l&apos;instance principale{primary ? ` (« ${primary} »)` : ""}. Gère ce
                    média directement dans « {item.service} ».
                </TooltipContent>
            </Tooltip>
        );
    }
    return (
        <>
            {item.monitored && (
                <Button
                    variant="outline"
                    size="sm"
                    disabled={!!pending}
                    onClick={onUnmonitor}
                    aria-label={`Ne plus surveiller ${item.title}`}
                >
                    {pending === "unmonitor" ? <Loader2 className="animate-spin" /> : <EyeOff />}
                    <span className="hidden md:inline">Ne plus surveiller</span>
                </Button>
            )}
            <Button
                variant="ghost"
                size="icon-sm"
                disabled={!!pending}
                onClick={onDelete}
                aria-label={`Supprimer ${item.title}`}
                className="text-red-400 hover:bg-red-500/10 hover:text-red-300"
            >
                {pending === "delete" ? <Loader2 className="animate-spin" /> : <Trash2 />}
            </Button>
            {href && (
                <Button asChild variant="ghost" size="icon-sm" aria-label={`Fiche de ${item.title}`}>
                    <Link href={href}>
                        <ChevronRight />
                    </Link>
                </Button>
            )}
        </>
    );
}

function CleanupSkeleton() {
    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3">
                <Shimmer className="h-9 w-9 rounded-xl" />
                <div className="space-y-2">
                    <Shimmer className="h-4 w-32 rounded-md" />
                    <Shimmer className="h-3 w-72 rounded-md" />
                </div>
            </div>
            <Shimmer className="h-10 w-full max-w-xl rounded-2xl" />
            <div className="glass space-y-2 rounded-2xl p-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Shimmer key={i} className="h-[72px] w-full" />
                ))}
            </div>
        </div>
    );
}
