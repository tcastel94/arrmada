"use client";

/**
 * En-tête de page : « grand titre » iOS.
 * ----------------------------------------------------------------
 * Gros titre gras aligné à gauche, éventuellement une ligne de
 * description grise, les actions de la page (à droite sur ordinateur,
 * sous le titre sur mobile) et une rangée de statistiques en capsules.
 * Quand on fait défiler, ce titre sort de l'écran et la barre du haut
 * reprend le nom de la page en petit (voir Header) : exactement le
 * comportement des apps Apple.
 *
 * Les props `icon`, `accent` et `eyebrow` de l'ancien bandeau « néon »
 * sont toujours acceptées (15 pages les passent) ; `icon` et `accent`
 * ne s'affichent plus : un grand titre iOS n'a pas d'icône.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

/** Ancienne palette de teintes, gardée pour compatibilité des appels. */
export const ACCENTS = {
    primary: {},
    brand: {},
    violet: {},
    emerald: {},
    amber: {},
    rose: {},
    sky: {},
    orange: {},
    fuchsia: {},
    slate: {},
} as const;

export type Accent = keyof typeof ACCENTS;

interface PageHeaderProps {
    /** Ancien pictogramme du bandeau (ignoré). */
    icon?: LucideIcon;
    title: ReactNode;
    description?: ReactNode;
    /** Petit libellé au-dessus du titre (ex : nom de la section). */
    eyebrow?: string;
    /** Ancienne teinte du bandeau (ignorée). */
    accent?: Accent;
    /** Boutons d'action. */
    actions?: ReactNode;
    /** Rangée de statistiques / filtres sous le titre. */
    children?: ReactNode;
    className?: string;
}

export function PageHeader({ title, description, eyebrow, actions, children, className }: PageHeaderProps) {
    return (
        <motion.section
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            className={cn("pt-1", className)}
        >
            {/* Titre et actions sur la même ligne (actions alignées sur le bas du titre) */}
            {/* Les actions passent sous le titre quand la place manque (le
                grand titre n'est jamais tronqué). */}
            <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2 md:gap-x-6">
                <div className="min-w-0 max-w-full">
                    {eyebrow && <p className="mb-0.5 text-[13px] font-semibold text-muted-foreground">{eyebrow}</p>}
                    <h1 className="break-words text-ios-large md:text-[2rem] md:leading-[2.375rem]">{title}</h1>
                </div>
                {actions && <div className="flex flex-wrap items-center gap-1 pb-0.5 md:gap-2">{actions}</div>}
            </div>
            {/* Description : ordinateur seulement (sur mobile, elle repousserait
                le contenu ; le grand titre suffit, comme dans les apps iOS). */}
            {description && <p className="mt-1 hidden max-w-2xl text-[15px] leading-snug text-muted-foreground text-balance md:block">{description}</p>}

            {children && (
                // Mobile : les capsules défilent horizontalement plutôt que de s'empiler
                <div className="scrollbar-none -mx-4 mt-4 flex items-center gap-2 overflow-x-auto px-4 md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
                    {children}
                </div>
            )}
        </motion.section>
    );
}

/** Statistique compacte en capsule grise (sous le grand titre ou ailleurs). */
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
        success: "text-success",
        warning: "text-warning",
        danger: "text-destructive",
    };
    return (
        <div className="flex h-8 shrink-0 items-center gap-1.5 rounded-full bg-white/[0.07] px-3">
            {Icon && <Icon className={cn("h-3.5 w-3.5", tones[tone])} />}
            <span className={cn("text-[13px] font-semibold tabular-nums", tones[tone])}>{value}</span>
            <span className="text-[13px] text-muted-foreground">{label}</span>
        </div>
    );
}
