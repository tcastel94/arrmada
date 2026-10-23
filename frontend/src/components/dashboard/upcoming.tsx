"use client";

/**
 * Section « À venir » de l'Accueil : les prochaines sorties (7 jours) en
 * liste groupée iOS, une ligne par titre avec sa vignette, le jour
 * (« Aujourd'hui », « Demain », « jeudi 24 »…) et une coche verte s'il
 * est déjà disponible.
 */
/* eslint-disable @next/next/no-img-element */
import { CalendarDays, CheckCircle2, Film, Tv } from "lucide-react";
import { useCalendar, type CalendarEntry } from "@/hooks/use-calendar";
import { Section } from "@/components/shared/section";
import { GroupedList, ListRow } from "@/components/shared/grouped-list";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { parseApiDate } from "@/lib/format";

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
    return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric" });
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

    const items = (data?.items ?? [])
        .map((e) => ({ e, d: entryDate(e) }))
        .filter((x): x is { e: CalendarEntry; d: Date } => !!x.d && x.d <= limit)
        .sort((a, b) => a.d.getTime() - b.d.getTime())
        .slice(0, 6);

    const hrefOf = (e: CalendarEntry) =>
        e.type === "movie" && e.movie_id ? `/media/movie/${e.movie_id}` : e.series_id ? `/media/series/${e.series_id}` : "/calendar";

    return (
        <Section title="À venir" href="/calendar" hrefLabel="Calendrier">
            {isLoading ? (
                <Shimmer className="h-[220px] rounded-xl" />
            ) : items.length === 0 ? (
                <div className="rounded-xl bg-card">
                    <EmptyState compact icon={CalendarDays} title="Semaine calme" description="Aucune sortie prévue dans les 7 jours." />
                </div>
            ) : (
                <GroupedList>
                    {items.map(({ e, d }) => (
                        <ListRow
                            key={e.id}
                            href={hrefOf(e)}
                            chevron={false}
                            leading={
                                <span className="my-2 h-[54px] w-9 shrink-0 overflow-hidden rounded-[6px] bg-white/[0.06]">
                                    {e.poster_url ? (
                                        <img src={e.poster_url} alt="" loading="lazy" className="h-full w-full object-cover" />
                                    ) : (
                                        <span className="flex h-full items-center justify-center">
                                            {e.type === "movie" ? <Film className="h-4 w-4 text-white/25" /> : <Tv className="h-4 w-4 text-white/25" />}
                                        </span>
                                    )}
                                </span>
                            }
                            title={e.title}
                            subtitle={[e.type === "episode" ? e.label : "Film", e.subtitle].filter(Boolean).join(" · ")}
                            detail={<span className="capitalize">{dayLabel(d)}</span>}
                            accessory={e.has_file ? <CheckCircle2 className="h-[18px] w-[18px] text-success" aria-label="Déjà disponible" /> : undefined}
                        />
                    ))}
                </GroupedList>
            )}
        </Section>
    );
}
