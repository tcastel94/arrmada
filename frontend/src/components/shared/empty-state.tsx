"use client";

/**
 * État vide animé (icône flottante dans un halo) + action optionnelle.
 * Variante `tone="error"` pour les erreurs API (avec bouton Réessayer).
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Inbox, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

interface EmptyStateProps {
    icon?: LucideIcon;
    title: string;
    description?: string;
    action?: {
        label: string;
        onClick?: () => void;
        href?: string;
    };
    tone?: "default" | "success" | "error";
    className?: string;
    compact?: boolean;
}

const TONE_STYLES = {
    default: { tile: "from-primary/25 to-brand/5 text-primary ring-primary/25", glow: "hsl(var(--primary) / 0.45)" },
    success: { tile: "from-emerald-500/25 to-teal-500/5 text-emerald-300 ring-emerald-400/25", glow: "hsl(152 69% 47% / 0.45)" },
    error: { tile: "from-red-500/25 to-orange-500/5 text-red-300 ring-red-400/25", glow: "hsl(0 84% 62% / 0.45)" },
};

export function EmptyState({
    icon: Icon = Inbox,
    title,
    description,
    action,
    tone = "default",
    className,
    compact = false,
}: EmptyStateProps) {
    const t = TONE_STYLES[tone];
    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
            className={cn(
                "flex flex-col items-center justify-center text-center",
                compact ? "py-8" : "py-14",
                className,
            )}
        >
            <div className="relative mb-5">
                <div
                    aria-hidden
                    className="absolute inset-0 -m-6 rounded-full opacity-70 blur-2xl"
                    style={{ background: `radial-gradient(closest-side, ${t.glow}, transparent)` }}
                />
                <div
                    className={cn(
                        "relative flex animate-float items-center justify-center rounded-2xl bg-gradient-to-br ring-1",
                        compact ? "h-12 w-12" : "h-16 w-16",
                        t.tile,
                    )}
                >
                    <Icon className={compact ? "h-6 w-6" : "h-8 w-8"} strokeWidth={1.6} />
                </div>
            </div>
            <h3 className={cn("font-semibold tracking-tight", compact ? "text-sm" : "text-lg")}>{title}</h3>
            {description && (
                <p className={cn("mt-1.5 max-w-sm text-muted-foreground text-balance", compact ? "text-xs" : "text-sm")}>
                    {description}
                </p>
            )}
            {action &&
                (action.href ? (
                    <Button asChild className="mt-5" size={compact ? "sm" : "default"}>
                        <Link href={action.href}>{action.label}</Link>
                    </Button>
                ) : (
                    <Button onClick={action.onClick} className="mt-5" size={compact ? "sm" : "default"}>
                        {action.label}
                    </Button>
                ))}
        </motion.div>
    );
}

/** Raccourci pour les erreurs de chargement : message + bouton Réessayer. */
export function ErrorState({
    error,
    onRetry,
    title = "Impossible de charger les données",
    compact,
}: {
    error?: unknown;
    onRetry?: () => void;
    title?: string;
    compact?: boolean;
}) {
    const message = error instanceof Error ? error.message : typeof error === "string" ? error : "Le service ne répond pas.";
    return (
        <EmptyState
            tone="error"
            title={title}
            description={message}
            compact={compact}
            action={onRetry ? { label: "Réessayer", onClick: onRetry } : undefined}
        />
    );
}
