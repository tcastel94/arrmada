/**
 * Pastille d'état (en ligne, hors ligne, dégradé…).
 * Couleurs système iOS, sans lueur. L'onde animée n'est plus jouée
 * que si on la demande explicitement (`pulse`), pour un écran calme.
 */
import { cn } from "@/lib/utils";

const TONES = {
    online: "bg-success",
    success: "bg-success",
    offline: "bg-destructive",
    error: "bg-destructive",
    degraded: "bg-warning",
    warning: "bg-warning",
    unknown: "bg-muted-foreground",
    primary: "bg-primary",
    brand: "bg-primary",
} as const;

export type StatusTone = keyof typeof TONES;

export function StatusDot({
    tone = "unknown",
    pulse = false,
    className,
    size = "md",
}: {
    tone?: StatusTone | string;
    /** Onde animée (ex : lecture en direct). */
    pulse?: boolean;
    className?: string;
    size?: "sm" | "md" | "lg";
}) {
    const color = TONES[tone as StatusTone] ?? TONES.unknown;
    const dim = size === "sm" ? "h-1.5 w-1.5" : size === "lg" ? "h-2.5 w-2.5" : "h-2 w-2";
    return (
        <span className={cn("relative inline-flex shrink-0", dim, className)}>
            {pulse && <span className={cn("absolute inset-0 animate-pulse-ring rounded-full", color)} />}
            <span className={cn("relative inline-flex rounded-full", dim, color)} />
        </span>
    );
}
