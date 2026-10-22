"use client";

/**
 * Sélecteur segmenté (« chips ») avec indicateur animé.
 * ----------------------------------------------------------------
 * Utilisé pour les sous-catégories (Nettoyage, Doublons) et les filtres
 * (Indexers, Docker). La pastille active glisse d'une option à l'autre
 * grâce à `layoutId` (framer-motion anime le déplacement tout seul).
 * Défile horizontalement sur mobile au lieu de déborder de la page.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

export interface SegmentOption<T extends string> {
    value: T;
    label: string;
    icon?: LucideIcon;
    /** Classe Tailwind de couleur de l'icône (ex: "text-amber-400"). */
    iconClassName?: string;
    /** Compteur affiché à droite du libellé. */
    count?: number;
    /** Info-bulle native (explication de la catégorie). */
    hint?: string;
}

interface SegmentedProps<T extends string> {
    value: T;
    onChange: (value: T) => void;
    options: SegmentOption<T>[];
    /** Identifiant UNIQUE par instance (sinon les pastilles de deux sélecteurs se mélangent). */
    layoutId: string;
    className?: string;
    /** Libellé accessible du groupe. */
    ariaLabel?: string;
    size?: "sm" | "md";
}

export function Segmented<T extends string>({
    value,
    onChange,
    options,
    layoutId,
    className,
    ariaLabel,
    size = "md",
}: SegmentedProps<T>) {
    return (
        <div
            role="tablist"
            aria-label={ariaLabel}
            className={cn(
                "scrollbar-none inline-flex max-w-full items-center gap-1 overflow-x-auto rounded-2xl border border-white/[0.06] bg-background/40 p-1 backdrop-blur",
                className,
            )}
        >
            {options.map((opt) => {
                const active = opt.value === value;
                const Icon = opt.icon;
                return (
                    <button
                        key={opt.value}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        title={opt.hint}
                        onClick={() => onChange(opt.value)}
                        className={cn(
                            "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
                            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
                            active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                        )}
                    >
                        {active && (
                            <motion.span
                                layoutId={layoutId}
                                transition={SPRING}
                                className="absolute inset-0 rounded-xl bg-white/[0.08]"
                            />
                        )}
                        {Icon && <Icon className={cn("relative h-3.5 w-3.5", opt.iconClassName)} />}
                        <span className="relative">{opt.label}</span>
                        {opt.count !== undefined && (
                            <span
                                className={cn(
                                    "relative min-w-[1.25rem] rounded-md px-1 text-center text-[10px] font-semibold tabular-nums",
                                    active ? "bg-primary/20 text-primary" : "bg-white/[0.06] text-muted-foreground",
                                )}
                            >
                                {opt.count.toLocaleString("fr-FR")}
                            </span>
                        )}
                    </button>
                );
            })}
        </div>
    );
}
