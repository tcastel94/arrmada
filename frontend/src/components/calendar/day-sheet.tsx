"use client";

/**
 * Panneau latéral (ou tiroir bas sur mobile) listant toutes les sorties
 * d'un jour — ouvert depuis « +N » ou un clic sur le numéro du jour.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { CalendarEntry } from "@/hooks/use-calendar";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { dayLabel } from "@/components/activity/day-groups";
import { plural } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { EntryRow } from "./calendar-entries";
import { parseDayKey } from "./calendar-utils";
import { useMediaQuery } from "./use-media-query";

interface DaySheetProps {
    /** Jour ouvert (null = panneau fermé). */
    dayKey: string | null;
    byDay: Map<string, CalendarEntry[]>;
    onClose: () => void;
}

export function DaySheet({ dayKey, byDay, onClose }: DaySheetProps) {
    const isMobile = useMediaQuery("(max-width: 639px)");
    // On garde le dernier jour affiché pendant l'animation de fermeture
    // (sinon le panneau se viderait en glissant hors de l'écran).
    const [shownKey, setShownKey] = useState(dayKey);
    useEffect(() => {
        if (dayKey) setShownKey(dayKey);
    }, [dayKey]);
    const entries = shownKey ? byDay.get(shownKey) ?? [] : [];
    const date = shownKey ? parseDayKey(shownKey) : null;
    const full = date
        ? date.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
        : "";
    const episodes = entries.filter((e) => e.type === "episode").length;
    const movies = entries.length - episodes;
    const title = date ? dayLabel(date) : "";
    // Titre relatif (« Aujourd'hui »…) → on rappelle la date complète ;
    // sinon le titre EST déjà la date, on n'affiche que le décompte.
    const isRelative = title === "Aujourd'hui" || title === "Hier" || title === "Demain";
    const counts = [episodes > 0 && plural(episodes, "épisode"), movies > 0 && plural(movies, "film")].filter(Boolean).join(" et ");

    return (
        <Sheet open={!!dayKey} onOpenChange={(o) => !o && onClose()}>
            <SheetContent
                side={isMobile ? "bottom" : "right"}
                className={cn(
                    "flex flex-col gap-4 overflow-hidden p-0",
                    isMobile ? "max-h-[85vh] rounded-t-3xl" : "w-full sm:max-w-md",
                )}
            >
                <SheetHeader className="border-b border-white/[0.06] px-5 pb-4 pt-5 text-left">
                    <p className="eyebrow">Sorties du jour</p>
                    <SheetTitle className="text-xl">{title}</SheetTitle>
                    <SheetDescription className="first-letter:uppercase">
                        {[isRelative ? full : null, counts || "Aucune sortie"].filter(Boolean).join(" · ")}
                    </SheetDescription>
                </SheetHeader>
                <div className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-6">
                    {entries.map((e, i) => (
                        <motion.div
                            key={e.id}
                            initial={{ opacity: 0, x: 16 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.35, ease: EASE_OUT, delay: Math.min(i, 15) * 0.04 }}
                        >
                            <EntryRow entry={e} />
                        </motion.div>
                    ))}
                </div>
            </SheetContent>
        </Sheet>
    );
}
