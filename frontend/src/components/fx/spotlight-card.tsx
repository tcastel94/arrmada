/**
 * Carte standard (surface gris foncé, coins arrondis).
 * ----------------------------------------------------------------
 * Ancienne « carte projecteur » dont le halo suivait la souris : l'effet
 * est retiré (refonte « Épuré »), le nom reste pour les 13 écrans qui
 * l'importent. `interactive` ne fait plus qu'un léger éclaircissement
 * au survol.
 */
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface SpotlightCardProps extends HTMLAttributes<HTMLDivElement> {
    /** Éclaircissement au survol (cartes cliquables). */
    interactive?: boolean;
}

export const SpotlightCard = forwardRef<HTMLDivElement, SpotlightCardProps>(
    ({ className, interactive = true, children, ...props }, ref) => (
        <div ref={ref} className={cn("surface rounded-2xl", interactive && "glass-hover", className)} {...props}>
            {children}
        </div>
    ),
);
SpotlightCard.displayName = "SpotlightCard";
