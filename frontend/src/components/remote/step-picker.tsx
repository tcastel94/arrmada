"use client";

/**
 * Sélecteur de niveau discret (0, 1, 2…) en pastilles, avec indicateur
 * animé qui glisse d'un niveau à l'autre.
 * ----------------------------------------------------------------
 * Pour les réglages Yamaha à quelques crans (rehaussement des voix 0-5,
 * niveau des dialogues 0-3) : plus rapide au doigt qu'un curseur, et la
 * valeur se lit d'un coup d'œil. Sémantique « radiogroup » : flèches
 * gauche/droite pour changer de cran au clavier.
 * `value = null` : valeur inconnue (aucune pastille active).
 */
import type { KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface StepPickerProps {
    value: number | null;
    onChange: (value: number) => void;
    min?: number;
    max: number;
    /** Identifiant UNIQUE par instance (pastille animée `layoutId`). */
    layoutId: string;
    /** Libellé du groupe (ou `ariaLabelledBy` vers un libellé visible). */
    ariaLabel?: string;
    ariaLabelledBy?: string;
    ariaDescribedBy?: string;
    /** Texte d'un cran (par défaut : le chiffre, « Off » pour 0). */
    format?: (value: number) => string;
    disabled?: boolean;
    className?: string;
}

export function StepPicker({
    value,
    onChange,
    min = 0,
    max,
    layoutId,
    ariaLabel,
    ariaLabelledBy,
    ariaDescribedBy,
    format = (v) => (v === 0 ? "Off" : String(v)),
    disabled,
    className,
}: StepPickerProps) {
    const steps = Array.from({ length: max - min + 1 }, (_, i) => min + i);

    // Flèches : cran précédent / suivant, comme un groupe de boutons radio natif.
    const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, current: number) => {
        const delta = e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1 : 0;
        if (!delta) return;
        e.preventDefault();
        const next = Math.max(min, Math.min(max, current + delta));
        if (next === current) return;
        onChange(next);
        const sibling = e.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`[data-step="${next}"]`);
        sibling?.focus();
    };

    return (
        <div
            role="radiogroup"
            aria-label={ariaLabel}
            aria-labelledby={ariaLabelledBy}
            aria-describedby={ariaDescribedBy}
            aria-disabled={disabled || undefined}
            className={cn(
                "inline-flex max-w-full items-center gap-1 rounded-xl border border-white/[0.06] bg-background/40 p-1",
                disabled && "pointer-events-none opacity-50",
                className,
            )}
        >
            {steps.map((s) => {
                const active = s === value;
                // Un seul cran atteignable par Tab (l'actif, ou le premier si inconnu).
                const focusable = value === null ? s === min : active;
                return (
                    <button
                        key={s}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        data-step={s}
                        tabIndex={focusable ? 0 : -1}
                        disabled={disabled}
                        onClick={() => !active && onChange(s)}
                        onKeyDown={(e) => onKeyDown(e, value ?? s)}
                        className={cn(
                            "relative h-8 min-w-[2rem] rounded-lg px-2 text-xs font-semibold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
                            active ? "text-foreground" : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground",
                        )}
                    >
                        {active && (
                            <motion.span
                                layoutId={layoutId}
                                transition={SPRING}
                                className="absolute inset-0 rounded-lg bg-primary/15 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.45),0_0_18px_-6px_hsl(var(--primary)/0.8)]"
                            />
                        )}
                        <span className="relative">{format(s)}</span>
                    </button>
                );
            })}
        </div>
    );
}
