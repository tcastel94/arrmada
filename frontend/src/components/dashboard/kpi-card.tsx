"use client";

/**
 * Carte indicateur clé du Dashboard : grand compteur animé + jauge
 * circulaire + sous-titre. Liseré lumineux en haut et halo au survol.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { RingGauge, type GaugeTone } from "@/components/fx/ring-gauge";
import { fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const TONE_TEXT: Record<GaugeTone, string> = {
    primary: "text-primary",
    brand: "text-brand",
    violet: "text-violet-300",
    emerald: "text-emerald-300",
    amber: "text-amber-300",
    rose: "text-rose-300",
};
const TONE_LINE: Record<GaugeTone, string> = {
    primary: "via-primary",
    brand: "via-brand",
    violet: "via-violet-400",
    emerald: "via-emerald-400",
    amber: "via-amber-400",
    rose: "via-rose-400",
};

interface KpiCardProps {
    label: string;
    icon: LucideIcon;
    tone: GaugeTone;
    value: ReactNode;
    sub?: ReactNode;
    /** Pourcentage affiché dans la jauge (0-100) ; masquée si undefined. */
    gauge?: number;
    gaugeLabel?: string;
    href?: string;
}

export function KpiCard({ label, icon: Icon, tone, value, sub, gauge, gaugeLabel, href }: KpiCardProps) {
    const body = (
        <SpotlightCard className="group relative h-full overflow-hidden p-5">
            {/* Liseré lumineux supérieur */}
            <div className={cn("absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent to-transparent opacity-70", TONE_LINE[tone])} />
            <div className="relative z-[2] flex items-center justify-between gap-3">
                <div className="min-w-0">
                    <p className="eyebrow flex items-center gap-1.5">
                        <Icon className={cn("h-3.5 w-3.5", TONE_TEXT[tone])} />
                        {label}
                    </p>
                    <div className="mt-2 text-3xl font-bold tracking-tight md:text-4xl">{value}</div>
                    {sub && <div className="mt-1.5 truncate text-xs text-muted-foreground">{sub}</div>}
                </div>
                {typeof gauge === "number" && (
                    <RingGauge value={gauge} size={68} stroke={6} tone={tone} className="transition-transform duration-500 ease-spring group-hover:scale-110">
                        <div className="text-center leading-none">
                            <span className={cn("text-sm font-bold tabular-nums", TONE_TEXT[tone])}>{Math.round(gauge)}%</span>
                            {gaugeLabel && <span className="mt-0.5 block text-[8px] uppercase tracking-wider text-muted-foreground">{gaugeLabel}</span>}
                        </div>
                    </RingGauge>
                )}
            </div>
        </SpotlightCard>
    );
    return (
        <motion.div variants={fadeUp} className="h-full">
            {href ? (
                <Link href={href} className="block h-full rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                    {body}
                </Link>
            ) : (
                body
            )}
        </motion.div>
    );
}
