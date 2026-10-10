"use client";

/**
 * Compteur animé « sûr » pour les StatPills.
 * ----------------------------------------------------------------
 * Contournement d'un défaut d'AnimatedNumber (composant partagé) : s'il est
 * monté avec une valeur `undefined` (données pas encore chargées), il rend
 * un <span> sans ref, son détecteur de visibilité ne s'attache jamais et le
 * compteur reste bloqué sur « 0 » une fois les données arrivées.
 * Ici on ne monte AnimatedNumber qu'une fois la valeur connue.
 */
import { AnimatedNumber } from "@/components/fx/animated-number";

export function LiveCount({ value }: { value: number | null | undefined }) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return <span className="text-muted-foreground/60">—</span>;
    }
    return <AnimatedNumber value={value} />;
}
