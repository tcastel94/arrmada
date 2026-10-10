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

    const hasValue = typeof value === "number" && Number.isFinite(value);
    const format = (n: number) => `${prefix}${formatter.current.format(n)}${suffix}`;

    // Lance l'animation vers la valeur cible dès que l'élément est visible.
    useEffect(() => {
        if (inView && hasValue) motionValue.set(value as number);
    }, [inView, hasValue, value, motionValue]);

    // Le texte est piloté EXCLUSIVEMENT ici (écriture directe dans le DOM,
    // sans re-render React à chaque frame). Le même <span> porteur de la ref
    // est toujours rendu : sinon l'observateur de visibilité ne s'accroche
    // jamais et le compteur reste bloqué à 0.
    useEffect(() => {
        if (!ref.current) return;
        ref.current.textContent = hasValue ? format(spring.get()) : fallback;
        if (!hasValue) return;
        return spring.on("change", (latest) => {
            if (ref.current) ref.current.textContent = format(latest);
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [spring, hasValue, fallback, prefix, suffix]);

    return <span ref={ref} className={cn("tabular-nums", className)} />;
}
