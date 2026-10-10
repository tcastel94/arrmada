"use client";

/**
 * Squelette de chargement qui imite la mise en page du hero (affiche à
 * gauche, titre, méta, notes, boutons, onglets) : la page ne « saute »
 * pas quand les données arrivent.
 */
import { Shimmer } from "@/components/shared/loading-skeleton";

export function DetailSkeleton() {
    return (
        <div className="space-y-8" aria-busy="true" aria-label="Chargement de la fiche">
            <div className="grid gap-6 pt-4 md:grid-cols-[220px_minmax(0,1fr)] md:gap-8 md:pt-14 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-10 lg:pt-20">
                <Shimmer className="hidden aspect-[2/3] w-full rounded-2xl md:block" />
                <div className="min-w-0 space-y-5">
                    <div className="flex items-end gap-4">
                        <Shimmer className="aspect-[2/3] w-24 shrink-0 rounded-xl sm:w-28 md:hidden" />
                        <div className="flex-1 space-y-3">
                            <Shimmer className="h-3 w-24 rounded-md" />
                            <Shimmer className="h-10 w-4/5 rounded-lg lg:h-14" />
                            <Shimmer className="h-4 w-1/3 rounded-md" />
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {["w-16", "w-20", "w-14", "w-24", "w-20"].map((w, i) => (
                            <Shimmer key={i} className={`h-6 rounded-full ${w}`} />
                        ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Shimmer className="h-9 w-28" />
                        <Shimmer className="h-9 w-28" />
                        <Shimmer className="h-9 w-36" />
                    </div>
                    <div className="max-w-3xl space-y-2">
                        <Shimmer className="h-3.5 w-full rounded-md" />
                        <Shimmer className="h-3.5 w-11/12 rounded-md" />
                        <Shimmer className="h-3.5 w-3/4 rounded-md" />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Shimmer className="h-11 w-44" />
                        <Shimmer className="h-11 w-36" />
                        <Shimmer className="h-11 w-11" />
                    </div>
                </div>
            </div>
            <Shimmer className="h-10 w-full max-w-xl" />
            <div className="space-y-3">
                <Shimmer className="h-24 w-full rounded-2xl" />
                <Shimmer className="h-24 w-full rounded-2xl" />
                <Shimmer className="h-24 w-full rounded-2xl" />
            </div>
        </div>
    );
}
