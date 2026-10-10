"use client";

/**
 * Carte « verre » avec halo lumineux qui suit la souris.
 * Le halo est un pseudo-élément CSS (.spotlight::after) positionné via
 * deux variables CSS mises à jour au mouvement — aucun re-render React.
 */
import { forwardRef, type HTMLAttributes, type MouseEvent } from "react";
import { cn } from "@/lib/utils";

interface SpotlightCardProps extends HTMLAttributes<HTMLDivElement> {
    /** Ajoute l'effet de survol (bordure + ombre colorée). */
    interactive?: boolean;
}

export const SpotlightCard = forwardRef<HTMLDivElement, SpotlightCardProps>(
    ({ className, interactive = true, onMouseMove, children, ...props }, ref) => {
        const handleMove = (e: MouseEvent<HTMLDivElement>) => {
            const rect = e.currentTarget.getBoundingClientRect();
            e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
            e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
            onMouseMove?.(e);
        };
        return (
            <div
                ref={ref}
                onMouseMove={handleMove}
                className={cn(
                    "glass spotlight rounded-2xl",
                    interactive && "glass-hover",
                    className,
                )}
                {...props}
            >
                {children}
            </div>
        );
    },
);
SpotlightCard.displayName = "SpotlightCard";
