"use client";

/**
 * Logo ArrMada « Lecture » : un « A » dont la barre est un bouton lecture.
 * ----------------------------------------------------------------
 * Mêmes tracés que branding/arrmada-mark.svg, la source de la marque : si le
 * logo change, modifier les deux (le SVG sert à générer favicon, icônes,
 * image de partage et images Kodi via branding/export.py).
 *
 * SVG en ligne plutôt qu'une image : net à toutes les tailles (de 16 px à
 * plein écran), aucune requête réseau, et pas de flou sur les écrans Retina.
 *
 * `animated` : le « A » se trace (comme un stylo), puis le bouton lecture
 * apparaît avec un léger rebond. Même chorégraphie que l'intro de l'appli Kodi.
 * Respecte « réduire les animations » du système (prefers-reduced-motion).
 */
import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

const A_PATH = "M11 54 L32 9 L53 54";
const PLAY_PATH =
    "M27 34.8v14.4a1.6 1.6 0 0 0 2.4 1.4l11.4-7.2a1.6 1.6 0 0 0 0-2.8l-11.4-7.2a1.6 1.6 0 0 0-2.4 1.4z";

interface BrandProps {
    className?: string;
    /** Texte lu par les lecteurs d'écran ; sans titre, le logo est décoratif. */
    title?: string;
    /** Logo qui se dessine à l'apparition (écran de connexion, accueil…). */
    animated?: boolean;
    /** Délai avant le début du tracé, en secondes. */
    delay?: number;
}

/** Le logo seul, sur fond transparent. */
export function BrandMark({ className, title, animated = false, delay = 0 }: BrandProps) {
    // Identifiant de dégradé unique : plusieurs logos peuvent cohabiter sur
    // une page (barre latérale + tableau de bord). Les « : » de useId sont
    // retirés, ils cassent la référence url(#…).
    const gradientId = `arrmada-g-${useId().replace(/:/g, "")}`;
    const reduced = useReducedMotion();
    const play = animated && !reduced;

    return (
        <svg
            viewBox="0 0 64 64"
            className={className}
            role={title ? "img" : undefined}
            aria-label={title}
            aria-hidden={title ? undefined : true}
        >
            <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#4A9EFF" />
                    <stop offset="1" stopColor="#22E0EE" />
                </linearGradient>
            </defs>
            <motion.path
                d={A_PATH}
                fill="none"
                stroke={`url(#${gradientId})`}
                strokeWidth={9}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={play ? { pathLength: 0, opacity: 0 } : false}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{
                    pathLength: { duration: 0.9, delay, ease: [0.65, 0, 0.35, 1] },
                    opacity: { duration: 0.15, delay },
                }}
            />
            <motion.path
                d={PLAY_PATH}
                fill="#EAF6FF"
                style={{ transformOrigin: "34px 42px" }}
                initial={play ? { scale: 0, opacity: 0 } : false}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 420, damping: 14, delay: delay + 0.75 }}
            />
        </svg>
    );
}

/**
 * Tuile d'application : fond nuit, halo bleu et logo à 62 %.
 * Elle remplit son conteneur, qui fixe la taille et l'arrondi (overflow-hidden).
 */
export function BrandIcon({ className, title, animated, delay }: BrandProps) {
    return (
        <div
            className={cn(
                "relative grid h-full w-full place-items-center bg-[radial-gradient(125%_125%_at_22%_0%,#17223A_0%,#0B111D_60%,#080B12_100%)]",
                className,
            )}
        >
            <div
                aria-hidden
                className="absolute inset-[10%] rounded-full bg-[radial-gradient(closest-side,rgba(74,158,255,0.32),transparent)]"
            />
            <BrandMark title={title} animated={animated} delay={delay} className="relative h-[62%] w-[62%]" />
        </div>
    );
}
