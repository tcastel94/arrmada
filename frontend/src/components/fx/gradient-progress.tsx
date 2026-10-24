"use client";

/**
 * Barre de progression fine, couleur pleine (style iOS).
 * ----------------------------------------------------------------
 * Le nom « Gradient » est historique (ancien thème en dégradé lumineux) ;
 * il est gardé pour ne pas toucher les 16 écrans qui l'utilisent.
 * `active` (téléchargement en cours) ajoute une légère pulsation au lieu
 * des anciennes rayures animées.
 */
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

const TONES = {
    primary: "bg-primary",
    emerald: "bg-success",
    amber: "bg-warning",
    rose: "bg-destructive",
    violet: "bg-[hsl(var(--chart-4))]",
    slate: "bg-muted-foreground",
} as const;

export type ProgressTone = keyof typeof TONES;

export function GradientProgress({
    value,
    tone = "primary",
    active = false,
    className,
}: {
    value: number;
    tone?: ProgressTone;
    /** Élément en cours (pulsation douce). */
    active?: boolean;
    className?: string;
    /** Ancienne option « halo » : ignorée (plus de lueurs). */
    glow?: boolean;
}) {
    const v = Math.max(0, Math.min(100, value || 0));
    return (
        <div className={cn("relative h-1 w-full overflow-hidden rounded-full bg-white/[0.12]", className)}>
            <motion.div
                className={cn("absolute inset-y-0 left-0 rounded-full", TONES[tone], active && "animate-shimmer")}
                initial={{ width: 0 }}
                animate={{ width: `${v}%` }}
                transition={{ duration: 0.6, ease: EASE_OUT }}
            />
        </div>
    );
}
