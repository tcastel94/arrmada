"use client";

/**
 * Curseur (slider) accessible et stylé, utilisé pour la progression Kodi
 * et les volumes Kodi / Yamaha.
 * ----------------------------------------------------------------
 * Principe : un vrai <input type="range"> natif, invisible mais posé PAR-
 * DESSUS le dessin. On garde ainsi gratuitement le clavier (flèches,
 * Page↑/↓, Début/Fin), le tactile et les lecteurs d'écran, tout en
 * dessinant une piste en dégradé lumineux et une bulle de valeur.
 *
 * - onChange : appelé en continu pendant le glissement (aperçu local).
 * - onCommit : appelé au RELÂCHEMENT (souris, doigt, touche) → c'est là
 *   qu'on envoie la commande réseau (évite de bombarder Kodi/l'ampli).
 */
import { useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

const TONES = {
    violet: { fill: "from-white to-white", glow: "transparent" },
    orange: { fill: "from-warning to-warning", glow: "transparent" },
    primary: { fill: "from-primary to-primary", glow: "transparent" },
} as const;

interface RangeSliderProps {
    value: number;
    min?: number;
    max?: number;
    step?: number;
    onChange?: (value: number) => void;
    onCommit?: (value: number) => void;
    /** Libellé lu par les lecteurs d'écran (obligatoire : pas de texte visible). */
    ariaLabel: string;
    /** Valeur lisible (ex: « 12:04 sur 1:45:00 »). */
    ariaValueText?: string;
    tone?: keyof typeof TONES;
    /** Texte de la bulle affichée pendant le glissement. */
    bubble?: (value: number) => string;
    disabled?: boolean;
    size?: "sm" | "md";
    className?: string;
}

export function RangeSlider({
    value,
    min = 0,
    max = 100,
    step = 1,
    onChange,
    onCommit,
    ariaLabel,
    ariaValueText,
    tone = "primary",
    bubble,
    disabled,
    size = "md",
    className,
}: RangeSliderProps) {
    const [active, setActive] = useState(false);
    const span = max - min || 1;
    const pct = Math.max(0, Math.min(100, ((value - min) / span) * 100));
    const t = TONES[tone];

    const commit = (el: HTMLInputElement) => {
        setActive(false);
        onCommit?.(Number(el.value));
    };

    // Les touches modifient la valeur une à une : on valide au relâchement.
    const onKeyUp = (e: KeyboardEvent<HTMLInputElement>) => {
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(e.key)) {
            commit(e.currentTarget);
        }
    };

    return (
        <div
            className={cn(
                "group relative flex w-full touch-none select-none items-center",
                size === "sm" ? "h-5" : "h-7",
                disabled && "pointer-events-none opacity-40",
                className,
            )}
        >
            {/* Piste */}
            <div className={cn("relative w-full overflow-hidden rounded-full bg-white/10", size === "sm" ? "h-1" : "h-1.5", "transition-[height] group-hover:h-2")}>
                <div
                    className={cn("absolute inset-y-0 left-0 rounded-full bg-gradient-to-r", t.fill)}
                    style={{ width: `${pct}%` }}
                />
            </div>

            {/* Input natif invisible, au-dessus : souris, tactile, clavier, lecteur d'écran */}
            <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={value}
                disabled={disabled}
                aria-label={ariaLabel}
                aria-valuetext={ariaValueText}
                onChange={(e) => {
                    setActive(true);
                    onChange?.(Number(e.target.value));
                }}
                onPointerUp={(e) => commit(e.currentTarget)}
                onKeyUp={onKeyUp}
                className="peer absolute inset-0 z-10 h-full w-full cursor-pointer appearance-none opacity-0"
            />

            {/* Poignée + bulle */}
            <div
                aria-hidden
                className="pointer-events-none absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${pct}%` }}
            >
                <div
                    className={cn(
                        // Contour de focus clavier en `outline` (le halo utilise déjà box-shadow).
                        "rounded-full bg-white outline-offset-2 outline-white transition-transform duration-200 ease-spring group-has-[:focus-visible]:outline group-has-[:focus-visible]:outline-2",
                        size === "sm" ? "h-3 w-3" : "h-4 w-4",
                        active ? "scale-125" : "scale-100 group-hover:scale-110",
                    )}
                />
                {bubble && active && (
                    <div className="glass-strong absolute bottom-full left-1/2 mb-2.5 -translate-x-1/2 whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-semibold tabular-nums">
                        {bubble(value)}
                    </div>
                )}
            </div>
        </div>
    );
}
