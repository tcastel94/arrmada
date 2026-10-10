"use client";

/**
 * Carte poster unique pour toute l'app (médiathèque, recherche, manquants,
 * filmographie…). Effets : inclinaison 3D, zoom de l'affiche, reflet,
 * halo coloré au survol, sélection animée.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Film, Tv } from "lucide-react";
import { useState, type ReactNode, type MouseEvent } from "react";
import { cn } from "@/lib/utils";
import { scaleIn } from "@/lib/motion";
import { TiltCard } from "@/components/fx/tilt-card";

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
    /** Ligne d'infos sous le titre (dans l'overlay). */
    meta?: ReactNode;
    /** Barre de progression en bas de l'affiche (0-100). */
    progress?: number;
    /** Bouton flottant (ex: « + Ajouter »). */
    action?: ReactNode;
    /** Mode sélection (cases à cocher). */
    selectable?: boolean;
    selected?: boolean;
    onToggleSelect?: () => void;
    /** Affiche grisée (ex: média manquant). */
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
        <TiltCard className="rounded-2xl" max={7}>
            <div
                className={cn(
                    "shine relative aspect-[2/3] overflow-hidden rounded-2xl bg-muted/40 ring-1 transition-all duration-500 ease-smooth",
                    selected
                        ? "ring-2 ring-primary shadow-[0_0_0_4px_hsl(var(--primary)/0.15),0_20px_50px_-15px_hsl(var(--primary)/0.6)]"
                        : "ring-white/[0.07] group-hover:ring-primary/40 group-hover:shadow-[0_24px_60px_-20px_hsl(var(--primary)/0.55)]",
                )}
            >
                {/* Affiche */}
                {posterUrl && !failed ? (
                    <img
                        src={posterUrl}
                        alt={title}
                        loading="lazy"
                        onLoad={() => setLoaded(true)}
                        onError={() => setFailed(true)}
                        className={cn(
                            "h-full w-full object-cover transition-all duration-700 ease-smooth group-hover:scale-[1.08]",
                            loaded ? "opacity-100 blur-0" : "opacity-0 blur-md",
                            dimmed && "grayscale-[60%] opacity-60 group-hover:grayscale-0 group-hover:opacity-100",
                        )}
                    />
                ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/60 via-muted/30 to-primary/10">
                        <Placeholder className="h-10 w-10 text-muted-foreground/30" strokeWidth={1.5} />
                    </div>
                )}
                {posterUrl && !loaded && !failed && <div className="shimmer absolute inset-0" />}

                {/* Dégradé bas + titre */}
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/95 via-black/45 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 z-[3] p-3" style={{ transform: "translateZ(30px)" }}>
                    <p className="line-clamp-2 text-sm font-semibold leading-tight text-white drop-shadow-lg">{title}</p>
                    {subtitle && <div className="mt-0.5 text-[11px] text-white/65">{subtitle}</div>}
                    {meta && (
                        <div className="mt-1.5 max-h-0 overflow-hidden opacity-0 transition-all duration-500 ease-smooth group-hover:max-h-16 group-hover:opacity-100">
                            {meta}
                        </div>
                    )}
                </div>

                {/* Progression (épisodes, lecture…) */}
                {typeof progress === "number" && (
                    <div className="absolute inset-x-0 bottom-0 z-[4] h-1 bg-white/10">
                        <div
                            className="h-full bg-gradient-to-r from-primary to-brand shadow-[0_0_10px_hsl(var(--primary))]"
                            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
                        />
                    </div>
                )}

                {/* Badges */}
                {badges && <div className="absolute left-2 top-2 z-[11] flex flex-col items-start gap-1">{badges}</div>}
                {corner && !selectable && <div className="absolute right-2 top-2 z-[11]">{corner}</div>}

                {/* Case de sélection */}
                {selectable && (
                    <motion.div
                        initial={false}
                        animate={{ scale: selected ? 1 : 0.9 }}
                        className={cn(
                            "absolute right-2 top-2 z-[11] flex h-6 w-6 items-center justify-center rounded-full border-2 backdrop-blur",
                            selected ? "border-primary bg-primary text-primary-foreground" : "border-white/60 bg-black/40",
                        )}
                    >
                        {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                    </motion.div>
                )}

            </div>
        </TiltCard>
    );

    const wrapped = href ? (
        <Link href={href} onClick={handleClick} className="block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
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
            className={cn("block rounded-2xl", (onClick || selectable) && "cursor-pointer")}
        >
            {body}
        </div>
    );

    // L'action flottante (ex: « + Ajouter ») est une SŒUR du lien, pas un
    // enfant : un <button> imbriqué dans un <a> est invalide et casse la
    // navigation clavier / lecteurs d'écran.
    const withAction = (
        <div className="relative">
            {wrapped}
            {action && !selectable && <div className="absolute bottom-2 right-2 z-[12]">{action}</div>}
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
        dark: "bg-black/65 text-white ring-white/15",
        primary: "bg-primary/85 text-primary-foreground ring-primary/40",
        success: "bg-emerald-500/85 text-white ring-emerald-300/30",
        warning: "bg-amber-500/90 text-black ring-amber-300/30",
        danger: "bg-red-500/85 text-white ring-red-300/30",
        violet: "bg-violet-500/85 text-white ring-violet-300/30",
    };
    return (
        <span
            title={title}
            className={cn(
                "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold leading-none ring-1 backdrop-blur-md",
                tones[tone],
                className,
            )}
        >
            {children}
        </span>
    );
}
