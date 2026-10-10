"use client";

/* eslint-disable @next/next/no-img-element */
/**
 * Ligne « média » commune aux onglets Qualité / Nettoyage du hub Santé :
 * vignette d'affiche, titre cliquable vers la fiche, méta (année ·
 * service…), badges, taille et actions.
 * ----------------------------------------------------------------
 * Mise en page en grille : sur mobile les actions passent sous le texte
 * (pas de débordement horizontal à 390 px), sur desktop elles restent à
 * droite.
 */
import Link from "next/link";
import { forwardRef, useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { Film, Tv } from "lucide-react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

/** Vignette d'affiche 2:3 avec repli sur une icône si l'image manque ou casse. */
export function PosterThumb({
    src,
    alt,
    type,
    className,
}: {
    src?: string | null;
    alt: string;
    type?: string;
    className?: string;
}) {
    const [failed, setFailed] = useState(false);
    const Icon = type === "series" ? Tv : Film;
    return (
        <div
            className={cn(
                "relative h-[60px] w-10 shrink-0 overflow-hidden rounded-lg bg-gradient-to-br from-muted/70 to-primary/10 ring-1 ring-white/[0.08]",
                className,
            )}
        >
            {src && !failed ? (
                <img
                    src={src}
                    alt={alt}
                    loading="lazy"
                    onError={() => setFailed(true)}
                    className="h-full w-full object-cover transition-transform duration-500 ease-smooth group-hover:scale-110"
                />
            ) : (
                <div className="flex h-full w-full items-center justify-center">
                    <Icon className="h-4 w-4 text-muted-foreground/60" strokeWidth={1.6} />
                </div>
            )}
        </div>
    );
}

export interface MediaRowProps {
    title: string;
    type?: string;
    posterUrl?: string | null;
    /** Lien vers la fiche média (titre + vignette cliquables). */
    href?: string;
    /** Éléments de la ligne méta, joints par « · » (les vides sont ignorés). */
    meta?: (string | number | null | undefined | false)[];
    /** Badges sous le titre (qualité, état…). */
    badges?: ReactNode;
    /** Explication (ex: suggestion du backend). */
    description?: ReactNode;
    /** Contenu additionnel (barre de progression…). */
    extra?: ReactNode;
    /** Taille lisible affichée à droite. */
    size?: string;
    sizeClassName?: string;
    actions?: ReactNode;
    /** Ligne en cours de traitement (action lancée) → légèrement estompée. */
    busy?: boolean;
    className?: string;
}

/**
 * `forwardRef` + `motion.li` : nécessaire pour `AnimatePresence
 * mode="popLayout"` (la ligne supprimée s'efface pendant que les autres
 * remontent en douceur).
 */
export const MediaRow = forwardRef<HTMLLIElement, MediaRowProps>(function MediaRow(
    { title, type, posterUrl, href, meta, badges, description, extra, size, sizeClassName, actions, busy, className },
    ref,
) {
    const metaText = (meta ?? []).filter((m) => m !== null && m !== undefined && m !== false && m !== "").join(" · ");
    const poster = <PosterThumb src={posterUrl} alt={title} type={type} />;

    return (
        <motion.li
            ref={ref}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: busy ? 0.55 : 1, y: 0 }}
            exit={{ opacity: 0, x: -24, transition: { duration: 0.25 } }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className={cn(
                "group grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 gap-y-2 px-4 py-3 transition-colors hover:bg-white/[0.025] sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:px-5",
                className,
            )}
        >
            {href ? (
                <Link href={href} aria-label={`Ouvrir la fiche de ${title}`} className="row-span-2 rounded-lg sm:row-span-1">
                    {poster}
                </Link>
            ) : (
                <div className="row-span-2 sm:row-span-1">{poster}</div>
            )}

            <div className="min-w-0">
                <div className="flex min-w-0 items-baseline gap-2">
                    {href ? (
                        <Link
                            href={href}
                            className="truncate text-sm font-semibold tracking-tight transition-colors hover:text-primary"
                        >
                            {title}
                        </Link>
                    ) : (
                        <p className="truncate text-sm font-semibold tracking-tight">{title}</p>
                    )}
                </div>
                {metaText && <p className="mt-0.5 truncate text-xs text-muted-foreground">{metaText}</p>}
                {badges && <div className="mt-1.5 flex flex-wrap items-center gap-1.5">{badges}</div>}
                {description && <p className="mt-1 text-xs text-muted-foreground/80">{description}</p>}
                {extra && <div className="mt-2">{extra}</div>}
            </div>

            {(size || actions) && (
                <div className="col-start-2 flex flex-wrap items-center justify-between gap-2 sm:col-start-3 sm:justify-end sm:gap-3">
                    {size && (
                        <span className={cn("text-sm font-semibold tabular-nums", sizeClassName)}>{size}</span>
                    )}
                    {actions && <div className="flex items-center gap-1">{actions}</div>}
                </div>
            )}
        </motion.li>
    );
});
