"use client";

// Rôle : bouton rond ou étiqueté de la télécommande tactile.

import { cn } from "@/lib/utils";
import { u } from "../_lib/units";

/**
 * Bouton de la télécommande. [round] : icône seule dans un rond (le texte
 * devient l'étiquette d'accessibilité), avec une petite [caption] dessous
 * (« 10 », « 30 ») pour les sauts.
 */
export function RemoteButton({
    label,
    caption,
    round,
    primary,
    accent,
    onClick,
    children,
}: {
    label: string;
    caption?: string;
    round?: boolean;
    primary?: boolean;
    accent?: boolean;
    onClick: () => void;
    children: React.ReactNode;
}) {
    if (round) {
        return (
            <button
                type="button"
                onClick={onClick}
                aria-label={label}
                title={label}
                className={cn(
                    "flex shrink-0 flex-col items-center justify-center rounded-full transition-colors active:scale-95",
                    primary ? "bg-[#4A9EFF] text-[#0b1220] hover:bg-[#6cb1ff]" : "bg-white/[0.07] text-slate-200 hover:bg-white/[0.12]",
                )}
                style={{ width: u(primary ? 9.5 : 8), height: u(primary ? 9.5 : 8) }}
            >
                {children}
                {caption && (
                    <span className="font-semibold leading-none tabular-nums" style={{ fontSize: u(1.9), marginTop: u(0.3) }}>
                        {caption}
                    </span>
                )}
            </button>
        );
    }
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "flex shrink-0 items-center rounded-full font-medium transition-colors active:scale-95",
                primary
                    ? "bg-[#4A9EFF] text-[#0b1220] hover:bg-[#6cb1ff]"
                    : accent
                      ? "bg-[#4A9EFF]/15 text-[#8CC4FF] ring-1 ring-[#4A9EFF]/40 hover:bg-[#4A9EFF]/25"
                      : "bg-white/[0.07] text-slate-200 hover:bg-white/[0.12]",
            )}
            style={{ height: u(8.5), padding: `0 ${u(2.6)}`, gap: u(1.1), fontSize: u(3) }}
        >
            {children}
            <span>{label}</span>
        </button>
    );
}
