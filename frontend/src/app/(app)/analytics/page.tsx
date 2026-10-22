"use client";

/**
 * Statistiques (/analytics) : radiographie de la médiathèque.
 * ----------------------------------------------------------------
 * Refonte : héros standard, panneaux verre, compteurs animés, palette
 * unique (--chart-1..5, films = violet comme ailleurs), info-bulles
 * communes en français, chaque graphe consultable en tableau.
 * Choix de formes (cf. principes dataviz) :
 *  - genres : barres horizontales (un anneau à 10 parts se lisait mal et
 *    ses libellés se chevauchaient sur mobile) ;
 *  - services : barre empilée + légende (peu de catégories) ;
 *  - années : colonnes dans le temps.
 */
import { useId, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, BarChart3, CalendarRange, ChevronRight, Film, HardDrive, Layers, Loader2, PieChart, Server, Tags, Trophy, Tv } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { RingGauge } from "@/components/fx/ring-gauge";
import { Tooltip as UiTooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAnalytics, type AnalyticsData, type BiggestItem, type DistributionItem } from "@/hooks/use-analytics";
import type { SearchResponse } from "@/hooks/use-media";
import { apiFetch } from "@/lib/api-client";
import { formatBytes, formatNumber, percent, plural } from "@/lib/format";
import { frSize, parseHumanSize } from "@/components/maintenance/size";
import { fadeUp, stagger, EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
    AXIS_TICK,
    CATEGORICAL,
    CHART,
    ChartPanel,
    ChartTooltip,
    GRID_STROKE,
    MOVIE_COLOR,
    SERIES_COLOR,
} from "@/components/analytics/chart-kit";
import { genreFr } from "@/components/analytics/genres";

/** Les séries renvoient un ID de profil (« 4 ») comme qualité : on les écarte. */
const isProfileId = (q: string) => /^\d+$/.test(q.trim());

export default function AnalyticsPage() {
    const { data, isLoading, isError, error, refetch } = useAnalytics();
    const o = data?.overview;
    const availablePct = o ? percent(o.available, o.total_items) : 0;

    return (
        <>
            <Header title="Statistiques" />
            <PageContainer>
                <PageHeader
                    icon={BarChart3}
                    accent="emerald"
                    title="Statistiques"
                    description="La radiographie de ta médiathèque : volumes, qualité, genres, années et poids lourds."
                >
                    {o && (
                        <>
                            <StatPill icon={Layers} label="médias" value={<AnimatedNumber value={o.total_items} />} tone="primary" />
                            <StatPill icon={HardDrive} label="sur disque" value={formatBytes(o.total_size_bytes)} />
                            <StatPill
                                icon={PieChart}
                                label="disponibles"
                                value={<AnimatedNumber value={availablePct} suffix=" %" />}
                                tone={availablePct >= 90 ? "success" : "warning"}
                            />
                            {o.missing > 0 && <StatPill icon={AlertTriangle} label="manquants" value={formatNumber(o.missing)} tone="warning" />}
                        </>
                    )}
                </PageHeader>

                {isLoading ? (
                    <AnalyticsSkeleton />
                ) : isError || !data ? (
                    <Panel>
                        <ErrorState error={error} onRetry={() => refetch()} title="Statistiques indisponibles" />
                    </Panel>
                ) : data.overview.total_items === 0 ? (
                    <Panel>
                        <EmptyState
                            icon={BarChart3}
                            title="Médiathèque vide"
                            description="Ajoute des films ou des séries pour voir apparaître les statistiques."
                            action={{ label: "Rechercher & ajouter", href: "/search" }}
                        />
                    </Panel>
                ) : (
                    <AnalyticsContent data={data} />
                )}
            </PageContainer>
        </>
    );
}

function AnalyticsContent({ data }: { data: AnalyticsData }) {
    const { overview: o } = data;

    // Qualités des films seulement (cf. isProfileId), triées, top 10.
    const qualities = useMemo(
        () => data.quality_distribution.filter((q) => !isProfileId(q.name)).sort((a, b) => b.count - a.count).slice(0, 10),
        [data.quality_distribution],
    );
    // Genres traduits en français (les *arr les renvoient en anglais).
    const genres = useMemo(
        () =>
            [...data.genre_distribution]
                .sort((a, b) => b.count - a.count)
                .slice(0, 10)
                .map((g) => ({ ...g, name: genreFr(g.name) })),
        [data.genre_distribution],
    );

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            {/* Indicateurs clés */}
            {/* 2 colonnes dès le mobile (tuiles compactes), 4 sur grand écran */}
            <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
                <KpiTile
                    icon={Film}
                    iconClass="bg-primary/15 text-primary ring-primary/25"
                    label="Films"
                    value={<AnimatedNumber value={o.movies} />}
                    sub={`${frSize(o.movie_size_human)} · moy. ${frSize(o.avg_movie_size_human)}`}
                />
                <KpiTile
                    icon={Tv}
                    iconClass="bg-blue-500/15 text-blue-300 ring-blue-400/25"
                    label="Séries"
                    value={<AnimatedNumber value={o.series} />}
                    sub={`${frSize(o.series_size_human)} · moy. ${frSize(o.avg_series_size_human)}`}
                />
                <KpiTile
                    icon={HardDrive}
                    iconClass="bg-success/15 text-success ring-success/25"
                    label="Stockage total"
                    className="col-span-2 sm:col-span-1"
                    value={formatBytes(o.total_size_bytes)}
                    sub={`${plural(o.monitored, "média surveillé", "médias surveillés")}`}
                />
                <motion.div variants={fadeUp} className="col-span-2 sm:col-span-1">
                    <Link
                        href="/media/missing"
                        className="glass glass-hover spotlight flex h-full items-center gap-4 rounded-2xl p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                    >
                        <RingGauge value={percent(o.available, o.total_items)} size={72} stroke={7} tone="emerald">
                            <span className="text-xs font-bold tabular-nums">{Math.round(percent(o.available, o.total_items))} %</span>
                        </RingGauge>
                        <div className="min-w-0 flex-1">
                            <p className="text-xs text-muted-foreground">Disponibles</p>
                            <p className="text-lg font-bold">
                                <AnimatedNumber value={o.available} /> <span className="text-xs font-normal text-muted-foreground">/ {formatNumber(o.total_items)}</span>
                            </p>
                            <p className={cn("text-[11px]", o.missing > 0 ? "text-warning" : "text-muted-foreground")}>
                                {o.missing > 0 ? `${plural(o.missing, "manquant")} · voir la liste` : "Rien ne manque"}
                            </p>
                        </div>
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    </Link>
                </motion.div>
            </div>

            {/* Films / séries + services */}
            <div className="grid gap-5 lg:grid-cols-2">
                <motion.div variants={fadeUp}>
                    <Panel title="Films et séries" icon={Layers} iconClassName="text-success" className="h-full">
                        <SplitBar
                            label="En nombre"
                            parts={[
                                { key: "movies", label: "Films", value: o.movies, display: formatNumber(o.movies), color: MOVIE_COLOR },
                                { key: "series", label: "Séries", value: o.series, display: formatNumber(o.series), color: SERIES_COLOR },
                            ]}
                        />
                        <SplitBar
                            className="mt-5"
                            label="En place sur le disque"
                            parts={[
                                { key: "movies", label: "Films", value: parseHumanSize(o.movie_size_human), display: frSize(o.movie_size_human), color: MOVIE_COLOR },
                                { key: "series", label: "Séries", value: parseHumanSize(o.series_size_human), display: frSize(o.series_size_human), color: SERIES_COLOR },
                            ]}
                        />
                    </Panel>
                </motion.div>
                <motion.div variants={fadeUp}>
                    <ServicesPanel items={data.service_breakdown} />
                </motion.div>
            </div>

            {/* Qualité + genres */}
            <div className="grid gap-5 lg:grid-cols-2">
                <motion.div variants={fadeUp}>
                    <ChartPanel
                        title="Qualité des films"
                        icon={BarChart3}
                        iconClassName="text-primary"
                        description="Les 10 qualités les plus présentes (les séries sont classées par profil, pas par fichier)."
                        rows={qualities}
                        rowKey={(r) => r.name}
                        columns={[
                            { header: "Qualité", cell: (r) => r.name },
                            { header: "Films", cell: (r) => formatNumber(r.count), align: "right" },
                        ]}
                    >
                        <HorizontalBars data={qualities} valueLabel="Films" />
                    </ChartPanel>
                </motion.div>
                <motion.div variants={fadeUp}>
                    <ChartPanel
                        title="Genres les plus représentés"
                        icon={Tags}
                        iconClassName="text-primary"
                        description="Un média peut avoir plusieurs genres."
                        rows={genres}
                        rowKey={(r) => r.name}
                        columns={[
                            { header: "Genre", cell: (r) => r.name },
                            { header: "Médias", cell: (r) => formatNumber(r.count), align: "right" },
                        ]}
                    >
                        <HorizontalBars data={genres} valueLabel="Médias" />
                    </ChartPanel>
                </motion.div>
            </div>

            {/* Années */}
            <motion.div variants={fadeUp}>
                <ChartPanel
                    title="Années de sortie"
                    icon={CalendarRange}
                    iconClassName="text-warning"
                    rows={[...data.year_distribution].reverse()}
                    rowKey={(r) => String(r.year)}
                    columns={[
                        { header: "Année", cell: (r) => r.year },
                        { header: "Médias", cell: (r) => formatNumber(r.count), align: "right" },
                    ]}
                >
                    {data.year_distribution.length === 0 ? (
                        <EmptyState compact icon={CalendarRange} title="Pas d'années connues" />
                    ) : (
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={data.year_distribution} margin={{ top: 8, right: 4, bottom: 0, left: -12 }}>
                                <defs>
                                    <linearGradient id="year-fill" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor={CHART.c1} stopOpacity={1} />
                                        <stop offset="100%" stopColor={CHART.c1} stopOpacity={0.45} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid vertical={false} stroke={GRID_STROKE} />
                                <XAxis dataKey="year" tick={AXIS_TICK} axisLine={false} tickLine={false} minTickGap={24} />
                                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} width={44} />
                                <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.35)" }} content={<ChartTooltip valueLabel="Médias" />} />
                                <Bar dataKey="count" fill="url(#year-fill)" radius={[4, 4, 0, 0]} maxBarSize={24} animationDuration={900} />
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </ChartPanel>
            </motion.div>

            {/* Top 10 */}
            <motion.div variants={fadeUp}>
                <TopBiggest items={data.top_biggest} />
            </motion.div>
        </motion.div>
    );
}

/* ── Composants ────────────────────────────────────────────── */

function KpiTile({
    icon: Icon,
    iconClass,
    label,
    value,
    sub,
    className,
}: {
    icon: typeof Film;
    iconClass: string;
    label: string;
    value: React.ReactNode;
    sub: string;
    className?: string;
}) {
    return (
        <motion.div
            variants={fadeUp}
            className={cn("glass spotlight flex flex-col gap-3 rounded-2xl p-3.5 sm:flex-row sm:items-center sm:gap-4 sm:p-4", className)}
        >
            {/* Fond teinté + icône claire : l'ancienne tuile avait une icône de la même couleur que son fond. */}
            <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1 sm:h-12 sm:w-12 sm:rounded-2xl", iconClass)}>
                <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
            </span>
            <div className="min-w-0">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-2xl font-bold tracking-tight">{value}</p>
                <p className="truncate text-[11px] text-muted-foreground">{sub}</p>
            </div>
        </motion.div>
    );
}

/** Barre à deux segments avec légende et valeurs (lisible sans survol). */
function SplitBar({
    label,
    parts,
    className,
}: {
    label: string;
    parts: { key: string; label: string; value: number; display: string; color: string }[];
    className?: string;
}) {
    const total = parts.reduce((s, p) => s + p.value, 0);
    return (
        <div className={className}>
            <p className="mb-2 text-xs text-muted-foreground">{label}</p>
            <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full bg-muted/40">
                {parts.map((p, i) =>
                    p.value > 0 ? (
                        <motion.div
                            key={p.key}
                            initial={{ width: 0 }}
                            animate={{ width: `${percent(p.value, total)}%` }}
                            transition={{ duration: 1, delay: 0.2 + i * 0.1, ease: EASE_OUT }}
                            className="h-full first:rounded-l-full last:rounded-r-full"
                            style={{ background: p.color }}
                        />
                    ) : null,
                )}
            </div>
            <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs">
                {parts.map((p) => (
                    <span key={p.key} className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-sm" style={{ background: p.color }} />
                        <span className="text-muted-foreground">{p.label}</span>
                        <span className="font-semibold tabular-nums">{p.display}</span>
                        <span className="text-muted-foreground tabular-nums">({Math.round(percent(p.value, total))} %)</span>
                    </span>
                ))}
            </div>
        </div>
    );
}

/** Répartition par service : barre empilée, couleur fixe par service (ordre alphabétique). */
function ServicesPanel({ items }: { items: { name: string; count: number }[] }) {
    const parts = useMemo(() => {
        // Couleur liée au service (jamais à son rang) : un Radarr prend la
        // couleur des films (violet), un Sonarr celle des séries (bleu), comme
        // partout ailleurs ; les autres prennent les teintes restantes dans
        // l'ordre alphabétique. Au-delà de 5 services → « Autres ».
        const sorted = [...items].sort((a, b) => a.name.localeCompare(b.name, "fr"));
        const spare = CATEGORICAL.filter((c) => c !== MOVIE_COLOR && c !== SERIES_COLOR);
        const used = new Set<string>();
        const colorFor = (name: string): string => {
            const n = name.toLowerCase();
            const wanted = n.includes("radarr") ? MOVIE_COLOR : n.includes("sonarr") ? SERIES_COLOR : undefined;
            if (wanted && !used.has(wanted)) {
                used.add(wanted);
                return wanted;
            }
            const next = spare.find((c) => !used.has(c)) ?? CHART.other;
            used.add(next);
            return next;
        };
        const main: { name: string; count: number; color: string }[] = sorted
            .slice(0, 5)
            .map((s) => ({ ...s, color: colorFor(s.name) }));
        const rest = sorted.slice(5);
        if (rest.length) main.push({ name: "Autres", count: rest.reduce((s, r) => s + r.count, 0), color: CHART.other });
        return main;
    }, [items]);
    const total = parts.reduce((s, p) => s + p.count, 0);

    return (
        <Panel title="Répartition par service" icon={Server} iconClassName="text-success" className="h-full">
            {parts.length === 0 ? (
                <EmptyState compact icon={Server} title="Aucun service" />
            ) : (
                <>
                    <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full bg-muted/40">
                        {parts.map((p, i) => (
                            <UiTooltip key={p.name}>
                                <TooltipTrigger asChild>
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${percent(p.count, total)}%` }}
                                        transition={{ duration: 1, delay: 0.2 + i * 0.08, ease: EASE_OUT }}
                                        className="h-full min-w-[3px] first:rounded-l-full last:rounded-r-full"
                                        style={{ background: p.color }}
                                    />
                                </TooltipTrigger>
                                <TooltipContent className="text-xs">
                                    {p.name} : {formatNumber(p.count)} médias
                                </TooltipContent>
                            </UiTooltip>
                        ))}
                    </div>
                    <ul className="mt-4 space-y-2">
                        {parts.map((p) => (
                            <li key={p.name} className="flex items-center gap-3 text-sm">
                                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: p.color }} />
                                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                                <span className="font-semibold tabular-nums">{formatNumber(p.count)}</span>
                                <span className="w-12 text-right text-xs text-muted-foreground tabular-nums">{Math.round(percent(p.count, total))} %</span>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </Panel>
    );
}

/** Barres horizontales à série unique (couleur --chart-1), triées. */
function HorizontalBars({ data, valueLabel }: { data: DistributionItem[]; valueLabel: string }) {
    // Identifiant unique du dégradé SVG (deux graphes sur la page).
    const gradientId = `hbar-${useId().replace(/:/g, "")}`;
    if (data.length === 0) return <EmptyState compact icon={BarChart3} title="Aucune donnée" />;
    const height = data.length * 30 + 16;
    return (
        <ResponsiveContainer width="100%" height={height}>
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
                <defs>
                    <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor={CHART.c1} stopOpacity={0.55} />
                        <stop offset="100%" stopColor={CHART.c1} stopOpacity={1} />
                    </linearGradient>
                </defs>
                <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
                <XAxis type="number" tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={112} tick={AXIS_TICK} axisLine={false} tickLine={false} interval={0} />
                <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.35)" }} content={<ChartTooltip valueLabel={valueLabel} labelKey="name" />} />
                <Bar dataKey="count" fill={`url(#${gradientId})`} radius={[0, 4, 4, 0]} maxBarSize={18} animationDuration={900} />
            </BarChart>
        </ResponsiveContainer>
    );
}

/** Top 10 des plus gros médias, avec lien vers la fiche. */
function TopBiggest({ items }: { items: BiggestItem[] }) {
    const router = useRouter();
    const [resolving, setResolving] = useState<string | null>(null);
    const max = Math.max(1, ...items.map((i) => i.size_bytes || 0));

    /**
     * Le backend ne renvoie pas encore l'ID du média : on le retrouve via
     * la recherche de la bibliothèque (titre exact + même type).
     */
    const open = async (item: BiggestItem) => {
        const type = item.type === "series" ? "series" : "movie";
        if (item.external_id !== undefined && item.external_id !== null) {
            router.push(`/media/${type}/${item.external_id}`);
            return;
        }
        setResolving(item.title);
        try {
            const res = await apiFetch<SearchResponse>(`/api/media/search?q=${encodeURIComponent(item.title)}`);
            const match =
                res.items.find((m) => m.type === type && m.title.toLowerCase() === item.title.toLowerCase()) ??
                res.items.find((m) => m.type === type);
            if (match) router.push(`/media/${match.type}/${match.external_id}`);
            else toast.error(`Fiche introuvable pour « ${item.title} »`);
        } catch (e) {
            toast.error("Recherche impossible", { description: e instanceof Error ? e.message : undefined });
        } finally {
            setResolving(null);
        }
    };

    return (
        <Panel title="Les 10 plus volumineux" icon={Trophy} iconClassName="text-warning" bodyClassName="p-2 sm:p-3">
            {items.length === 0 ? (
                <EmptyState compact icon={Trophy} title="Aucun fichier" />
            ) : (
                <ol className="grid gap-1 md:grid-cols-2 md:gap-x-4">
                    {items.map((item, i) => {
                        const isSeries = item.type === "series";
                        const Icon = isSeries ? Tv : Film;
                        const busy = resolving === item.title;
                        return (
                            <li key={`${item.type}:${item.title}`}>
                                <button
                                    type="button"
                                    onClick={() => open(item)}
                                    disabled={!!resolving}
                                    className="group grid w-full grid-cols-[1.75rem_minmax(0,1fr)_auto] items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-white/[0.04] focus-visible:bg-white/[0.04] focus-visible:outline-none disabled:opacity-70"
                                >
                                    <span
                                        className={cn(
                                            "flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold tabular-nums",
                                            i < 3 ? "bg-warning/15 text-warning" : "bg-white/[0.05] text-muted-foreground",
                                        )}
                                    >
                                        {i + 1}
                                    </span>
                                    <span className="min-w-0">
                                        <span className="flex items-center gap-1.5">
                                            <Icon className={cn("h-3.5 w-3.5 shrink-0", isSeries ? "text-blue-400" : "text-primary")} />
                                            <span className="truncate text-sm font-medium transition-colors group-hover:text-primary">{item.title}</span>
                                        </span>
                                        {/* Barre proportionnelle au plus gros (lecture immédiate des écarts) */}
                                        <span className="mt-1.5 block h-1 w-full overflow-hidden rounded-full bg-muted/40">
                                            <motion.span
                                                className="block h-full rounded-full"
                                                style={{ background: isSeries ? SERIES_COLOR : MOVIE_COLOR }}
                                                initial={{ width: 0 }}
                                                animate={{ width: `${percent(item.size_bytes, max)}%` }}
                                                transition={{ duration: 0.9, delay: 0.1 + i * 0.04, ease: EASE_OUT }}
                                            />
                                        </span>
                                    </span>
                                    <span className="flex items-center gap-2">
                                        {item.quality && !isProfileId(item.quality) && (
                                            <span className="hidden rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline">
                                                {item.quality}
                                            </span>
                                        )}
                                        <span className="text-sm font-semibold tabular-nums">{formatBytes(item.size_bytes)}</span>
                                        {busy ? (
                                            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                                        ) : (
                                            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                                        )}
                                    </span>
                                </button>
                            </li>
                        );
                    })}
                </ol>
            )}
        </Panel>
    );
}

function AnalyticsSkeleton() {
    return (
        <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Shimmer key={i} className="h-24 rounded-2xl" />
                ))}
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
                <Shimmer className="h-48 rounded-2xl" />
                <Shimmer className="h-48 rounded-2xl" />
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
                <Shimmer className="h-80 rounded-2xl" />
                <Shimmer className="h-80 rounded-2xl" />
            </div>
            <Shimmer className="h-72 rounded-2xl" />
        </div>
    );
}
