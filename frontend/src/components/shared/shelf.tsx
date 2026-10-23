"use client";

/**
 * Rangée horizontale défilante (« étagère » d'affiches, de cartes…).
 * ----------------------------------------------------------------
 * - Mobile : la rangée déborde jusqu'aux bords de l'écran (comme l'App
 *   Store / l'app TV) et s'arrête « à cran » sur chaque élément.
 * - Ordinateur : flèches ‹ › qui apparaissent au survol de la rangée et
 *   font défiler d'une largeur d'écran.
 * Les enfants doivent avoir une largeur fixe (ex : w-[120px] shrink-0).
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function Shelf({ children, className, gap = "gap-3" }: { children: ReactNode; className?: string; gap?: string }) {
    const ref = useRef<HTMLDivElement>(null);
    const [edges, setEdges] = useState({ start: true, end: false });

    // Masque la flèche du côté où l'on ne peut plus défiler.
    const update = useCallback(() => {
        const el = ref.current;
        if (!el) return;
        setEdges({ start: el.scrollLeft <= 4, end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 4 });
    }, []);

    useEffect(() => {
        update();
        const el = ref.current;
        if (!el) return;
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, [update, children]);

    const scroll = (dir: 1 | -1) => ref.current?.scrollBy({ left: dir * ref.current.clientWidth * 0.85, behavior: "smooth" });

    return (
        <div className={cn("group/shelf relative", className)}>
            <div
                ref={ref}
                onScroll={update}
                className={cn(
                    "scrollbar-none snap-row -mx-4 flex overflow-x-auto px-4 pb-1 md:-mx-6 md:px-6 lg:mx-0 lg:px-0",
                    gap,
                )}
            >
                {children}
            </div>
            <ShelfArrow side="left" hidden={edges.start} onClick={() => scroll(-1)} />
            <ShelfArrow side="right" hidden={edges.end} onClick={() => scroll(1)} />
        </div>
    );
}

function ShelfArrow({ side, hidden, onClick }: { side: "left" | "right"; hidden: boolean; onClick: () => void }) {
    const Icon = side === "left" ? ChevronLeft : ChevronRight;
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={side === "left" ? "Défiler vers la gauche" : "Défiler vers la droite"}
            tabIndex={-1}
            className={cn(
                "absolute top-[calc(50%-1.5rem)] z-10 hidden h-9 w-9 items-center justify-center rounded-full bg-[hsl(240_3%_18%/0.92)] text-foreground shadow-lg backdrop-blur transition-opacity duration-200 hover:bg-[hsl(240_3%_24%)] lg:flex",
                side === "left" ? "-left-3" : "-right-3",
                hidden ? "pointer-events-none opacity-0" : "opacity-0 group-hover/shelf:opacity-100",
            )}
        >
            <Icon className="h-5 w-5" />
        </button>
    );
}
