"use client";

/**
 * Barre de progression en dégradé, avec rayures animées tant que
 * l'élément est « actif » (téléchargement en cours, etc.).
 */
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

const TONES = {
    primary: "from-primary via-sky-400 to-brand",
    emerald: "from-emerald-500 to-teal-400",
    amber: "from-amber-500 to-orange-400",
    rose: "from-rose-500 to-pink-400",
    violet: "from-violet-500 to-fuchsia-400",
    slate: "from-slate-500 to-slate-400",
} as const;

export type ProgressTone = keyof typeof TONES;

export function GradientProgress({
    value,
    tone = "primary",
    active = false,
    className,
    glow = true,
}: {
    value: number;
    tone?: ProgressTone;
    /** Rayures animées (élément en cours). */
    active?: boolean;
    className?: string;
    glow?: boolean;
}) {
    const v = Math.max(0, Math.min(100, value || 0));
    return (
        <div className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted/60", className)}>
            <motion.div
                className={cn("absolute inset-y-0 left-0 rounded-full bg-gradient-to-r", TONES[tone])}
                initial={{ width: 0 }}
                animate={{ width: `${v}%` }}
                transition={{ duration: 0.9, ease: EASE_OUT }}
                style={glow ? { boxShadow: "0 0 12px 0 hsl(var(--primary) / 0.55)" } : undefined}
            >
                {active && (
                    <span
                        className="absolute inset-0 animate-progress-stripes opacity-40"
                        style={{
                            backgroundImage:
                                "repeating-linear-gradient(-45deg, rgba(255,255,255,.35) 0 7px, transparent 7px 14px)",
                            backgroundSize: "28px 100%",
                        }}
                    />
                )}
            </motion.div>
        </div>
    );
}
