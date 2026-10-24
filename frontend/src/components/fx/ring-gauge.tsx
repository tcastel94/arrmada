"use client";

/**
 * Jauge circulaire (SVG), style « anneaux d'activité » Apple :
 * piste gris foncé, arc de couleur pleine, bouts arrondis.
 * L'arc se remplit à l'apparition.
 */
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

const TONES = {
    primary: "hsl(var(--primary))",
    brand: "hsl(var(--primary))",
    violet: "hsl(var(--chart-4))",
    emerald: "hsl(var(--success))",
    amber: "hsl(var(--warning))",
    rose: "hsl(var(--destructive))",
} as const;

export type GaugeTone = keyof typeof TONES;

interface RingGaugeProps {
    /** 0 → 100. */
    value: number;
    size?: number;
    stroke?: number;
    tone?: GaugeTone;
    className?: string;
    /** Contenu centré (texte, icône…). */
    children?: ReactNode;
}

export function RingGauge({ value, size = 64, stroke = 6, tone = "primary", className, children }: RingGaugeProps) {
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const clamped = Math.max(0, Math.min(100, value || 0));

    return (
        <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Piste */}
                <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="hsl(0 0% 100% / 0.1)" strokeWidth={stroke} />
                {/* Arc */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={TONES[tone]}
                    strokeWidth={stroke}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
                    transition={{ duration: 0.9, ease: EASE_OUT }}
                />
            </svg>
            {children && <div className="absolute inset-0 flex items-center justify-center">{children}</div>}
        </div>
    );
}
