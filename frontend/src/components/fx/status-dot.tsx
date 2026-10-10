/**
 * Pastille d'état avec onde pulsée (pour les éléments « vivants »).
 */
import { cn } from "@/lib/utils";

const TONES = {
    online: "bg-emerald-400",
    success: "bg-emerald-400",
    offline: "bg-red-500",
    error: "bg-red-500",
    degraded: "bg-amber-400",
    warning: "bg-amber-400",
    unknown: "bg-slate-500",
    primary: "bg-primary",
    brand: "bg-brand",
} as const;

export type StatusTone = keyof typeof TONES;

export function StatusDot({
    tone = "unknown",
    pulse,
    className,
    size = "md",
}: {
    tone?: StatusTone | string;
    /** Onde animée ; par défaut active pour online/primary/brand. */
    pulse?: boolean;
    className?: string;
    size?: "sm" | "md" | "lg";
}) {
    const color = TONES[tone as StatusTone] ?? TONES.unknown;
    const shouldPulse = pulse ?? (tone === "online" || tone === "primary" || tone === "brand");
    const dim = size === "sm" ? "h-1.5 w-1.5" : size === "lg" ? "h-3 w-3" : "h-2 w-2";
    return (
        <span className={cn("relative inline-flex shrink-0", dim, className)}>
            {shouldPulse && <span className={cn("absolute inset-0 rounded-full animate-pulse-ring", color)} />}
            <span
                className={cn("relative inline-flex rounded-full", dim, color)}
                style={{ boxShadow: "0 0 10px 0 currentColor" }}
            />
        </span>
    );
}
