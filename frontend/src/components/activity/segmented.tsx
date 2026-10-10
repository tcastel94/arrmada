"use client";

/**
 * Sélecteur segmenté (« Tous / Succès / Échecs… ») avec indicateur animé.
 * ----------------------------------------------------------------
 * Le fond lumineux de l'option active glisse d'une option à l'autre grâce à
 * `layoutId` (framer-motion) au lieu de clignoter. Utilisé par le Journal,
 * les Notifications, les Téléchargements et le Calendrier (zone « Activité »).
 *
 * Accessibilité : groupe de boutons radio (role="radiogroup" / "radio"),
 * navigation au clavier avec les flèches gauche/droite.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

export interface SegmentOption<T extends string> {
    value: T;
    label: ReactNode;
    icon?: LucideIcon;
    /** Compteur affiché à droite du libellé (masqué si undefined). */
    count?: number;
    /** Couleur de l'icône quand l'option est active (ex: "text-red-400"). */
    tone?: string;
}

interface SegmentedProps<T extends string> {
    value: T;
    onChange: (value: T) => void;
    options: SegmentOption<T>[];
    /** Libellé accessible du groupe (lu par les lecteurs d'écran). */
    ariaLabel: string;
    size?: "sm" | "md";
    className?: string;
}

export function Segmented<T extends string>({
    value,
    onChange,
    options,
    ariaLabel,
    size = "md",
    className,
}: SegmentedProps<T>) {
    // Un layoutId unique par instance : sinon deux sélecteurs sur la même
    // page se « voleraient » l'indicateur.
    const layoutId = `seg-${useId()}`;
    const refs = useRef<Array<HTMLButtonElement | null>>([]);

    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        const i = options.findIndex((o) => o.value === value);
        const next = (i + (e.key === "ArrowRight" ? 1 : -1) + options.length) % options.length;
        onChange(options[next].value);
        refs.current[next]?.focus();
    };

    return (
        <div
            role="radiogroup"
            aria-label={ariaLabel}
            onKeyDown={onKeyDown}
            className={cn(
                "relative inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-xl border border-white/[0.06] bg-background/50 p-1 backdrop-blur scrollbar-none",
                className,
            )}
        >
            {options.map((o, i) => {
                const active = o.value === value;
                const Icon = o.icon;
                return (
                    <button
                        key={o.value}
                        ref={(el) => {
                            refs.current[i] = el;
                        }}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        tabIndex={active ? 0 : -1}
                        onClick={() => onChange(o.value)}
                        className={cn(
                            "relative inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors duration-200",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
                            size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
                            active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                        )}
                    >
                        {active && (
                            <motion.span
                                layoutId={layoutId}
                                transition={SPRING}
                                className="absolute inset-0 rounded-lg bg-primary/15 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.3),0_0_18px_-6px_hsl(var(--primary)/0.7)]"
                            />
                        )}
                        {Icon && <Icon className={cn("relative h-3.5 w-3.5", active && (o.tone ?? "text-primary"))} />}
                        <span className="relative">{o.label}</span>
                        {typeof o.count === "number" && (
                            <span
                                className={cn(
                                    "relative rounded-md px-1.5 text-[10px] tabular-nums leading-4",
                                    active ? "bg-primary/20 text-primary" : "bg-white/[0.05] text-muted-foreground",
                                )}
                            >
                                {o.count > 999 ? "999+" : o.count}
                            </span>
                        )}
                    </button>
                );
            })}
        </div>
    );
}
