"use client";

/**
 * Barre d'actions flottante (sélection multiple, recherche groupée…).
 * ----------------------------------------------------------------
 * Fixée en bas de l'écran, centrée sur la zone de contenu (décalée de la
 * largeur de la sidebar via la variable CSS --sb-w posée par le layout) et,
 * sur mobile, AU-DESSUS de la barre de navigation flottante (~88 px).
 * Doit être rendue hors de tout parent animé avec transform/filter (sinon
 * `position: fixed` devient relatif à ce parent).
 */
import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

export function FloatingBar({
    open,
    children,
    className,
    label = "Actions de sélection",
}: {
    open: boolean;
    children: ReactNode;
    className?: string;
    label?: string;
}) {
    return (
        <AnimatePresence>
            {open && (
                <motion.div
                    initial={{ y: 48, opacity: 0, scale: 0.94 }}
                    animate={{ y: 0, opacity: 1, scale: 1 }}
                    exit={{ y: 48, opacity: 0, scale: 0.94 }}
                    transition={SPRING}
                    className="pointer-events-none fixed inset-x-3 bottom-[calc(6.25rem+env(safe-area-inset-bottom))] z-[45] flex justify-center lg:bottom-6 lg:left-[var(--sb-w)] lg:right-5"
                >
                    <div
                        role="toolbar"
                        aria-label={label}
                        className={cn(
                            "glass-strong border-gradient pointer-events-auto flex max-w-full flex-wrap items-center justify-center gap-1.5 rounded-2xl p-2 shadow-[0_24px_70px_-20px_rgba(0,0,0,0.9),0_0_40px_-12px_hsl(var(--primary)/0.45)]",
                            className,
                        )}
                    >
                        {children}
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

/** Compteur « 12 sélectionnés » qui roule à chaque changement. */
export function SelectionCount({ count, label = "sélectionné" }: { count: number; label?: string }) {
    return (
        <span className="flex items-center gap-1.5 rounded-xl bg-primary/10 px-3 py-1.5 text-sm ring-1 ring-primary/25">
            <AnimatePresence mode="popLayout" initial={false}>
                <motion.span
                    key={count}
                    initial={{ y: -10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: 10, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="font-semibold tabular-nums text-primary"
                >
                    {count}
                </motion.span>
            </AnimatePresence>
            <span className="text-muted-foreground">
                {label}
                {count > 1 ? "s" : ""}
            </span>
        </span>
    );
}
