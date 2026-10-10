"use client";

/**
 * Panneau de contenu standard (carte en verre + en-tête optionnel).
 * Remplace les dizaines de variantes `Card border-0 ring-1 ring-white/5…`.
 */
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { SpotlightCard } from "@/components/fx/spotlight-card";

interface PanelProps {
    title?: ReactNode;
    icon?: LucideIcon;
    /** Couleur Tailwind de l'icône (ex: "text-amber-400"). */
    iconClassName?: string;
    /** Élément à droite de l'en-tête (badge, bouton…). */
    action?: ReactNode;
    /** Lien « voir tout » affiché dans l'en-tête. */
    href?: string;
    hrefLabel?: string;
    children: ReactNode;
    className?: string;
    bodyClassName?: string;
    interactive?: boolean;
}

export function Panel({
    title,
    icon: Icon,
    iconClassName = "text-primary",
    action,
    href,
    hrefLabel = "Tout voir",
    children,
    className,
    bodyClassName,
    interactive = false,
}: PanelProps) {
    return (
        <SpotlightCard interactive={interactive} className={cn("overflow-hidden", className)}>
            {(title || action || href) && (
                <div className="relative z-[2] flex items-center justify-between gap-3 border-b border-white/[0.05] px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-2.5">
                        {Icon && (
                            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ring-white/[0.06]">
                                <Icon className={cn("h-3.5 w-3.5", iconClassName)} />
                            </span>
                        )}
                        {title && <h2 className="truncate text-sm font-semibold tracking-tight">{title}</h2>}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                        {action}
                        {href && (
                            <Link
                                href={href}
                                className="group flex items-center gap-0.5 text-xs text-muted-foreground transition-colors hover:text-primary"
                            >
                                {hrefLabel}
                                <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                            </Link>
                        )}
                    </div>
                </div>
            )}
            <div className={cn("relative z-[2] p-5", bodyClassName)}>{children}</div>
        </SpotlightCard>
    );
}
