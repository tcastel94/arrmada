"use client";

/**
 * Compteur animé : le nombre « roule » de 0 (ou de l'ancienne valeur)
 * jusqu'à la nouvelle valeur, comme un compteur kilométrique.
 * Démarre seulement quand l'élément devient visible à l'écran.
 */
import { useEffect, useRef } from "react";
import { useInView, useMotionValue, useSpring } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedNumberProps {
    value: number | null | undefined;
    /** Nombre de décimales affichées. */
    decimals?: number;
    /** Suffixe collé au nombre (ex: " %", " Go"). */
    suffix?: string;
    prefix?: string;
    className?: string;
    /** Texte affiché si la valeur est absente. */
    fallback?: string;
}

export function AnimatedNumber({
    value,
    decimals = 0,
    suffix = "",
    prefix = "",
    className,
    fallback = "—",
}: AnimatedNumberProps) {
    const ref = useRef<HTMLSpanElement>(null);
    const inView = useInView(ref, { once: true, margin: "-20px" });
    const motionValue = useMotionValue(0);
    // Ressort amorti : rapide au début, ralentit en arrivant (effet « premium »).
    const spring = useSpring(motionValue, { stiffness: 70, damping: 20, mass: 0.9 });

    const formatter = useRef(
        new Intl.NumberFormat("fr-FR", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }),
    );

    useEffect(() => {
        if (inView && typeof value === "number" && Number.isFinite(value)) {
            motionValue.set(value);
        }
    }, [inView, value, motionValue]);

    // On écrit directement dans le DOM (pas de re-render React à chaque frame).
    useEffect(
        () =>
            spring.on("change", (latest) => {
                if (ref.current) {
                    ref.current.textContent = `${prefix}${formatter.current.format(latest)}${suffix}`;
                }
            }),
        [spring, prefix, suffix],
    );

    if (value === null || value === undefined || !Number.isFinite(value)) {
        return <span className={className}>{fallback}</span>;
    }

    return (
        <span ref={ref} className={cn("tabular-nums", className)}>
            {prefix}
            {formatter.current.format(0)}
            {suffix}
        </span>
    );
}
