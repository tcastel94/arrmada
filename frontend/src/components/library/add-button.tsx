"use client";

/**
 * Bouton rond « + » posé sur une affiche, avec 3 états animés :
 * idle (+) → adding (spinner) → added (✓ vert + onde).
 * Il stoppe la propagation du clic pour ne pas ouvrir l'aperçu en dessous.
 */
import { AnimatePresence, motion } from "framer-motion";
import { Check, Loader2, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";
import type { AddState } from "./adder";

export function AddButton({
    state,
    onAdd,
    title,
    className,
}: {
    state: AddState;
    onAdd: () => void;
    /** Titre du média (nom accessible du bouton). */
    title: string;
    className?: string;
}) {
    const label = state === "added" ? `« ${title} » ajouté` : state === "adding" ? `Ajout de « ${title} »…` : `Ajouter « ${title} »`;
    return (
        <motion.button
            type="button"
            whileHover={state === "idle" ? { scale: 1.12 } : undefined}
            whileTap={state === "idle" ? { scale: 0.9 } : undefined}
            transition={SPRING}
            onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (state === "idle") onAdd();
            }}
            onKeyDown={(e) => e.stopPropagation()}
            aria-label={label}
            title={label}
            disabled={state !== "idle"}
            className={cn(
                "relative flex h-9 w-9 items-center justify-center rounded-full shadow-lg ring-1 backdrop-blur-md transition-colors duration-300",
                state === "added"
                    ? "bg-success text-white ring-success/50"
                    : "bg-gradient-to-br from-primary to-brand text-primary-foreground ring-white/25 shadow-primary/50",
                className,
            )}
        >
            {state === "added" && (
                <motion.span
                    aria-hidden
                    initial={{ scale: 1, opacity: 0.7 }}
                    animate={{ scale: 2.2, opacity: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="absolute inset-0 rounded-full bg-success"
                />
            )}
            <AnimatePresence mode="popLayout" initial={false}>
                <motion.span
                    key={state}
                    initial={{ scale: 0.3, opacity: 0, rotate: -90 }}
                    animate={{ scale: 1, opacity: 1, rotate: 0 }}
                    exit={{ scale: 0.3, opacity: 0, rotate: 90 }}
                    transition={SPRING}
                    className="relative flex"
                >
                    {state === "adding" ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : state === "added" ? (
                        <Check className="h-4 w-4" strokeWidth={3} />
                    ) : (
                        <Plus className="h-4 w-4" strokeWidth={2.75} />
                    )}
                </motion.span>
            </AnimatePresence>
        </motion.button>
    );
}
