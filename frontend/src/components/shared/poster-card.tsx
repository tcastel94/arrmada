"use client";

/**
 * Carte affiche unique pour toute l'app (médiathèque, recherche, manquants,
 * filmographie…), style app Apple TV :
 *   - affiche nette aux coins arrondis, titre et sous-titre EN DESSOUS
 *     (lisibles même sur une affiche chargée, contrairement à un texte
 *     posé sur l'image) ;
 *   - au survol (souris) : léger agrandissement + ombre portée, et les
 *     infos détaillées (`meta`) apparaissent en bas de l'affiche ;
 *   - au toucher (mobile) : léger enfoncement, comme un bouton iOS ;
 *   - mode sélection : pastille ronde cochée en haut à droite.
 * L'affiche apparaît en fondu une fois chargée (pas de saut visuel).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Film, Tv } from "lucide-react";
import { useState, type ReactNode, type MouseEvent } from "react";
import { cn } from "@/lib/utils";
import { scaleIn } from "@/lib/motion";

export interface PosterCardProps {
    title: string;
    subtitle?: ReactNode;
    posterUrl?: string | null;
    type?: "movie" | "series" | string;
    href?: string;
    onClick?: () => void;
    /** Badges en haut à gauche (qualité, statut…). */
    badges?: ReactNode;
    /** Badge en haut à droite. */
    corner?: ReactNode;
    /** Infos détaillées, affichées sur l'affiche au survol. */
    meta?: ReactNode;
    /** Barre de progression en bas de l'affiche (0-100). */
    progress?: number;
    /** Bouton flottant (ex : « + Ajouter »). */
    action?: ReactNode;
    /** Mode sélection (cases à cocher). */
    selectable?: boolean;
    selected?: boolean;
    onToggleSelect?: () => void;
    /** Affiche grisée (ex : média manquant). */
    dimmed?: boolean;
    className?: string;
    /** Désactive l'animation d'entrée (si le parent n'utilise pas stagger). */
    noEntrance?: boolean;
}

export function PosterCard({
    title,
    subtitle,
    posterUrl,
    type,
    href,
    onClick,
    badges,
    corner,
    meta,
    progress,
    action,
    selectable,
    selected,
    onToggleSelect,
    dimmed,
    className,
    noEntrance,
}: PosterCardProps) {
    const [loaded, setLoaded] = useState(false);
    const [failed, setFailed] = useState(false);
    const Placeholder = type === "series" ? Tv : Film;

    const handleClick = (e: MouseEvent) => {
        if (selectable) {
            e.preventDefault();
            onToggleSelect?.();
            return;
        }
        onClick?.();
    };

    const body = (
        <div className="group/poster">
            <div
                className={cn(
                    "relative aspect-[2/3] overflow-hidden rounded-[10px] bg-white/[0.06] transition-[transform,box-shadow] duration-300 ease-smooth",
                    "group-hover/poster:scale-[1.03] group-hover/poster:shadow-[0_16px_40px_-12px_rgb(0_0_0/0.9)] group-active/poster:scale-[0.98]",
                    selected && "ring-[3px] ring-primary ring-offset-2 ring-offset-background",
                )}
            >
                {/* Affiche */}
                {posterUrl && !failed ? (
                    <img
                        src={posterUrl}
                        alt={title}
                        loading="lazy"
                        decoding="async"
                        onLoad={() => setLoaded(true)}
                        onError={() => setFailed(true)}
                        className={cn(
                            "h-full w-full object-cover transition-opacity duration-500",
                            loaded ? "opacity-100" : "opacity-0",
                            dimmed && "opacity-50 grayscale-[50%]",
                        )}
                    />
                ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-2 p-3 text-center">
                        <Placeholder className="h-8 w-8 text-white/20" strokeWidth={1.5} />
                        <span className="line-clamp-3 text-[12px] font-medium text-white/40">{title}</span>
                    </div>
                )}
                {posterUrl && !loaded && !failed && <div className="shimmer absolute inset-0" />}

                {/* Infos détaillées au survol (souris uniquement) */}
                {meta && (
                    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[3] bg-gradient-to-t from-black/90 via-black/60 to-transparent p-2.5 pt-8 opacity-0 transition-opacity duration-200 [@media(hover:hover)]:group-hover/poster:opacity-100">
                        {meta}
                    </div>
                )}

                {/* Progression (épisodes, lecture…) */}
                {typeof progress === "number" && (
                    <div className="absolute inset-x-2 bottom-2 z-[4] h-1 overflow-hidden rounded-full bg-black/50">
                        <div className="h-full rounded-full bg-white" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
                    </div>
                )}

                {/* Badges */}
                {badges && <div className="absolute left-1.5 top-1.5 z-[11] flex flex-col items-start gap-1">{badges}</div>}
                {corner && !selectable && <div className="absolute right-1.5 top-1.5 z-[11]">{corner}</div>}

                {/* Case de sélection */}
                {selectable && (
                    <motion.div
                        initial={false}
                        animate={{ scale: selected ? 1 : 0.9 }}
                        className={cn(
                            "absolute right-2 top-2 z-[11] flex h-6 w-6 items-center justify-center rounded-full border-2",
                            selected ? "border-primary bg-primary text-white" : "border-white/80 bg-black/30",
                        )}
                    >
                        {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                    </motion.div>
                )}
            </div>

            {/* Titre et sous-titre sous l'affiche */}
            <div className="mt-2 min-w-0 px-0.5">
                <p className={cn("truncate text-[13px] font-medium leading-tight", dimmed && "text-foreground/60")}>{title}</p>
                {subtitle && <div className="mt-0.5 truncate text-[12px] text-muted-foreground">{subtitle}</div>}
            </div>
        </div>
    );

    const wrapped = href ? (
        <Link href={href} onClick={handleClick} className="block rounded-[10px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            {body}
        </Link>
    ) : (
        <div
            role={onClick || selectable ? "button" : undefined}
            tabIndex={onClick || selectable ? 0 : undefined}
            onClick={handleClick}
            onKeyDown={(e) => {
                if ((e.key === "Enter" || e.key === " ") && (onClick || selectable)) {
                    e.preventDefault();
                    if (selectable) onToggleSelect?.();
                    else onClick?.();
                }
            }}
            className={cn("block rounded-[10px]", (onClick || selectable) && "cursor-pointer")}
        >
            {body}
        </div>
    );

    // L'action flottante (ex : « + Ajouter ») est une SŒUR du lien, pas un
    // enfant : un <button> imbriqué dans un <a> est invalide et casse la
    // navigation clavier / lecteurs d'écran. Elle se pose sur l'affiche
    // (bas droit), au-dessus du titre.
    const withAction = (
        <div className="relative">
            {wrapped}
            {action && !selectable && (
                // Boîte calée sur l'affiche (même largeur, ratio 2:3) pour poser
                // l'action dans son coin bas droit, quelle que soit la taille.
                <div className="pointer-events-none absolute inset-x-0 top-0 z-[12] aspect-[2/3]">
                    <div className="pointer-events-auto absolute bottom-1.5 right-1.5">{action}</div>
                </div>
            )}
        </div>
    );

    return noEntrance ? (
        <div className={className}>{withAction}</div>
    ) : (
        <motion.div variants={scaleIn} className={className}>
            {withAction}
        </motion.div>
    );
}

/** Petit badge lisible posé sur une affiche. */
export function PosterBadge({
    children,
    tone = "dark",
    className,
    title,
}: {
    children: ReactNode;
    tone?: "dark" | "primary" | "success" | "warning" | "danger" | "violet";
    className?: string;
    title?: string;
}) {
    const tones = {
        dark: "bg-black/70 text-white",
        primary: "bg-primary text-white",
        success: "bg-success text-white",
        warning: "bg-warning text-black",
        danger: "bg-destructive text-white",
        violet: "bg-black/70 text-white",
    };
    return (
        <span
            title={title}
            className={cn("inline-flex items-center gap-1 rounded-[5px] px-1.5 py-[3px] text-[10px] font-semibold leading-none backdrop-blur-md", tones[tone], className)}
        >
            {children}
        </span>
    );
}
