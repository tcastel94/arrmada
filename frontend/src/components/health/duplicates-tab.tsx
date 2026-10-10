"use client";

/**
 * Onglet « Doublons » du hub Santé médiathèque.
 * ----------------------------------------------------------------
 * Deux familles (sélecteur « Entre services » / « Même service ») :
 *  - Entre services : le même titre existe dans plusieurs instances
 *    (ex: Radarr + Radarr 4K). Pour chaque groupe on désigne la copie à
 *    GARDER (meilleure qualité parmi celles qui ont un fichier) ; les
 *    copies sans fichier sont signalées.
 *  - Même service : le même titre apparaît plusieurs fois dans une seule
 *    instance avec des qualités différentes (l'ancienne page l'appelait à
 *    tort « Upgrades »).
 */
import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Copy, Crown, FileX2, Film, HardDrive, Layers3, Server, Tv } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { useDuplicates, type DuplicateGroup, type SameServiceVariant } from "@/hooks/use-duplicates";
import { useUrlState } from "@/hooks/use-url-state";
import { formatBytes, plural } from "@/lib/format";
import { frSize } from "@/components/maintenance/size";
import { fadeUp, stagger, EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Segmented } from "@/components/maintenance/segmented";
import { HealthTabHeader, ShownCount } from "./tab-header";
import { qualityBadgeClass, qualityLabel, qualityRank } from "./quality-utils";

type DupView = "cross" | "same";

/** Clé stable d'un groupe (pas d'ID côté backend → titre + année + services). */
function groupKey(g: { title: string; year: number | null; type: string }, extra = ""): string {
    return `${g.type}:${g.title}:${g.year ?? ""}:${extra}`;
}

/**
 * Index de la copie à garder : la meilleure qualité parmi les copies
 * qui ont réellement un fichier. `null` si on ne peut pas départager
 * (qualités identiques ou inconnues, ex: séries dont le backend ne
 * renvoie que l'ID de profil).
 */
function bestCopyIndex(group: DuplicateGroup): number | null {
    const candidates = group.items
        .map((item, idx) => ({ idx, rank: qualityRank(item.quality), hasFile: item.has_file }))
        .filter((c) => c.hasFile);
    if (candidates.length === 0) return null;
    // Une seule copie a un fichier : c'est forcément elle qu'on garde.
    if (candidates.length === 1) return candidates[0].idx;
    const best = Math.max(...candidates.map((c) => c.rank));
    const top = candidates.filter((c) => c.rank === best);
    // Égalité parfaite entre plusieurs copies : on ne conseille rien.
    return top.length === 1 ? top[0].idx : null;
}

export function DuplicatesTab() {
    const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useDuplicates();
    const [view, setView] = useUrlState<DupView>("dup", "cross");

    const sameService = useMemo(() => data?.upgrade_opportunities ?? [], [data]);

    if (isLoading) return <DuplicatesSkeleton />;
    if (isError || !data) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Détection des doublons indisponible" />
            </Panel>
        );
    }

    const { stats } = data;

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            <motion.div variants={fadeUp}>
                <HealthTabHeader
                    icon={Copy}
                    title="Doublons"
                    description="Titres présents plusieurs fois dans ta médiathèque, avec la copie conseillée à garder."
                    updatedAt={dataUpdatedAt}
                    isFetching={isFetching}
                    onRescan={() => refetch()}
                />
            </motion.div>

            <motion.div variants={fadeUp} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Segmented<DupView>
                    layoutId="dup-view"
                    ariaLabel="Type de doublons"
                    value={view}
                    onChange={setView}
                    options={[
                        {
                            value: "cross",
                            label: "Entre services",
                            icon: Server,
                            iconClassName: "text-fuchsia-300",
                            count: stats.total_duplicates,
                            hint: "Le même titre existe dans plusieurs instances (ex: Radarr et Radarr 4K).",
                        },
                        {
                            value: "same",
                            label: "Même service",
                            icon: Layers3,
                            iconClassName: "text-sky-300",
                            count: stats.total_upgrades,
                            hint: "Le même titre apparaît plusieurs fois dans une seule instance.",
                        },
                    ]}
                />
                {view === "cross" && stats.wasted_space_bytes > 0 && (
                    <span className="inline-flex items-center gap-1.5 self-start rounded-lg border border-amber-400/25 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300 sm:self-auto">
                        <HardDrive className="h-3.5 w-3.5" />
                        {formatBytes(stats.wasted_space_bytes)} occupés par des copies en trop
                    </span>
                )}
            </motion.div>

            <motion.div variants={fadeUp}>
                <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                        key={view}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.3, ease: EASE_OUT }}
                    >
                        {view === "cross" ? (
                            <CrossServiceList groups={data.duplicates} />
                        ) : (
                            <SameServiceList items={sameService} total={stats.total_upgrades} />
                        )}
                    </motion.div>
                </AnimatePresence>
            </motion.div>
        </motion.div>
    );
}

/* ── Entre services ────────────────────────────────────────── */

function CrossServiceList({ groups }: { groups: DuplicateGroup[] }) {
    if (groups.length === 0) {
        return (
            <Panel>
                <EmptyState
                    tone="success"
                    icon={Copy}
                    title="Aucun doublon entre tes services"
                    description="Chaque titre n'existe que dans une seule instance Radarr/Sonarr."
                />
            </Panel>
        );
    }
    return (
        <div className="space-y-3">
            <div className="flex justify-end">
                <ShownCount shown={groups.length} total={groups.length} />
            </div>
            <motion.ul variants={stagger(0, 0.04)} initial="hidden" animate="show" className="grid gap-3 xl:grid-cols-2">
                {groups.map((g, i) => (
                    <DuplicateCard key={groupKey(g, g.services.join("+"))} group={g} animate={i < 20} />
                ))}
            </motion.ul>
        </div>
    );
}

function DuplicateCard({ group, animate }: { group: DuplicateGroup; animate: boolean }) {
    const keep = bestCopyIndex(group);
    const TypeIcon = group.type === "series" ? Tv : Film;
    return (
        <motion.li variants={animate ? fadeUp : undefined} className="glass glass-hover spotlight rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                    <span
                        className={cn(
                            "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1",
                            group.type === "series"
                                ? "bg-sky-500/15 text-sky-300 ring-sky-400/25"
                                : "bg-violet-500/15 text-violet-300 ring-violet-400/25",
                        )}
                    >
                        <TypeIcon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold tracking-tight">{group.title}</h3>
                        <p className="text-xs text-muted-foreground">
                            {[group.year ?? "·", group.type === "series" ? "Série" : "Film", plural(group.copies, "copie")].join(" · ")}
                        </p>
                    </div>
                </div>
                <div className="shrink-0 text-right">
                    <p className="text-sm font-bold tabular-nums">{formatBytes(group.total_size_bytes)}</p>
                    <p className="text-[10px] text-muted-foreground">au total</p>
                </div>
            </div>

            <ul className="mt-3 space-y-1.5">
                {group.items.map((item, idx) => {
                    const isKeep = keep === idx;
                    return (
                        <li
                            // Pas d'ID de copie côté backend : source + qualité + position.
                            key={`${item.source}:${item.quality}:${idx}`}
                            className={cn(
                                "flex items-center gap-2 rounded-xl px-3 py-2 text-xs ring-1 transition-colors",
                                isKeep
                                    ? "bg-emerald-500/10 ring-emerald-400/25"
                                    : item.has_file
                                      ? "bg-white/[0.025] ring-white/[0.05]"
                                      : "bg-white/[0.015] ring-white/[0.05] opacity-75",
                            )}
                        >
                            <span className="min-w-0 flex-1 truncate font-medium">{item.source}</span>
                            <span className={cn("rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold", qualityBadgeClass(item.quality))}>
                                {qualityLabel(item.quality)}
                            </span>
                            <span className="w-16 text-right tabular-nums text-muted-foreground">
                                {item.has_file ? frSize(item.size_human) : "—"}
                            </span>
                            {isKeep ? (
                                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
                                    <Crown className="h-3 w-3" /> À garder
                                </span>
                            ) : !item.has_file ? (
                                <span className="inline-flex items-center gap-1 rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                                    <FileX2 className="h-3 w-3" /> Sans fichier
                                </span>
                            ) : (
                                <span className="rounded-md bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                                    En trop
                                </span>
                            )}
                        </li>
                    );
                })}
            </ul>
            {keep === null && group.items.some((i) => i.has_file) && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                    Qualités équivalentes : compare les fichiers dans chaque service avant de supprimer.
                </p>
            )}
        </motion.li>
    );
}

/* ── Même service ──────────────────────────────────────────── */

function SameServiceList({ items, total }: { items: SameServiceVariant[]; total: number }) {
    if (total === 0 || items.length === 0) {
        return (
            <Panel>
                <EmptyState
                    tone="success"
                    icon={Layers3}
                    title="Aucune entrée en double dans un même service"
                    description="Aucun titre n'apparaît deux fois dans une même instance Radarr/Sonarr."
                />
            </Panel>
        );
    }
    return (
        <Panel
            title="Titres présents plusieurs fois dans un même service"
            icon={Layers3}
            iconClassName="text-sky-300"
            bodyClassName="p-0"
            action={<ShownCount shown={items.length} total={total} />}
        >
            <ul className="divide-y divide-white/[0.04]">
                {items.map((v, i) => (
                    <motion.li
                        key={groupKey(v, `${v.service}:${v.qualities.join("|")}`)}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: Math.min(i, 20) * 0.03, duration: 0.35, ease: EASE_OUT }}
                        className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5"
                    >
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold">{v.title}</p>
                            <p className="text-xs text-muted-foreground">
                                {[v.year ?? "·", v.type === "series" ? "Série" : "Film", v.service].join(" · ")}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {v.qualities.map((q, j) => (
                                <span
                                    key={`${q}:${j}`}
                                    className={cn("rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold", qualityBadgeClass(q))}
                                >
                                    {qualityLabel(q)}
                                </span>
                            ))}
                        </div>
                    </motion.li>
                ))}
            </ul>
        </Panel>
    );
}

function DuplicatesSkeleton() {
    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3">
                <Shimmer className="h-9 w-9 rounded-xl" />
                <div className="space-y-2">
                    <Shimmer className="h-4 w-32 rounded-md" />
                    <Shimmer className="h-3 w-72 rounded-md" />
                </div>
            </div>
            <Shimmer className="h-10 w-72 rounded-2xl" />
            <div className="grid gap-3 xl:grid-cols-2">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Shimmer key={i} className="h-40 rounded-2xl" />
                ))}
            </div>
        </div>
    );
}
