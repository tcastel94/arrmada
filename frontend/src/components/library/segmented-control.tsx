"use client";

/**
 * Sélecteur segmenté iOS (« segmented control ») avec pastille animée.
 * ----------------------------------------------------------------
 * La pilule de fond glisse d'une option à l'autre grâce à `layoutId`
 * (framer-motion interpole position et taille). Chaque instance doit avoir
 * son propre `layoutId`, sinon deux sélecteurs de la page se « volent »
 * la pilule.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

export interface SegmentOption<T extends string> {
    value: T;
    label: ReactNode;
    icon?: LucideIcon;
    /** Petit compteur à droite du libellé. */
    count?: number | null;
    /** Infobulle (et nom accessible quand le libellé est masqué). */
    title?: string;
}

interface SegmentedControlProps<T extends string> {
    value: T;
    onChange: (value: T) => void;
    options: SegmentOption<T>[];
    layoutId: string;
    size?: "sm" | "md" | "lg";
    /** "tablist" pour des onglets, "radiogroup" pour un choix de filtre/vue. */
    role?: "tablist" | "radiogroup";
    ariaLabel?: string;
    /** Sur mobile, n'affiche que l'icône (gain de place dans les barres d'outils). */
    iconOnlyOnMobile?: boolean;
    className?: string;
}

const SIZES = {
    sm: "h-[26px] px-2.5 text-[12px]",
    md: "h-[30px] px-3 text-[13px]",
    lg: "h-9 px-4 text-[14px]",
};

export function SegmentedControl<T extends string>({
    value,
    onChange,
    options,
    layoutId,
    size = "md",
    role = "radiogroup",
    ariaLabel,
    iconOnlyOnMobile = false,
    className,
}: SegmentedControlProps<T>) {
    return (
        <div
            role={role}
            aria-label={ariaLabel}
            className={cn(
                "relative inline-flex max-w-full shrink-0 items-center gap-0.5 rounded-[9px] bg-white/[0.09] p-[2px]",
                className,
            )}
        >
            {options.map((option) => {
                const active = option.value === value;
                const Icon = option.icon;
                return (
                    <button
                        key={option.value}
                        type="button"
                        role={role === "tablist" ? "tab" : "radio"}
                        aria-selected={role === "tablist" ? active : undefined}
                        aria-checked={role === "radiogroup" ? active : undefined}
                        aria-label={iconOnlyOnMobile && option.title ? option.title : undefined}
                        title={option.title}
                        onClick={() => onChange(option.value)}
                        className={cn(
                            "relative inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-[7px] font-medium outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-primary/60",
                            SIZES[size],
                            active ? "font-semibold text-white" : "text-foreground/75 hover:text-foreground",
                        )}
                    >
                        {active && (
                            <motion.span
                                layoutId={layoutId}
                                transition={SPRING}
                                aria-hidden
                                className="absolute inset-0 rounded-[7px] bg-[#636366] shadow-[0_3px_8px_rgb(0_0_0/0.25)]"
                            />
                        )}
                        <span className="relative z-[1] inline-flex items-center gap-1.5">
                            {Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}
                            <span className={cn(iconOnlyOnMobile && Icon && "hidden sm:inline")}>{option.label}</span>
                            {typeof option.count === "number" && (
                                <span
                                    className={cn(
                                        "rounded-full px-1.5 text-[10px] font-semibold tabular-nums",
                                        active ? "bg-white/20 text-white" : "bg-white/[0.08] text-muted-foreground",
                                    )}
                                >
                                    {option.count}
                                </span>
                            )}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}
