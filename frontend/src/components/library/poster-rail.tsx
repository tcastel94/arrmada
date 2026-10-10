"use client";

/**
 * Rangée horizontale d'affiches « façon Netflix ».
 * ----------------------------------------------------------------
 * Défilement natif (doigt / trackpad / molette+Maj) aimanté sur chaque
 * affiche (scroll-snap), bords en fondu (mask-fade-x), et flèches ‹ › sur
 * desktop qui avancent d'environ un écran. Les flèches se désactivent
 * d'elles-mêmes en début / fin de rangée.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fadeUp, stagger } from "@/lib/motion";

export function PosterRail({
    title,
    subtitle,
    icon: Icon,
    iconClassName = "text-primary",
    leading,
    action,
    children,
}: {
    title: ReactNode;
    subtitle?: ReactNode;
    icon?: LucideIcon;
    iconClassName?: string;
    /** Élément à gauche du titre à la place de l'icône (ex: mini-affiche). */
    leading?: ReactNode;
    /** Élément à droite (lien « tout voir »…). */
    action?: ReactNode;
    children: ReactNode;
}) {
    const scroller = useRef<HTMLDivElement>(null);
    const [canPrev, setCanPrev] = useState(false);
    const [canNext, setCanNext] = useState(false);

    const update = useCallback(() => {
        const el = scroller.current;
        if (!el) return;
        setCanPrev(el.scrollLeft > 4);
        setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
    }, []);

    // Recalcule à l'affichage et quand la largeur change (rotation, sidebar…).
    useEffect(() => {
        update();
        const el = scroller.current;
        if (!el || typeof ResizeObserver === "undefined") return;
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, [update, children]);

    const scrollByPage = (dir: 1 | -1) => {
        const el = scroller.current;
        if (!el) return;
        el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: "smooth" });
    };

    return (
        <motion.section variants={fadeUp} className="space-y-1">
            <div className="flex items-end justify-between gap-3 px-1">
                <div className="flex min-w-0 items-center gap-3">
                    {leading ??
                        (Icon && (
                            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.04] ring-1 ring-white/[0.08]">
                                <Icon className={cn("h-4 w-4", iconClassName)} />
                            </span>
                        ))}
                    <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold tracking-tight">{title}</h3>
                        {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
                    </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                    {action}
                    <Button
                        variant="outline"
                        size="icon-sm"
                        className="hidden md:inline-flex"
                        onClick={() => scrollByPage(-1)}
                        disabled={!canPrev}
                        aria-label="Faire défiler vers la gauche"
                    >
                        <ChevronLeft />
                    </Button>
                    <Button
                        variant="outline"
                        size="icon-sm"
                        className="hidden md:inline-flex"
                        onClick={() => scrollByPage(1)}
                        disabled={!canNext}
                        aria-label="Faire défiler vers la droite"
                    >
                        <ChevronRight />
                    </Button>
                </div>
            </div>
            {/* py : laisse de la place à l'inclinaison / l'ombre des affiches (overflow coupe sinon). */}
            <motion.div
                ref={scroller}
                onScroll={update}
                variants={stagger(0.05, 0.04)}
                className="mask-fade-x scrollbar-none -mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-px-3 px-3 py-4 sm:gap-4"
            >
                {children}
            </motion.div>
        </motion.section>
    );
}

/** Emplacement d'une affiche dans une rangée (largeur fixe + aimantation). */
export function RailItem({ children }: { children: ReactNode }) {
    return <div className="w-[136px] shrink-0 snap-start sm:w-[156px] lg:w-[172px]">{children}</div>;
}
