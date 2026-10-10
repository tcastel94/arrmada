"use client";

/**
 * « Prochaines sorties » : les 10 prochaines sorties à partir d'aujourd'hui,
 * quel que soit le mois affiché dans le calendrier (requête séparée sur les
 * 30 prochains jours), avec les mêmes filtres que le calendrier.
 */
import { useMemo } from "react";
import { motion } from "framer-motion";
import { CalendarClock, Clock } from "lucide-react";
import { useCalendar, type CalendarEntry } from "@/hooks/use-calendar";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { EntryRow } from "./calendar-entries";
import { UpcomingSkeleton } from "./calendar-skeleton";
import { addDays, entryDate, entryDayKey, entryTime, localDayKey, matchesFilters, type TypeFilter } from "./calendar-utils";

const HORIZON_DAYS = 30;
const MAX_ITEMS = 10;

interface UpcomingPanelProps {
    todayKey: string;
    typeFilter: TypeFilter;
    monitoredOnly: boolean;
    className?: string;
}

function whenLabel(e: CalendarEntry, todayKey: string, tomorrowKey: string): { day: string; time: string | null } {
    const key = entryDayKey(e);
    const time = entryTime(e);
    if (key === todayKey) return { day: "Aujourd'hui", time };
    if (key === tomorrowKey) return { day: "Demain", time };
    const d = entryDate(e);
    return {
        day: d ? d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "") : "",
        time,
    };
}

export function UpcomingPanel({ todayKey, typeFilter, monitoredOnly, className }: UpcomingPanelProps) {
    const range = useMemo(() => {
        const start = new Date();
        return { start: localDayKey(start), end: localDayKey(addDays(start, HORIZON_DAYS)), unmonitored: true };
    }, []);
    const { data, isLoading, isError, error, refetch } = useCalendar(HORIZON_DAYS, range);
    const tomorrowKey = useMemo(() => localDayKey(addDays(new Date(), 1)), []);

    const upcoming = useMemo(
        () =>
            (data?.items ?? [])
                .filter((e) => (entryDayKey(e) ?? "") >= todayKey && matchesFilters(e, typeFilter, monitoredOnly))
                .sort((a, b) => (entryDate(a)?.getTime() ?? 0) - (entryDate(b)?.getTime() ?? 0))
                .slice(0, MAX_ITEMS),
        [data, todayKey, typeFilter, monitoredOnly],
    );

    return (
        <Panel title="Prochaines sorties" icon={Clock} iconClassName="text-sky-300" className={className} bodyClassName="p-2">
            {isLoading ? (
                <UpcomingSkeleton />
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} title="Impossible de charger les prochaines sorties" />
            ) : upcoming.length === 0 ? (
                <EmptyState
                    compact
                    icon={CalendarClock}
                    title="Rien de prévu"
                    description={`Aucune sortie dans les ${HORIZON_DAYS} prochains jours avec ces filtres.`}
                />
            ) : (
                // Liste sur une colonne en panneau latéral, sur 2-3 colonnes sous le calendrier.
                <ol className="grid gap-x-2 sm:grid-cols-2 lg:grid-cols-3 min-[1800px]:grid-cols-1">
                    {upcoming.map((e, i) => {
                        const when = whenLabel(e, todayKey, tomorrowKey);
                        const soon = when.day === "Aujourd'hui";
                        return (
                            <motion.li
                                key={e.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.4, ease: EASE_OUT, delay: i * 0.04 }}
                            >
                                <EntryRow
                                    entry={e}
                                    aside={
                                        <div className="flex flex-col items-end leading-tight">
                                            <span className={cn("text-[11px] font-semibold capitalize", soon ? "text-sky-300" : "text-foreground/80")}>
                                                {when.day}
                                            </span>
                                            {when.time && <span className="text-[11px] text-muted-foreground">{when.time}</span>}
                                        </div>
                                    }
                                />
                            </motion.li>
                        );
                    })}
                </ol>
            )}
        </Panel>
    );
}
