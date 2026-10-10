"use client";

/**
 * En-tête « héros » standard de chaque page.
 * ----------------------------------------------------------------
 * Avant : chaque page dessinait son propre bandeau (couleurs, tailles,
 * largeurs différentes). Ce composant unifie : tuile d'icône lumineuse,
 * titre, description, zone d'actions à droite et rangée de statistiques.
 * Seule la teinte (`accent`) varie d'une page à l'autre.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

export const ACCENTS = {
    primary: { tile: "from-primary/30 to-brand/10 text-primary", orb: "hsl(var(--primary))", ring: "ring-primary/30" },
    brand: { tile: "from-brand/30 to-primary/10 text-brand", orb: "hsl(var(--brand))", ring: "ring-brand/30" },
    violet: { tile: "from-violet-500/30 to-fuchsia-500/10 text-violet-300", orb: "hsl(262 83% 65%)", ring: "ring-violet-400/30" },
    emerald: { tile: "from-emerald-500/30 to-teal-500/10 text-emerald-300", orb: "hsl(152 69% 47%)", ring: "ring-emerald-400/30" },
    amber: { tile: "from-amber-500/30 to-orange-500/10 text-amber-300", orb: "hsl(38 95% 58%)", ring: "ring-amber-400/30" },
    rose: { tile: "from-rose-500/30 to-pink-500/10 text-rose-300", orb: "hsl(350 89% 64%)", ring: "ring-rose-400/30" },
    sky: { tile: "from-sky-500/30 to-cyan-500/10 text-sky-300", orb: "hsl(199 89% 60%)", ring: "ring-sky-400/30" },
    orange: { tile: "from-orange-500/30 to-red-500/10 text-orange-300", orb: "hsl(24 95% 58%)", ring: "ring-orange-400/30" },
    fuchsia: { tile: "from-fuchsia-500/30 to-pink-500/10 text-fuchsia-300", orb: "hsl(292 84% 65%)", ring: "ring-fuchsia-400/30" },
    slate: { tile: "from-slate-400/25 to-slate-500/10 text-slate-200", orb: "hsl(215 20% 60%)", ring: "ring-slate-400/30" },
} as const;

export type Accent = keyof typeof ACCENTS;

interface PageHeaderProps {
    icon: LucideIcon;
    title: ReactNode;
    description?: ReactNode;
    /** Petit libellé au-dessus du titre (ex: nom du groupe de menu). */
    eyebrow?: string;
    accent?: Accent;
    /** Boutons d'action à droite. */
    actions?: ReactNode;
    /** Rangée de statistiques / chips sous le titre. */
    children?: ReactNode;
    className?: string;
}

export function PageHeader({
    icon: Icon,
    title,
    description,
    eyebrow,
    accent = "primary",
    actions,
    children,
    className,
}: PageHeaderProps) {
    const a = ACCENTS[accent];
    return (
        <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT }}
            className={cn("glass border-gradient relative overflow-hidden rounded-3xl p-5 md:p-7", className)}
        >
            {/* Halo coloré + grille décorative */}
            <div
                aria-hidden
                className="pointer-events-none absolute -right-24 -top-28 h-72 w-72 rounded-full opacity-40 animate-pulse-glow"
                style={{ background: `radial-gradient(closest-side, ${a.orb}, transparent)` }}
            />
            <div
                aria-hidden
                className="pointer-events-none absolute -bottom-32 left-1/4 h-56 w-96 rounded-full opacity-20"
                style={{ background: `radial-gradient(closest-side, ${a.orb}, transparent)` }}
            />
            <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid opacity-40 [mask-image:linear-gradient(110deg,transparent_35%,#000)]" />

            <div className="relative flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <div className="flex min-w-0 items-start gap-4">
                    <motion.div
                        initial={{ scale: 0.6, rotate: -12, opacity: 0 }}
                        animate={{ scale: 1, rotate: 0, opacity: 1 }}
                        transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}
                        className={cn(
                            "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ring-1 md:h-14 md:w-14",
                            a.tile,
                            a.ring,
                        )}
                        style={{ boxShadow: `0 0 32px -6px ${a.orb}` }}
                    >
                        <Icon className="h-6 w-6 md:h-7 md:w-7" strokeWidth={1.75} />
                    </motion.div>
                    <div className="min-w-0">
                        {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
                        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
                        {description && (
                            <p className="mt-1 max-w-2xl text-sm text-muted-foreground text-balance">{description}</p>
                        )}
                    </div>
                </div>
                {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
            </div>

            {children && <div className="relative mt-5 flex flex-wrap items-center gap-2">{children}</div>}
        </motion.section>
    );
}

/** Statistique compacte à placer dans le PageHeader (ou ailleurs). */
export function StatPill({
    label,
    value,
    icon: Icon,
    tone = "default",
}: {
    label: string;
    value: ReactNode;
    icon?: LucideIcon;
    tone?: "default" | "primary" | "success" | "warning" | "danger";
}) {
    const tones = {
        default: "text-foreground",
        primary: "text-primary",
        success: "text-emerald-400",
        warning: "text-amber-400",
        danger: "text-red-400",
    };
    return (
        <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-background/40 px-3 py-1.5 backdrop-blur">
            {Icon && <Icon className={cn("h-3.5 w-3.5", tones[tone])} />}
            <span className={cn("text-sm font-semibold tabular-nums", tones[tone])}>{value}</span>
            <span className="text-xs text-muted-foreground">{label}</span>
        </div>
    );
}
