"use client";

/**
 * Section de contenu standard, façon iOS : titre de section au-dessus,
 * contenu dans une carte gris foncé.
 * Les props `icon` / `iconClassName` de l'ancien en-tête sont acceptées
 * mais plus affichées (les titres de section iOS n'ont pas d'icône).
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
    action,
    href,
    hrefLabel = "Tout voir",
    children,
    className,
    bodyClassName,
    interactive = false,
}: PanelProps) {
    return (
        <section className={cn("min-w-0", className)}>
            {/* En-tête de section iOS : titre gras à gauche, « Tout voir › » en bleu à droite */}
            {(title || action || href) && (
                <div className="mb-2.5 flex items-end justify-between gap-3 px-0.5">
                    {title ? <h2 className="truncate text-[20px] font-bold tracking-tight">{title}</h2> : <span />}
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
            <SpotlightCard interactive={interactive} className="overflow-hidden">
                <div className={cn("p-4 md:p-5", bodyClassName)}>{children}</div>
            </SpotlightCard>
        </section>
    );
}
