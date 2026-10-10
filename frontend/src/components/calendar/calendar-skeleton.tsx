"use client";

/**
 * Squelettes calqués sur les vraies vues du calendrier (grille du mois ou
 * liste agenda) — plutôt que le PageSkeleton générique.
 */
import { Shimmer } from "@/components/shared/loading-skeleton";
import { WEEKDAYS } from "./calendar-utils";

export function MonthGridSkeleton() {
    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.06]" aria-busy aria-label="Chargement du calendrier">
            <div className="grid grid-cols-7 border-b border-white/[0.06]">
                {WEEKDAYS.map((d) => (
                    <div key={d} className="py-2 text-center text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/40">
                        {d}
                    </div>
                ))}
            </div>
            <div className="grid grid-cols-7">
                {Array.from({ length: 35 }).map((_, i) => (
                    <div key={i} className="min-h-[58px] space-y-1.5 border-b border-r border-white/[0.04] p-1.5 sm:min-h-[124px]">
                        <Shimmer className="h-5 w-5 rounded-full" />
                        {/* Quelques fausses pastilles, réparties de façon irrégulière */}
                        {i % 3 === 0 && <Shimmer className="hidden h-4 w-full rounded-md sm:block" />}
                        {i % 5 === 1 && <Shimmer className="hidden h-4 w-4/5 rounded-md sm:block" />}
                    </div>
                ))}
            </div>
        </div>
    );
}

export function AgendaSkeleton() {
    return (
        <div className="space-y-5" aria-busy aria-label="Chargement de l'agenda">
            {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex gap-3">
                    <Shimmer className="h-14 w-12 rounded-xl" />
                    <div className="flex-1 space-y-2">
                        <Shimmer className="h-3.5 w-32 rounded-md" />
                        {Array.from({ length: (i % 2) + 1 }).map((__, j) => (
                            <div key={j} className="flex items-center gap-3 p-2">
                                <Shimmer className="h-[60px] w-10 rounded-lg" />
                                <div className="flex-1 space-y-2">
                                    <Shimmer className="h-3.5 w-2/3 rounded-md" />
                                    <Shimmer className="h-3 w-1/3 rounded-md" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

export function UpcomingSkeleton() {
    return (
        <div className="space-y-1">
            {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-2">
                    <Shimmer className="h-[60px] w-10 rounded-lg" />
                    <div className="flex-1 space-y-2">
                        <Shimmer className="h-3.5 w-3/4 rounded-md" />
                        <Shimmer className="h-3 w-1/2 rounded-md" />
                    </div>
                </div>
            ))}
        </div>
    );
}
