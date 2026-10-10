"use client";

/**
 * Jauge circulaire animée (SVG) avec trait en dégradé et halo.
 * Le cercle se « remplit » à l'apparition.
 */
import { motion } from "framer-motion";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";

const TONES = {
    primary: ["hsl(var(--primary))", "hsl(var(--brand))"],
    brand: ["hsl(var(--brand))", "hsl(170 80% 55%)"],
    violet: ["hsl(262 83% 70%)", "hsl(290 80% 70%)"],
    emerald: ["hsl(152 69% 47%)", "hsl(170 80% 50%)"],
    amber: ["hsl(38 95% 58%)", "hsl(25 95% 60%)"],
    rose: ["hsl(350 89% 64%)", "hsl(330 85% 66%)"],
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

export function RingGauge({
    value,
    size = 64,
    stroke = 6,
    tone = "primary",
    className,
    children,
}: RingGaugeProps) {
    const id = useId().replace(/:/g, "");
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const clamped = Math.max(0, Math.min(100, value || 0));
    const [from, to] = TONES[tone];

    return (
        <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90 overflow-visible">
                <defs>
                    <linearGradient id={`g-${id}`} x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor={from} />
                        <stop offset="100%" stopColor={to} />
                    </linearGradient>
                    <filter id={`f-${id}`} x="-50%" y="-50%" width="200%" height="200%">
                        <feGaussianBlur stdDeviation="2.5" />
                    </filter>
                </defs>
                {/* Piste */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="hsl(var(--muted))"
                    strokeWidth={stroke}
                    opacity={0.7}
                />
                {/* Halo flou sous l'arc */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={`url(#g-${id})`}
                    strokeWidth={stroke}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    filter={`url(#f-${id})`}
                    opacity={0.6}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
                    transition={{ duration: 1.4, ease: EASE_OUT, delay: 0.15 }}
                />
                {/* Arc principal */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={`url(#g-${id})`}
                    strokeWidth={stroke}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
                    transition={{ duration: 1.4, ease: EASE_OUT, delay: 0.15 }}
                />
            </svg>
            {children && <div className="absolute inset-0 flex items-center justify-center">{children}</div>}
        </div>
    );
}
