"use client";

/**
 * Onglet « Qualité » du hub Santé médiathèque.
 * ----------------------------------------------------------------
 * - Répartition des films par résolution (2160p → SD, ordre fixe — avant
 *   les cartes étaient triées par nombre, l'ordre changeait d'un jour à
 *   l'autre), barre empilée + tuiles.
 * - Détail par qualité *arr, trié de la meilleure à la moins bonne.
 * - Séries : le backend ne note pas la qualité épisode par épisode, on
 *   affiche ce qu'il fournit réellement (séries + épisodes analysés).
 * - Films à améliorer : bouton « Rechercher un upgrade » par ligne (lance
 *   la recherche automatique Radarr) + lien vers la fiche.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    ArrowUpCircle,
    Check,
    ChevronRight,
    Film,
    Gauge,
    Layers,
    Loader2,
    Search,
    Sparkles,
    Tv,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useQualityOverview, type UpgradeableItem } from "@/hooks/use-quality";
import { useTriggerMediaSearch } from "@/hooks/use-media-actions";
import { useDebounce } from "@/hooks/use-debounce";
import { formatBytes, formatNumber, plural } from "@/lib/format";
import { frSize } from "@/components/maintenance/size";
import { stagger, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { HealthTabHeader, ShownCount } from "./tab-header";
import { MediaRow } from "./media-row";
import { usePrimaryInstance } from "./use-primary-instance";
import {
    RESOLUTION_META,
    RESOLUTION_ORDER,
    qualityBadgeClass,
    qualityLabel,
    qualityRank,
    resolutionOf,
    type Resolution,
} from "./quality-utils";

/** Clé stable d'un film améliorable (pas d'index de tableau). */
function upgradeKey(item: UpgradeableItem): string {
    return `${item.service}:${item.external_id ?? item.title}:${item.year ?? ""}`;
}

export function QualityTab() {
    const { data, isLoading, isError, error, refetch, rescan, isFetching, dataUpdatedAt } = useQualityOverview();
    const triggerSearch = useTriggerMediaSearch();
    const { isActionable, primaryName } = usePrimaryInstance();
    const [query, setQuery] = useState("");
    const debounced = useDebounce(query, 250);
    // États par ligne : recherche en cours / lancée (l'ancien `isPending`
    // global bloquait tous les boutons dès qu'un seul était cliqué).
    const [searching, setSearching] = useState<Set<string>>(new Set());
    const [launched, setLaunched] = useState<Set<string>>(new Set());

    const movies = data?.movies;
    const totalMovies = movies?.total ?? 0;

    // Résolutions dans un ordre FIXE (2160p → Autre), en ignorant les vides.
    const resolutions = useMemo(() => {
        const dist = movies?.resolution_distribution ?? {};
        return RESOLUTION_ORDER.map((res) => ({
            res,
            count: dist[res]?.count ?? 0,
            percent: dist[res]?.percent ?? 0,
        }));
    }, [movies]);

    // Détail par qualité trié de la meilleure à la moins bonne.
    const qualities = useMemo(() => {
        const dist = movies?.quality_distribution ?? {};
        return Object.entries(dist)
            .map(([name, info]) => ({ name, ...info, rank: qualityRank(name), res: resolutionOf(name) }))
            .sort((a, b) => b.rank - a.rank || b.count - a.count);
    }, [movies]);

    const upgradeItems = useMemo(() => {
        const items = data?.upgradeable.items ?? [];
        const q = debounced.trim().toLowerCase();
        return q ? items.filter((i) => i.title.toLowerCase().includes(q)) : items;
    }, [data, debounced]);

    const launchSearch = (item: UpgradeableItem) => {
        if (item.external_id === undefined || item.external_id === null) return;
        const key = upgradeKey(item);
        setSearching((s) => new Set(s).add(key));
        triggerSearch.mutate(
            { type: item.type === "series" ? "series" : "movie", id: item.external_id },
            {
                onSuccess: () => {
                    setLaunched((s) => new Set(s).add(key));
                    toast.success(`Recherche lancée pour « ${item.title} »`, {
                        description: "Radarr cherche une meilleure version sur tes indexers.",
                    });
                },
                onError: (e) => toast.error(`Recherche impossible pour « ${item.title} »`, { description: e.message }),
                onSettled: () =>
                    setSearching((s) => {
                        const next = new Set(s);
                        next.delete(key);
                        return next;
                    }),
            },
        );
    };

    if (isLoading) return <QualitySkeleton />;
    if (isError || !data) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Analyse qualité indisponible" />
            </Panel>
        );
    }

    const upgradeable = data.upgradeable;

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            <motion.div variants={fadeUp}>
                <HealthTabHeader
                    icon={Gauge}
                    title="Qualité des fichiers"
                    description="Résolution de tes films et ceux qui mériteraient une meilleure version."
                    updatedAt={dataUpdatedAt}
                    isFetching={isFetching}
                    onRescan={() => rescan()}
                />
            </motion.div>

            {totalMovies === 0 ? (
                <motion.div variants={fadeUp}>
                    <Panel>
                        <EmptyState
                            icon={Film}
                            title="Aucun film analysé"
                            description="Aucun fichier film trouvé dans Radarr. Vérifie que le service est activé dans les paramètres."
                            action={{ label: "Ouvrir les services", href: "/settings/services" }}
                        />
                    </Panel>
                </motion.div>
            ) : (
                <>
                    {/* Résolutions + séries */}
                    <div className="grid gap-5 lg:grid-cols-3">
                        <motion.div variants={fadeUp} className="lg:col-span-2">
                            <Panel
                                title="Résolution des films"
                                icon={Layers}
                                iconClassName="text-fuchsia-300"
                                action={
                                    <span className="text-xs text-muted-foreground tabular-nums">
                                        {plural(totalMovies, "film")}
                                    </span>
                                }
                            >
                                <ResolutionStack items={resolutions} />
                                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                    {resolutions
                                        .filter((r) => r.res !== "Other" || r.count > 0)
                                        .map((r) => (
                                            <ResolutionTile key={r.res} res={r.res} count={r.count} percent={r.percent} />
                                        ))}
                                </div>
                            </Panel>
                        </motion.div>

                        <motion.div variants={fadeUp}>
                            <Panel title="Séries" icon={Tv} iconClassName="text-sky-300" className="h-full">
                                <div className="flex items-end gap-6">
                                    <div>
                                        <p className="text-3xl font-bold tracking-tight">
                                            <AnimatedNumber value={data.series.total} />
                                        </p>
                                        <p className="text-xs text-muted-foreground">séries avec fichiers</p>
                                    </div>
                                    <div>
                                        <p className="text-3xl font-bold tracking-tight">
                                            <AnimatedNumber value={data.series.total_episodes} />
                                        </p>
                                        <p className="text-xs text-muted-foreground">épisodes sur disque</p>
                                    </div>
                                </div>
                                <p className="mt-4 rounded-xl bg-white/[0.03] p-3 text-xs text-muted-foreground ring-1 ring-white/[0.05]">
                                    Sonarr ne donne pas la qualité de chaque épisode dans cette analyse : la répartition
                                    ci-contre ne concerne que les films. Pour une série précise, ouvre sa fiche.
                                </p>
                            </Panel>
                        </motion.div>
                    </div>

                    {/* Détail par qualité */}
                    <motion.div variants={fadeUp}>
                        <Panel title="Détail par qualité" icon={Sparkles} iconClassName="text-violet-300">
                            <ul className="grid gap-x-8 gap-y-3 md:grid-cols-2">
                                {qualities.map((q) => (
                                    <li key={q.name} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3">
                                        <span className="flex min-w-0 items-center gap-2 text-xs">
                                            <span className={cn("h-2 w-2 shrink-0 rounded-full", RESOLUTION_META[q.res].dot)} />
                                            <span className="truncate font-mono text-muted-foreground" title={q.name}>
                                                {qualityLabel(q.name)}
                                            </span>
                                        </span>
                                        <GradientProgress value={q.percent} tone={RESOLUTION_META[q.res].tone} glow={false} />
                                        <span className="w-24 text-right text-xs tabular-nums text-muted-foreground">
                                            {formatNumber(q.count)}{" "}
                                            <span className="text-muted-foreground/60">({q.percent.toLocaleString("fr-FR")} %)</span>
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </Panel>
                    </motion.div>
                </>
            )}

            {/* Films à améliorer */}
            <motion.div variants={fadeUp}>
                <Panel
                    title="Films à améliorer"
                    icon={ArrowUpCircle}
                    iconClassName="text-amber-300"
                    bodyClassName="p-0"
                    action={<ShownCount shown={upgradeable.items.length} total={upgradeable.count} sortHint="les moins bons d'abord" />}
                >
                    {upgradeable.count === 0 ? (
                        <EmptyState
                            compact
                            tone="success"
                            icon={Check}
                            title="Rien à améliorer"
                            description="Tous tes films surveillés sont en 1080p Bluray ou mieux."
                        />
                    ) : (
                        <>
                            <div className="flex flex-col gap-3 border-b border-white/[0.05] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
                                    <span>
                                        Taille actuelle :{" "}
                                        <span className="font-semibold text-foreground">{frSize(upgradeable.total_current_size)}</span>
                                    </span>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-4">
                                                Espace en plus (estimation) :{" "}
                                                <span className="font-semibold text-foreground">≈ +{frSize(upgradeable.estimated_space_needed)}</span>
                                            </span>
                                        </TooltipTrigger>
                                        <TooltipContent className="max-w-64 text-xs">
                                            Calcul grossier : environ 10 Go par film en 1080p Bluray, moins la taille actuelle.
                                            La place réelle dépend des releases trouvées.
                                        </TooltipContent>
                                    </Tooltip>
                                </div>
                                <div className="relative w-full sm:w-64">
                                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                                    <Input
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        placeholder="Filtrer par titre…"
                                        aria-label="Filtrer les films à améliorer"
                                        className="h-8 pl-8 text-xs"
                                    />
                                </div>
                            </div>
                            {upgradeItems.length === 0 ? (
                                <EmptyState compact icon={Search} title="Aucun titre ne correspond" description={`Rien pour « ${debounced} ».`} />
                            ) : (
                                <ul className="divide-y divide-white/[0.04]">
                                    <AnimatePresence initial={false}>
                                        {upgradeItems.map((item) => {
                                            const key = upgradeKey(item);
                                            const isSearching = searching.has(key);
                                            const isLaunched = launched.has(key);
                                            const mediaType = item.type === "series" ? "series" : "movie";
                                            // Lien + recherche seulement si l'ID désigne bien ce média
                                            // (cf. garde-fou « instance principale »).
                                            const actionable = isActionable(item.service, mediaType);
                                            const href =
                                                actionable && item.external_id !== undefined && item.external_id !== null
                                                    ? `/media/${mediaType}/${item.external_id}`
                                                    : undefined;
                                            return (
                                                <MediaRow
                                                    key={key}
                                                    title={item.title}
                                                    type={mediaType}
                                                    href={href}
                                                    meta={[item.year, item.profile && `Profil ${item.profile}`, item.service]}
                                                    badges={
                                                        <span
                                                            className={cn(
                                                                "rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                                                                qualityBadgeClass(item.quality),
                                                            )}
                                                        >
                                                            {qualityLabel(item.quality)}
                                                        </span>
                                                    }
                                                    size={formatBytes(item.size_bytes)}
                                                    sizeClassName="text-muted-foreground"
                                                    actions={
                                                        <>
                                                            <Button
                                                                variant={isLaunched ? "outline" : "glow"}
                                                                size="sm"
                                                                disabled={!href || isSearching}
                                                                onClick={() => launchSearch(item)}
                                                                aria-label={`Rechercher un upgrade pour ${item.title}`}
                                                                title={
                                                                    actionable
                                                                        ? undefined
                                                                        : `Recherche possible uniquement sur « ${primaryName(mediaType) ?? "l'instance principale"} »`
                                                                }
                                                            >
                                                                {isSearching ? (
                                                                    <Loader2 className="animate-spin" />
                                                                ) : isLaunched ? (
                                                                    <Check className="text-emerald-400" />
                                                                ) : (
                                                                    <Search />
                                                                )}
                                                                <span className="hidden sm:inline">
                                                                    {isLaunched ? "Relancer" : "Rechercher un upgrade"}
                                                                </span>
                                                                <span className="sm:hidden">{isLaunched ? "Relancer" : "Upgrade"}</span>
                                                            </Button>
                                                            {href && (
                                                                <Button asChild variant="ghost" size="icon-sm" aria-label={`Fiche de ${item.title}`}>
                                                                    <Link href={href}>
                                                                        <ChevronRight />
                                                                    </Link>
                                                                </Button>
                                                            )}
                                                        </>
                                                    }
                                                />
                                            );
                                        })}
                                    </AnimatePresence>
                                </ul>
                            )}
                        </>
                    )}
                </Panel>
            </motion.div>
        </motion.div>
    );
}

/* ── Sous-composants ───────────────────────────────────────── */

/** Barre empilée : chaque résolution occupe sa part (2 px d'écart entre segments). */
function ResolutionStack({ items }: { items: { res: Resolution; count: number; percent: number }[] }) {
    const visible = items.filter((i) => i.count > 0);
    return (
        <div>
            <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full bg-muted/40" role="img" aria-label="Répartition des films par résolution">
                {visible.map((i, idx) => (
                    <Tooltip key={i.res}>
                        <TooltipTrigger asChild>
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${i.percent}%` }}
                                transition={{ duration: 1, delay: 0.15 + idx * 0.08, ease: [0.22, 1, 0.36, 1] }}
                                className={cn("h-full min-w-[3px] first:rounded-l-full last:rounded-r-full", RESOLUTION_META[i.res].dot)}
                            />
                        </TooltipTrigger>
                        <TooltipContent className="text-xs">
                            {RESOLUTION_META[i.res].label} : {formatNumber(i.count)} films ({i.percent.toLocaleString("fr-FR")} %)
                        </TooltipContent>
                    </Tooltip>
                ))}
            </div>
            {/* Légende (l'identité ne repose jamais sur la seule couleur) */}
            <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
                {visible.map((i) => (
                    <span key={i.res} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <span className={cn("h-2 w-2 rounded-full", RESOLUTION_META[i.res].dot)} />
                        {RESOLUTION_META[i.res].label}
                    </span>
                ))}
            </div>
        </div>
    );
}

function ResolutionTile({ res, count, percent }: { res: Resolution; count: number; percent: number }) {
    const meta = RESOLUTION_META[res];
    return (
        <div className="rounded-xl bg-white/[0.025] p-3 ring-1 ring-white/[0.05] transition-colors hover:bg-white/[0.04]">
            <div className="flex items-center justify-between gap-2">
                <span className={cn("rounded-md border px-1.5 py-0.5 text-[10px] font-semibold", meta.badge)}>{meta.label}</span>
                <span className="text-[10px] text-muted-foreground">{meta.hint}</span>
            </div>
            <p className="mt-2 text-2xl font-bold tracking-tight">
                <AnimatedNumber value={percent} decimals={percent % 1 === 0 ? 0 : 1} suffix=" %" />
            </p>
            <GradientProgress value={percent} tone={meta.tone} className="mt-2" glow={false} />
            <p className="mt-1.5 text-[11px] text-muted-foreground tabular-nums">{plural(count, "film")}</p>
        </div>
    );
}

function QualitySkeleton() {
    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3">
                <Shimmer className="h-9 w-9 rounded-xl" />
                <div className="space-y-2">
                    <Shimmer className="h-4 w-40 rounded-md" />
                    <Shimmer className="h-3 w-64 rounded-md" />
                </div>
            </div>
            <div className="grid gap-5 lg:grid-cols-3">
                <Shimmer className="h-56 rounded-2xl lg:col-span-2" />
                <Shimmer className="h-56 rounded-2xl" />
            </div>
            <Shimmer className="h-40 rounded-2xl" />
            <div className="glass space-y-2 rounded-2xl p-4">
                {Array.from({ length: 5 }).map((_, i) => (
                    <Shimmer key={i} className="h-16 w-full" />
                ))}
            </div>
        </div>
    );
}
