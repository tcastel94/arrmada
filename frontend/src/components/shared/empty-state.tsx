"use client";

/**
 * État vide façon iOS (« Aucun contenu ») : grande icône grise, titre,
 * explication, bouton teinté optionnel.
 * Variante `tone="error"` pour les erreurs API (avec bouton Réessayer).
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Inbox, ServerCrash, type LucideIcon } from "lucide-react";
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

const TONE_ICON = {
    default: "text-muted-foreground/70",
    success: "text-success",
    error: "text-destructive",
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
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            className={cn("flex flex-col items-center justify-center px-6 text-center", compact ? "py-8" : "py-16", className)}
        >
            <Icon className={cn("mb-3", compact ? "h-8 w-8" : "h-12 w-12", TONE_ICON[tone])} strokeWidth={1.5} />
            <h3 className={cn("font-semibold tracking-tight", compact ? "text-[15px]" : "text-[20px]")}>{title}</h3>
            {description && (
                <p className={cn("mt-1 max-w-sm text-muted-foreground text-balance", compact ? "text-[13px]" : "text-[15px]")}>{description}</p>
            )}
            {action &&
                (action.href ? (
                    <Button asChild variant="tinted" className="mt-5" size={compact ? "sm" : "default"}>
                        <Link href={action.href}>{action.label}</Link>
                    </Button>
                ) : (
                    <Button onClick={action.onClick} variant="tinted" className="mt-5" size={compact ? "sm" : "default"}>
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
            icon={ServerCrash}
            title={title}
            description={message}
            compact={compact}
            action={onRetry ? { label: "Réessayer", onClick: onRetry } : undefined}
        />
    );
}
