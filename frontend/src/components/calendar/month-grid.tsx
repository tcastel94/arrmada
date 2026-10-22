"use client";

/**
 * Grille « Mois » du calendrier (lundi → dimanche, semaines débordantes).
 * ----------------------------------------------------------------
 * - Case du jour : fond et pastille lumineux bleu ciel.
 * - Jusqu'à 3 sorties par case (pastilles cliquables vers la fiche) ; au-delà,
 *   « +N » ouvre le panneau du jour.
 * - Sur petit écran, 7 colonnes de 50 px ne permettent pas de lire un titre :
 *   les pastilles deviennent des points colorés et toute la case ouvre le
 *   panneau du jour (la vue Agenda reste la vue par défaut sur mobile).
 * - Apparition en vague diagonale à chaque changement de mois.
 */
import { motion } from "framer-motion";
import type { CalendarEntry } from "@/hooks/use-calendar";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { EntryPill, TYPE_TONES } from "./calendar-entries";
import { WEEKDAYS, WEEKDAYS_LONG, localDayKey } from "./calendar-utils";

const MAX_PILLS = 3;

interface MonthGridProps {
    days: Date[];
    month: Date;
    byDay: Map<string, CalendarEntry[]>;
    todayKey: string;
    onOpenDay: (key: string) => void;
    /** -1 = on recule d'un mois, +1 = on avance (sens de l'animation). */
    direction: number;
}

export function MonthGrid({ days, month, byDay, todayKey, onOpenDay, direction }: MonthGridProps) {
    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-background/30">
            {/* En-têtes des jours */}
            <div className="grid grid-cols-7 border-b border-white/[0.06] bg-white/[0.02]">
                {WEEKDAYS.map((d, i) => (
                    <div
                        key={d}
                        className={cn(
                            "py-2 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:text-[11px]",
                            i >= 5 && "text-sky-300/70",
                        )}
                    >
                        <span className="sm:hidden">{d.charAt(0)}</span>
                        <span className="hidden sm:inline">{d}</span>
                    </div>
                ))}
            </div>

            <motion.div
                key={localDayKey(month)}
                initial={{ opacity: 0, x: direction * 28 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, ease: EASE_OUT }}
                className="grid grid-cols-7"
            >
                {days.map((day, i) => {
                    const key = localDayKey(day);
                    const entries = byDay.get(key) ?? [];
                    const inMonth = day.getMonth() === month.getMonth();
                    const isToday = key === todayKey;
                    const isPast = key < todayKey;
                    const col = i % 7;
                    const row = Math.floor(i / 7);
                    const hidden = entries.length - MAX_PILLS;
                    const dayName = `${WEEKDAYS_LONG[col]} ${day.getDate()} ${day.toLocaleDateString("fr-FR", { month: "long" })}`;
                    const a11y = `${dayName} : ${entries.length === 0 ? "aucune sortie" : `${entries.length} sortie${entries.length > 1 ? "s" : ""}`}`;

                    return (
                        <motion.div
                            key={key}
                            initial={{ opacity: 0, scale: 0.96 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.35, ease: EASE_OUT, delay: (row + col) * 0.018 }}
                            className={cn(
                                "group/cell relative flex min-h-[58px] flex-col gap-1 border-b border-r border-white/[0.05] p-1 transition-colors sm:min-h-[124px] sm:p-1.5",
                                col === 6 && "border-r-0",
                                i >= days.length - 7 && "border-b-0",
                                !inMonth && "bg-black/20",
                                inMonth && col >= 5 && !isToday && "bg-white/[0.012]",
                                isToday && "bg-gradient-to-b from-sky-500/[0.14] via-sky-500/[0.05] to-transparent",
                                "hover:bg-white/[0.025]",
                            )}
                        >
                            <div className="flex items-center justify-between">
                                {/* Sur mobile, le ::after du bouton s'étend à toute la case
                                    (motif « stretched link ») : un seul bouton par jour. */}
                                <button
                                    type="button"
                                    onClick={() => onOpenDay(key)}
                                    aria-label={a11y}
                                    disabled={entries.length === 0}
                                    className="group/day rounded-full disabled:cursor-default max-sm:after:absolute max-sm:after:inset-0 max-sm:after:content-['']"
                                >
                                    <span
                                        className={cn(
                                            "relative flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-[11px] font-semibold tabular-nums transition-all sm:text-xs",
                                            entries.length > 0 && !isToday && "group-hover/day:bg-white/10",
                                            !inMonth && "text-muted-foreground/35",
                                            inMonth && isPast && !isToday && "text-muted-foreground/70",
                                            isToday && "bg-sky-400 text-slate-950",
                                        )}
                                    >
                                        {day.getDate()}
                                        {isToday && <span aria-hidden className="absolute inset-0 -z-10 animate-pulse-ring rounded-full bg-sky-400/50" />}
                                    </span>
                                </button>
                                {entries.length > 0 && (
                                    <span
                                        className={cn(
                                            "hidden rounded-md px-1 text-[10px] font-semibold tabular-nums sm:inline",
                                            isToday ? "bg-sky-400/20 text-sky-200" : "text-muted-foreground/60",
                                        )}
                                    >
                                        {entries.length}
                                    </span>
                                )}
                            </div>

                            {/* Desktop : pastilles lisibles */}
                            <div className={cn("hidden min-w-0 flex-col gap-1 sm:flex", !inMonth && "opacity-50")}>
                                {entries.slice(0, MAX_PILLS).map((e) => (
                                    <EntryPill key={e.id} entry={e} past={isPast && !isToday} />
                                ))}
                                {hidden > 0 && (
                                    <button
                                        type="button"
                                        onClick={() => onOpenDay(key)}
                                        className="rounded-md px-1.5 py-0.5 text-left text-[10px] font-semibold text-sky-300/90 transition-colors hover:bg-sky-500/10 hover:text-sky-200"
                                    >
                                        +{hidden} autre{hidden > 1 ? "s" : ""}
                                    </button>
                                )}
                            </div>

                            {/* Mobile : points colorés */}
                            {entries.length > 0 && (
                                <div className={cn("mt-auto flex flex-wrap justify-center gap-0.5 pb-0.5 sm:hidden", !inMonth && "opacity-50")}>
                                    {entries.slice(0, 4).map((e) => (
                                        <span
                                            key={e.id}
                                            className={cn("h-1.5 w-1.5 rounded-full", e.has_file ? "bg-emerald-400" : TYPE_TONES[e.type]?.dot ?? "bg-sky-400")}
                                        />
                                    ))}
                                    {entries.length > 4 && <span className="text-[8px] leading-[6px] text-muted-foreground">+</span>}
                                </div>
                            )}
                        </motion.div>
                    );
                })}
            </motion.div>
        </div>
    );
}
