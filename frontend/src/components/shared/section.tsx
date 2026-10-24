"use client";

/**
 * Section de page, façon apps Apple : titre gras à gauche, lien bleu
 * « Tout voir › » (ou une action) à droite, contenu dessous, SANS carte
 * autour. À utiliser pour les rangées d'affiches et les listes groupées
 * (qui portent déjà leur propre fond). Pour un contenu à encadrer, voir
 * `Panel` (même en-tête + carte grise).
 */
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Section({
    title,
    subtitle,
    href,
    hrefLabel = "Tout voir",
    action,
    children,
    className,
}: {
    title?: ReactNode;
    /** Petite ligne grise sous le titre. */
    subtitle?: ReactNode;
    href?: string;
    hrefLabel?: string;
    /** Élément à droite (remplace ou complète le lien). */
    action?: ReactNode;
    children: ReactNode;
    className?: string;
}) {
    return (
        <section className={cn("min-w-0", className)}>
            {(title || href || action) && (
                <div className="mb-2.5 flex items-end justify-between gap-3">
                    <div className="min-w-0">
                        {title && <h2 className="truncate text-[20px] font-bold leading-tight tracking-tight">{title}</h2>}
                        {subtitle && <p className="truncate text-[13px] text-muted-foreground">{subtitle}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                        {action}
                        {href && (
                            <Link href={href} className="flex items-center text-[15px] text-primary transition-opacity hover:opacity-80 active:opacity-50">
                                {hrefLabel}
                                <ChevronRight className="h-4 w-4" />
                            </Link>
                        )}
                    </div>
                </div>
            )}
            {children}
        </section>
    );
}
