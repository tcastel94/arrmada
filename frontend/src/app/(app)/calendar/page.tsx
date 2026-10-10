"use client";

/**
 * Calendrier des sorties (épisodes Sonarr + films Radarr).
 * ----------------------------------------------------------------
 * Bugs corrigés :
 *  - décalage d'un jour (clés de jour en UTC alors que les cases étaient
 *    construites à minuit local) → tout est calculé en heure locale ;
 *  - mois passés vides (le backend partait toujours d'aujourd'hui) → on
 *    charge exactement le mois affiché + ses semaines débordantes ;
 *  - entrées non cliquables → lien vers la fiche film / série.
 * Vues : « Mois » (grille) et « Agenda » (liste, par défaut sur mobile).
 * URL : ?mois=2026-11 et ?vue=agenda sont partageables.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import {
    CalendarDays,
    CalendarRange,
    Check,
    ChevronLeft,
    ChevronRight,
    Download,
    Film,
    Layers,
    ListOrdered,
    Loader2,
    Tv,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/empty-state";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { calendarQueryOptions, useCalendar, type CalendarRange as Range } from "@/hooks/use-calendar";
import { useUrlState } from "@/hooks/use-url-state";
import { Segmented } from "@/components/activity/segmented";
import { MonthGrid } from "@/components/calendar/month-grid";
import { AgendaView } from "@/components/calendar/agenda-view";
import { DaySheet } from "@/components/calendar/day-sheet";
import { UpcomingPanel } from "@/components/calendar/upcoming-panel";
import { AgendaSkeleton, MonthGridSkeleton } from "@/components/calendar/calendar-skeleton";
import { useMediaQuery } from "@/components/calendar/use-media-query";
import {
    addDays,
    groupEntriesByDay,
    localDayKey,
    matchesFilters,
    monthGrid,
    monthKey,
    monthTitle,
    parseMonthKey,
    startOfMonth,
    type TypeFilter,
} from "@/components/calendar/calendar-utils";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

type View = "mois" | "agenda";

/** Titre du mois : glisse vers le haut quand on avance, vers le bas quand on
 *  recule. `custom` transmet le sens AUSSI au titre qui sort (AnimatePresence). */
const TITLE_VARIANTS: Variants = {
    enter: (dir: number) => ({ opacity: 0, y: dir >= 0 ? 14 : -14 }),
    center: { opacity: 1, y: 0 },
    exit: (dir: number) => ({ opacity: 0, y: dir >= 0 ? -14 : 14 }),
};

/** Fenêtre à charger pour un mois : grille complète + 1 jour de marge de
 *  chaque côté (un épisode diffusé à 1 h du matin heure de Paris est daté
 *  de la veille en UTC). Toujours avec les non-surveillés : le filtre est
 *  appliqué côté navigateur, sans nouvelle requête. */
function rangeForMonth(month: Date): Range {
    const grid = monthGrid(month);
    return {
        start: localDayKey(addDays(grid[0], -1)),
        end: localDayKey(addDays(grid[grid.length - 1], 1)),
        unmonitored: true,
    };
}

export default function CalendarPage() {
    const qc = useQueryClient();
    // « Aujourd'hui » figé pour la durée de vie de la page.
    const [now] = useState(() => new Date());
    const todayKey = localDayKey(now);

    const [monthParam, setMonthParam] = useUrlState<string>("mois", "");
    const [viewParam, setViewParam] = useUrlState<string>("vue", "");
    const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
    const [monitoredOnly, setMonitoredOnly] = useState(true);
    const [direction, setDirection] = useState(0);
    const [openDay, setOpenDay] = useState<string | null>(null);

    // Vue : celle de l'URL, sinon Agenda sur mobile / Mois sur grand écran.
    const isMobile = useMediaQuery("(max-width: 767px)");
    const view: View | null =
        viewParam === "mois" || viewParam === "agenda" ? viewParam : isMobile === null ? null : isMobile ? "agenda" : "mois";

    const month = useMemo(() => parseMonthKey(monthParam) ?? startOfMonth(now), [monthParam, now]);
    const mk = monthKey(month);
    const isCurrentMonth = mk === monthKey(now);
    const grid = useMemo(() => monthGrid(month), [month]);
    const range = useMemo(() => rangeForMonth(month), [month]);

    const { data, isLoading, isError, error, refetch, isPlaceholderData, isFetching } = useCalendar(30, range);

    const entries = useMemo(
        () => (data?.items ?? []).filter((e) => matchesFilters(e, typeFilter, monitoredOnly)),
        [data, typeFilter, monitoredOnly],
    );
    const byDay = useMemo(() => groupEntriesByDay(entries), [entries]);

    // Jours du mois affiché (hors semaines débordantes) qui ont des sorties.
    const monthDays = useMemo(
        () =>
            Array.from(byDay.entries())
                .filter(([key]) => key.startsWith(mk))
                .sort(([a], [b]) => a.localeCompare(b)),
        [byDay, mk],
    );
    const stats = useMemo(() => {
        const list = monthDays.flatMap(([, l]) => l);
        return {
            total: list.length,
            episodes: list.filter((e) => e.type === "episode").length,
            movies: list.filter((e) => e.type === "movie").length,
            downloaded: list.filter((e) => e.has_file).length,
        };
    }, [monthDays]);

    const goToMonth = (target: Date, dir: number) => {
        setDirection(dir);
        setOpenDay(null);
        const key = monthKey(target);
        setMonthParam(key === monthKey(now) ? "" : key);
    };
    const shift = (delta: number) => goToMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1), delta);
    // Précharge le mois voisin au survol des flèches : le clic est instantané.
    const prefetch = (delta: number) =>
        qc.prefetchQuery(calendarQueryOptions(30, rangeForMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1))));

    const changing = isFetching && isPlaceholderData;

    return (
        <>
            <Header title="Calendrier" />
            <PageContainer>
                <PageHeader
                    icon={CalendarDays}
                    accent="sky"
                    eyebrow="Bibliothèque"
                    title="Calendrier"
                    description="Les épisodes et films attendus par Sonarr et Radarr, jour par jour. Clique une sortie pour ouvrir sa fiche."
                    actions={
                        view && (
                            <Segmented<View>
                                ariaLabel="Mode d'affichage"
                                value={view}
                                onChange={(v) => setViewParam(v)}
                                options={[
                                    { value: "mois", label: "Mois", icon: CalendarRange },
                                    { value: "agenda", label: "Agenda", icon: ListOrdered },
                                ]}
                            />
                        )
                    }
                >
                    <StatPill label="sorties ce mois-ci" value={<AnimatedNumber value={stats.total} />} icon={Layers} tone="primary" />
                    <StatPill label={stats.episodes > 1 ? "épisodes" : "épisode"} value={<AnimatedNumber value={stats.episodes} />} icon={Tv} />
                    <StatPill label={stats.movies > 1 ? "films" : "film"} value={<AnimatedNumber value={stats.movies} />} icon={Film} />
                    <StatPill
                        label={stats.downloaded > 1 ? "déjà téléchargés" : "déjà téléchargé"}
                        value={<AnimatedNumber value={stats.downloaded} />}
                        icon={Download}
                        tone="success"
                    />
                </PageHeader>

                {/* Panneau « Prochaines sorties » à droite seulement sur très grand écran :
                    en dessous, la grille a besoin de toute la largeur pour rester lisible. */}
                <div className="grid gap-6 min-[1800px]:grid-cols-[minmax(0,1fr)_360px]">
                    <SpotlightCard interactive={false} className="min-w-0 p-3 sm:p-4">
                        {/* ── Barre d'outils : navigation + filtres ── */}
                        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                            <div className="flex items-center gap-1.5">
                                <Button
                                    variant="outline"
                                    size="icon-sm"
                                    aria-label="Mois précédent"
                                    onClick={() => shift(-1)}
                                    onMouseEnter={() => prefetch(-1)}
                                    onFocus={() => prefetch(-1)}
                                >
                                    <ChevronLeft />
                                </Button>
                                <div className="relative min-w-[11rem] overflow-hidden px-1 text-center sm:min-w-[13rem]">
                                    <AnimatePresence mode="popLayout" initial={false} custom={direction}>
                                        <motion.h2
                                            key={mk}
                                            custom={direction}
                                            variants={TITLE_VARIANTS}
                                            initial="enter"
                                            animate="center"
                                            exit="exit"
                                            transition={{ duration: 0.3, ease: EASE_OUT }}
                                            className="text-lg font-bold tracking-tight sm:text-xl"
                                            aria-live="polite"
                                        >
                                            {monthTitle(month)}
                                        </motion.h2>
                                    </AnimatePresence>
                                </div>
                                <Button
                                    variant="outline"
                                    size="icon-sm"
                                    aria-label="Mois suivant"
                                    onClick={() => shift(1)}
                                    onMouseEnter={() => prefetch(1)}
                                    onFocus={() => prefetch(1)}
                                >
                                    <ChevronRight />
                                </Button>
                                {!isCurrentMonth && (
                                    <Button
                                        variant="glow"
                                        size="sm"
                                        className="ml-1"
                                        onClick={() => goToMonth(startOfMonth(now), month > now ? -1 : 1)}
                                    >
                                        Aujourd&apos;hui
                                    </Button>
                                )}
                                {changing && <Loader2 className="ml-1 h-4 w-4 animate-spin text-sky-300" aria-label="Chargement du mois" />}
                            </div>

                            <div className="flex flex-wrap items-center gap-3">
                                <Segmented<TypeFilter>
                                    ariaLabel="Type de sortie"
                                    size="sm"
                                    value={typeFilter}
                                    onChange={setTypeFilter}
                                    options={[
                                        { value: "all", label: "Tout" },
                                        { value: "episode", label: "Séries", icon: Tv, tone: "text-sky-300" },
                                        { value: "movie", label: "Films", icon: Film, tone: "text-violet-300" },
                                    ]}
                                />
                                <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                                    <Switch checked={monitoredOnly} onCheckedChange={setMonitoredOnly} aria-label="Surveillés seulement" />
                                    Surveillés seulement
                                </label>
                            </div>
                        </div>

                        {/* ── Légende ── */}
                        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[11px] text-muted-foreground" aria-label="Légende">
                            <span className="inline-flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_8px_hsl(199_89%_60%)]" /> Séries
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-full bg-violet-400 shadow-[0_0_8px_hsl(262_83%_65%)]" /> Films
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                                <Check className="h-3 w-3 text-emerald-300" strokeWidth={3} /> Déjà téléchargé
                            </span>
                            {!monitoredOnly && (
                                <span className="inline-flex items-center gap-1.5">
                                    <span className="h-2.5 w-4 rounded-sm border border-dashed border-white/30" /> Non surveillé
                                </span>
                            )}
                            <span className="inline-flex items-center gap-1.5">
                                <span className="h-2.5 w-2.5 rounded-full bg-sky-400 shadow-[0_0_8px_hsl(199_89%_60%)]" /> Aujourd&apos;hui
                            </span>
                        </div>

                        {/* ── Vue ── */}
                        {isError ? (
                            <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger le calendrier" />
                        ) : isLoading || !view ? (
                            view === "agenda" ? <AgendaSkeleton /> : <MonthGridSkeleton />
                        ) : view === "mois" ? (
                            <>
                                <MonthGrid
                                    days={grid}
                                    month={month}
                                    byDay={byDay}
                                    todayKey={todayKey}
                                    direction={direction}
                                    onOpenDay={setOpenDay}
                                />
                                {stats.total === 0 && !changing && (
                                    <p className="mt-3 text-center text-xs text-muted-foreground">
                                        Aucune sortie ce mois-ci avec ces filtres
                                        {monitoredOnly ? " — essaie d'afficher aussi les éléments non surveillés." : "."}
                                    </p>
                                )}
                            </>
                        ) : (
                            <div className={cn("transition-opacity", changing && "opacity-60")}>
                                <AgendaView
                                    key={mk}
                                    days={monthDays}
                                    todayKey={todayKey}
                                    isCurrentMonth={isCurrentMonth}
                                    onNextMonth={() => shift(1)}
                                />
                            </div>
                        )}
                    </SpotlightCard>

                    {/* En vue Agenda du mois en cours, la liste démarre déjà à aujourd'hui :
                        le panneau ferait doublon. */}
                    {!(view === "agenda" && isCurrentMonth) && (
                        <UpcomingPanel
                            todayKey={todayKey}
                            typeFilter={typeFilter}
                            monitoredOnly={monitoredOnly}
                            className="min-[1800px]:sticky min-[1800px]:top-20 min-[1800px]:self-start"
                        />
                    )}
                </div>
            </PageContainer>

            <DaySheet dayKey={openDay} byDay={byDay} onClose={() => setOpenDay(null)} />
        </>
    );
}
