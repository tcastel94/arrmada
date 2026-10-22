"use client";

/**
 * Vue « Agenda » : liste des sorties du mois, jour par jour.
 * ----------------------------------------------------------------
 * Vue par défaut sur mobile (une grille de 7 colonnes est illisible à
 * 390 px). Pour le mois en cours, les jours déjà passés sont repliés
 * derrière un bouton : on arrive directement sur « Aujourd'hui ».
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { CalendarX2, History } from "lucide-react";
import type { CalendarEntry } from "@/hooks/use-calendar";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { dayLabel } from "@/components/activity/day-groups";
import { plural } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { EntryRow } from "./calendar-entries";
import { parseDayKey } from "./calendar-utils";

interface AgendaViewProps {
    /** Jours du mois affiché qui ont au moins une sortie, triés. */
    days: Array<[string, CalendarEntry[]]>;
    todayKey: string;
    /** Le mois affiché contient-il aujourd'hui ? */
    isCurrentMonth: boolean;
    onNextMonth: () => void;
}

export function AgendaView({ days, todayKey, isCurrentMonth, onNextMonth }: AgendaViewProps) {
    const [showPast, setShowPast] = useState(false);

    if (days.length === 0) {
        return (
            <EmptyState
                icon={CalendarX2}
                title="Aucune sortie ce mois-ci"
                description="Rien de prévu avec les filtres actuels. Essaie le mois suivant ou affiche aussi les éléments non surveillés."
                action={{ label: "Mois suivant", onClick: onNextMonth }}
            />
        );
    }

    const past = isCurrentMonth ? days.filter(([key]) => key < todayKey) : [];
    const visible = isCurrentMonth && !showPast ? days.filter(([key]) => key >= todayKey) : days;
    const pastCount = past.reduce((n, [, list]) => n + list.length, 0);

    return (
        <div className="space-y-4">
            {past.length > 0 && !showPast && (
                <Button variant="ghost" size="sm" onClick={() => setShowPast(true)} className="w-full text-muted-foreground">
                    <History /> Voir les sorties déjà passées ce mois-ci ({pastCount})
                </Button>
            )}
            {visible.length === 0 && (
                <EmptyState
                    compact
                    icon={CalendarX2}
                    title="Plus rien d'ici la fin du mois"
                    action={{ label: "Mois suivant", onClick: onNextMonth }}
                />
            )}
            {visible.map(([key, entries], i) => {
                const date = parseDayKey(key);
                const isToday = key === todayKey;
                const isPast = key < todayKey;
                return (
                    <motion.section
                        key={key}
                        aria-label={dayLabel(date)}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, ease: EASE_OUT, delay: Math.min(i, 12) * 0.04 }}
                        className={cn("flex gap-3 sm:gap-4", isPast && "opacity-70")}
                    >
                        {/* Pavé date */}
                        <div
                            className={cn(
                                "flex h-14 w-12 shrink-0 flex-col items-center justify-center rounded-xl ring-1 sm:h-16 sm:w-14",
                                isToday
                                    ? "bg-gradient-to-b from-sky-400/30 to-sky-500/10 text-sky-100 ring-sky-400/50"
                                    : "bg-white/[0.03] ring-white/[0.07]",
                            )}
                        >
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                {date.toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "")}
                            </span>
                            <span className="text-lg font-bold leading-none tabular-nums sm:text-xl">{date.getDate()}</span>
                        </div>

                        <div className="min-w-0 flex-1">
                            <div className="mb-1 flex items-baseline gap-2 px-2">
                                <h3 className={cn("text-sm font-semibold", isToday && "text-sky-200")}>{dayLabel(date)}</h3>
                                <span className="text-[11px] text-muted-foreground">{plural(entries.length, "sortie")}</span>
                            </div>
                            <div className="space-y-0.5 border-l border-white/[0.06] pl-1">
                                {entries.map((e) => (
                                    <EntryRow key={e.id} entry={e} />
                                ))}
                            </div>
                        </div>
                    </motion.section>
                );
            })}
        </div>
    );
}
