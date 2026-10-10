"use client";

/**
 * Journal — tout ce qui se passe dans la stack : téléchargements, imports,
 * sous-titres, lectures Kodi/Cast, ajouts, suppressions…
 * ----------------------------------------------------------------
 * - Timeline verticale animée, regroupée par jour (heure locale).
 * - Filtres synchronisés à l'URL (partageables) :
 *     ?cat=download,subtitle  ?statut=ko  ?q=dune  ?vue=media
 * - « Charger plus » augmente progressivement le nombre d'évènements
 *   demandés (50 → 100 → … → 500, plafond du backend) ; la liste actuelle
 *   reste affichée pendant la requête (keepPreviousData dans le hook).
 */
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
    Activity,
    AlertOctagon,
    CalendarClock,
    CheckCircle2,
    FilterX,
    Info,
    LayoutGrid,
    Loader2,
    RefreshCw,
    Rows3,
    Search,
    X,
    XCircle,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActivityTimeline, type TimelineItem } from "@/hooks/use-activity";
import { useUrlState } from "@/hooks/use-url-state";
import { Segmented } from "@/components/activity/segmented";
import { CATEGORIES } from "@/components/activity/activity-meta";
import { ActivityTimeline, MediaGroups, TimelineSkeleton } from "@/components/activity/timeline";
import { useUrlSearch } from "@/components/activity/use-url-search";
import { localDayKey } from "@/components/activity/day-groups";
import { plural } from "@/lib/format";
import { fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

type StatusFilter = "all" | "ok" | "ko" | "info";
type View = "chrono" | "media";

/** Taille d'une « page » d'évènements et plafond du backend. */
const PAGE = 50;
const MAX_LIMIT = 500;

export default function ActivityPage() {
    const [catParam, setCatParam] = useUrlState<string>("cat", "");
    const [status, setStatus] = useUrlState<StatusFilter>("statut", "all");
    const [view, setView] = useUrlState<View>("vue", "chrono");
    const { input, setInput, search } = useUrlSearch("q");

    const cats = useMemo(() => catParam.split(",").filter(Boolean), [catParam]);

    // « Charger plus » : le nombre demandé repart de PAGE quand un filtre change.
    const filterKey = `${catParam}|${status}|${search}|${view}`;
    const [more, setMore] = useState({ key: filterKey, limit: PAGE });
    const limit = more.key === filterKey ? more.limit : PAGE;

    const { data, isLoading, isError, error, refetch, isFetching, isPlaceholderData } = useActivityTimeline({
        categories: cats.length ? cats : undefined,
        statuses: status === "all" ? undefined : [status],
        search: search || undefined,
        group: view === "media" ? "media" : "none",
        limit,
    });

    // Tous les évènements chargés (aplatis si la vue est groupée) → stats du héros.
    const flat: TimelineItem[] = useMemo(
        () => (data?.grouped ? (data.groups ?? []).flatMap((g) => g.items) : data?.items ?? []),
        [data],
    );
    const stats = useMemo(() => {
        const today = localDayKey(new Date());
        let ok = 0;
        let ko = 0;
        let todayCount = 0;
        for (const it of flat) {
            if (it.status === "ok") ok += 1;
            else if (it.status === "ko") ko += 1;
            if (localDayKey(new Date(it.ts * 1000)) === today) todayCount += 1;
        }
        return { ok, ko, today: todayCount };
    }, [flat]);

    const total = data?.total ?? 0;
    const canLoadMore = total >= limit && limit < MAX_LIMIT;
    const filtersActive = cats.length > 0 || status !== "all" || search !== "";
    const loadingMore = isFetching && isPlaceholderData;

    const toggleCat = (key: string) => {
        const next = cats.includes(key) ? cats.filter((c) => c !== key) : [...cats, key];
        setCatParam(next.join(","));
    };
    const resetFilters = () => {
        setCatParam("");
        setStatus("all");
        setInput("");
    };

    return (
        <>
            <Header title="Journal" />
            <PageContainer>
                <PageHeader
                    icon={Activity}
                    accent="emerald"
                    eyebrow="Activité"
                    title="Journal"
                    description="Téléchargements, imports, sous-titres, lectures, ajouts : tout ce qui se passe dans ta stack, au fil de l'eau."
                    actions={
                        <Button variant="outline" size="icon" onClick={() => refetch()} aria-label="Rafraîchir le journal">
                            <RefreshCw className={cn(isFetching && "animate-spin")} />
                        </Button>
                    }
                >
                    <StatPill
                        label={total > 1 ? "évènements" : "évènement"}
                        value={
                            <>
                                <AnimatedNumber value={total} />
                                {canLoadMore ? "+" : ""}
                            </>
                        }
                        icon={Activity}
                        tone="success"
                    />
                    <StatPill label="aujourd'hui" value={<AnimatedNumber value={stats.today} />} icon={CalendarClock} />
                    <StatPill label="succès" value={<AnimatedNumber value={stats.ok} />} icon={CheckCircle2} />
                    <StatPill
                        label={stats.ko > 1 ? "échecs" : "échec"}
                        value={<AnimatedNumber value={stats.ko} />}
                        icon={XCircle}
                        tone={stats.ko > 0 ? "danger" : "default"}
                    />
                </PageHeader>

                {/* ── Filtres ─────────────────────────────────────── */}
                <motion.div variants={fadeUp} initial="hidden" animate="show">
                    <SpotlightCard interactive={false} className="space-y-3 p-3 sm:p-4">
                        <div
                            className="-mx-1 flex items-center gap-2 overflow-x-auto px-1 pb-0.5 scrollbar-none sm:flex-wrap"
                            role="group"
                            aria-label="Filtrer par catégorie"
                        >
                            <button
                                type="button"
                                className="chip shrink-0"
                                data-active={cats.length === 0}
                                aria-pressed={cats.length === 0}
                                onClick={() => setCatParam("")}
                            >
                                Tout
                            </button>
                            {CATEGORIES.map((c) => {
                                const active = cats.includes(c.key);
                                return (
                                    <button
                                        key={c.key}
                                        type="button"
                                        className="chip shrink-0"
                                        data-active={active}
                                        aria-pressed={active}
                                        onClick={() => toggleCat(c.key)}
                                    >
                                        <c.icon className={cn("h-3.5 w-3.5", !active && c.text)} />
                                        {c.label}
                                    </button>
                                );
                            })}
                        </div>
                        <div className="flex flex-col gap-2 md:flex-row md:items-center">
                            <div className="relative md:max-w-xs md:flex-1">
                                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                                <Input
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Filtrer par titre…"
                                    aria-label="Filtrer par titre"
                                    className="h-9 pl-9 pr-9"
                                />
                                {input && (
                                    <button
                                        type="button"
                                        onClick={() => setInput("")}
                                        aria-label="Effacer la recherche"
                                        className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                            </div>
                            <div className="flex flex-wrap items-center gap-2 md:ml-auto">
                                <Segmented<StatusFilter>
                                    ariaLabel="Filtrer par statut"
                                    size="sm"
                                    value={status}
                                    onChange={setStatus}
                                    options={[
                                        { value: "all", label: "Tous" },
                                        { value: "ok", label: "Succès", icon: CheckCircle2, tone: "text-emerald-300" },
                                        { value: "ko", label: "Échecs", icon: AlertOctagon, tone: "text-red-300" },
                                        { value: "info", label: "Info", icon: Info, tone: "text-sky-300" },
                                    ]}
                                />
                                <Segmented<View>
                                    ariaLabel="Mode d'affichage"
                                    size="sm"
                                    value={view}
                                    onChange={setView}
                                    options={[
                                        { value: "chrono", label: "Chronologique", icon: Rows3 },
                                        { value: "media", label: "Par média", icon: LayoutGrid },
                                    ]}
                                />
                                {filtersActive && (
                                    <Button variant="ghost" size="sm" onClick={resetFilters}>
                                        <FilterX /> Réinitialiser
                                    </Button>
                                )}
                            </div>
                        </div>
                    </SpotlightCard>
                </motion.div>

                {/* ── Contenu ─────────────────────────────────────── */}
                {isLoading ? (
                    <TimelineSkeleton />
                ) : isError ? (
                    <SpotlightCard interactive={false}>
                        <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger le journal" />
                    </SpotlightCard>
                ) : total === 0 ? (
                    <SpotlightCard interactive={false}>
                        {filtersActive ? (
                            <EmptyState
                                icon={FilterX}
                                title="Aucun évènement pour ces filtres"
                                description="Élargis la recherche ou retire un filtre pour voir plus d'activité."
                                action={{ label: "Réinitialiser les filtres", onClick: resetFilters }}
                            />
                        ) : (
                            <EmptyState
                                icon={Activity}
                                title="Aucune activité pour l'instant"
                                description="Les téléchargements, imports, sous-titres et lectures apparaîtront ici au fil de l'eau."
                            />
                        )}
                    </SpotlightCard>
                ) : (
                    <div className={cn("space-y-6 transition-opacity duration-300", loadingMore && "opacity-70")}>
                        {data?.grouped ? <MediaGroups groups={data.groups ?? []} /> : <ActivityTimeline items={data?.items ?? []} />}

                        <div className="flex flex-col items-center gap-2 pb-2">
                            {canLoadMore ? (
                                <Button
                                    variant="outline"
                                    onClick={() => setMore({ key: filterKey, limit: Math.min(limit + PAGE, MAX_LIMIT) })}
                                    disabled={loadingMore}
                                >
                                    {loadingMore && <Loader2 className="animate-spin" />}
                                    Charger plus
                                </Button>
                            ) : null}
                            <p className="text-[11px] text-muted-foreground">
                                {plural(total, "évènement affiché", "évènements affichés")}
                                {!canLoadMore && total >= MAX_LIMIT ? " (maximum atteint)" : ""}
                            </p>
                        </div>
                    </div>
                )}
            </PageContainer>
        </>
    );
}
