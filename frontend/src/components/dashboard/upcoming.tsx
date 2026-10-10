"use client";

/**
 * Widget « À venir » : les sorties des 7 prochains jours, groupées par
 * jour (Aujourd'hui, Demain, puis jour de la semaine).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { motion } from "framer-motion";
import { CalendarDays, Film, Tv, CheckCircle2 } from "lucide-react";
import { useCalendar, type CalendarEntry } from "@/hooks/use-calendar";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { parseApiDate } from "@/lib/format";
import { stagger, slideIn } from "@/lib/motion";

/** Clé de jour en heure LOCALE (évite le décalage UTC de toISOString). */
function localDayKey(d: Date) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayLabel(d: Date) {
    const today = new Date();
    const tomorrow = new Date();
    tomorrow.setDate(today.getDate() + 1);
    if (localDayKey(d) === localDayKey(today)) return "Aujourd'hui";
    if (localDayKey(d) === localDayKey(tomorrow)) return "Demain";
    return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "short" });
}

/** Les dates « jour seul » (YYYY-MM-DD) sont lues en local, les autres via parseApiDate. */
function entryDate(e: CalendarEntry): Date | null {
    if (/^\d{4}-\d{2}-\d{2}$/.test(e.air_date)) {
        const [y, m, d] = e.air_date.split("-").map(Number);
        return new Date(y, m - 1, d);
    }
    return parseApiDate(e.air_date);
}

export function UpcomingWidget() {
    const { data, isLoading } = useCalendar(14);

    const limit = new Date();
    limit.setDate(limit.getDate() + 7);
    const groups = new Map<string, { date: Date; items: CalendarEntry[] }>();
    for (const e of data?.items ?? []) {
        const d = entryDate(e);
        if (!d || d > limit) continue;
        const key = localDayKey(d);
        if (!groups.has(key)) groups.set(key, { date: d, items: [] });
        groups.get(key)!.items.push(e);
    }
    const days = Array.from(groups.values()).sort((a, b) => a.date.getTime() - b.date.getTime()).slice(0, 5);

    const hrefOf = (e: CalendarEntry & { series_id?: number; movie_id?: number }) =>
        e.type === "movie" && e.movie_id ? `/media/movie/${e.movie_id}` : e.series_id ? `/media/series/${e.series_id}` : "/calendar";

    return (
        <Panel title="À venir cette semaine" icon={CalendarDays} iconClassName="text-sky-300" href="/calendar" hrefLabel="Calendrier">
            {isLoading ? (
                <div className="space-y-3">
                    {[0, 1, 2].map((i) => (
                        <Shimmer key={i} className="h-12" />
                    ))}
                </div>
            ) : days.length === 0 ? (
                <EmptyState compact icon={CalendarDays} title="Semaine calme" description="Aucune sortie prévue dans les 7 jours." />
            ) : (
                <motion.div variants={stagger(0.05, 0.05)} initial="hidden" animate="show" className="space-y-4">
                    {days.map(({ date, items }) => (
                        <div key={localDayKey(date)}>
                            <p className="eyebrow mb-2 capitalize">{dayLabel(date)}</p>
                            <ul className="space-y-1.5">
                                {items.slice(0, 4).map((e) => (
                                    <motion.li key={e.id} variants={slideIn}>
                                        <Link
                                            href={hrefOf(e)}
                                            className="group flex items-center gap-3 rounded-xl p-1.5 transition-colors hover:bg-white/[0.04]"
                                        >
                                            <div className="h-11 w-8 shrink-0 overflow-hidden rounded-md bg-muted ring-1 ring-white/10">
                                                {e.poster_url ? (
                                                    <img src={e.poster_url} alt="" loading="lazy" className="h-full w-full object-cover" />
                                                ) : (
                                                    <div className="flex h-full w-full items-center justify-center">
                                                        {e.type === "movie" ? <Film className="h-3.5 w-3.5 opacity-50" /> : <Tv className="h-3.5 w-3.5 opacity-50" />}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-medium transition-colors group-hover:text-primary">{e.title}</p>
                                                <p className="truncate text-[11px] text-muted-foreground">
                                                    {e.type === "episode" ? e.label : "Film"}
                                                    {e.subtitle ? ` · ${e.subtitle}` : ""}
                                                </p>
                                            </div>
                                            {e.has_file && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" aria-label="Déjà disponible" />}
                                        </Link>
                                    </motion.li>
                                ))}
                                {items.length > 4 && <li className="pl-12 text-[11px] text-muted-foreground">+{items.length - 4} autre(s)</li>}
                            </ul>
                        </div>
                    ))}
                </motion.div>
            )}
        </Panel>
    );
}
