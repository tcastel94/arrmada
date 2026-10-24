"use client";

/**
 * Tuiles du héros « Santé médiathèque » : score global (jauge) + espace
 * récupérable + doublons + upgrades. Chaque tuile chiffrée est un bouton
 * qui ouvre l'onglet correspondant.
 */
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ArrowUpCircle, ChevronRight, Copy, HardDrive, type LucideIcon } from "lucide-react";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { RingGauge } from "@/components/fx/ring-gauge";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { fadeUp, stagger } from "@/lib/motion";
import { healthTone, healthVerdict, type HealthResult } from "./health-score";

export type HealthTab = "quality" | "duplicates" | "cleanup";

/** Découpe une taille en valeur + unité pour pouvoir animer le nombre. */
function bytesParts(bytes: number): { value: number; unit: string; decimals: number } {
    const GB = 1024 ** 3;
    const TB = 1024 ** 4;
    if (bytes >= TB) return { value: bytes / TB, unit: "To", decimals: 2 };
    if (bytes >= GB) return { value: bytes / GB, unit: "Go", decimals: 1 };
    return { value: bytes / 1024 ** 2, unit: "Mo", decimals: 0 };
}

interface HealthHeroProps {
    health: HealthResult;
    scoreLoading: boolean;
    reclaimable?: { bytes: number; exact: boolean };
    reclaimableLoading: boolean;
    duplicates?: number;
    duplicatesLoading: boolean;
    upgrades?: number;
    upgradesLoading: boolean;
    onOpen: (tab: HealthTab) => void;
}

export function HealthHero({
    health,
    scoreLoading,
    reclaimable,
    reclaimableLoading,
    duplicates,
    duplicatesLoading,
    upgrades,
    upgradesLoading,
    onOpen,
}: HealthHeroProps) {
    const tone = healthTone(health.score);
    const bp = reclaimable ? bytesParts(reclaimable.bytes) : null;

    return (
        <motion.div
            variants={stagger(0.15, 0.08)}
            initial="hidden"
            animate="show"
            // Mobile : score en pleine largeur puis 3 tuiles compactes côte à côte.
            className="grid w-full grid-cols-3 gap-2 sm:grid-cols-2 sm:gap-3 xl:grid-cols-[1.6fr_1fr_1fr_1fr]"
        >
            {/* Score global */}
            <motion.div
                variants={fadeUp}
                className="col-span-3 flex items-center gap-4 rounded-2xl border border-white/[0.06] bg-background/40 p-4 backdrop-blur sm:col-span-2 xl:col-span-1"
            >
                {scoreLoading ? (
                    <Shimmer className="h-[92px] w-[92px] shrink-0 rounded-full" />
                ) : (
                    <RingGauge value={health.score ?? 0} size={92} stroke={8} tone={tone} className="shrink-0">
                        <div className="text-center leading-none">
                            {health.score === null ? (
                                <span className="text-lg font-bold text-muted-foreground">—</span>
                            ) : (
                                <AnimatedNumber value={health.score} className="text-2xl font-bold" />
                            )}
                            <span className="mt-0.5 block text-[9px] uppercase tracking-widest text-muted-foreground">/ 100</span>
                        </div>
                    </RingGauge>
                )}
                <div className="min-w-0 flex-1">
                    <p className="eyebrow">Score de santé</p>
                    <p className="text-sm font-semibold">{scoreLoading ? "Analyse en cours…" : healthVerdict(health.score)}</p>
                    <ul className="mt-2 space-y-1.5">
                        {health.parts.map((p) => (
                            <li key={p.key}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <div tabIndex={0} className="grid cursor-help grid-cols-[4.5rem_1fr_2rem] items-center gap-2 text-[11px]">
                                            <span className="text-muted-foreground">{p.label}</span>
                                            <GradientProgress
                                                value={p.score}
                                                tone={p.score >= 80 ? "emerald" : p.score >= 60 ? "amber" : "rose"}
                                                glow={false}
                                                className="h-1"
                                            />
                                            <span className="text-right font-semibold tabular-nums">{Math.round(p.score)}</span>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent className="text-xs">
                                        {p.detail} · compte pour {Math.round(p.weight * 100)} % du score
                                    </TooltipContent>
                                </Tooltip>
                            </li>
                        ))}
                    </ul>
                </div>
            </motion.div>

            <MetricTile
                icon={HardDrive}
                iconClass="bg-success/15 text-success ring-success/25"
                label="Espace récupérable"
                hint={reclaimable && !reclaimable.exact ? "au moins · non surveillés + séries incomplètes" : "non surveillés + séries incomplètes"}
                loading={reclaimableLoading}
                onClick={() => onOpen("cleanup")}
                value={
                    bp ? (
                        <>
                            {reclaimable && !reclaimable.exact && <span className="mr-0.5 text-lg">≥</span>}
                            <AnimatedNumber value={bp.value} decimals={bp.decimals} suffix={` ${bp.unit}`} />
                        </>
                    ) : null
                }
            />
            <MetricTile
                icon={Copy}
                iconClass="bg-primary/15 text-primary ring-primary/25"
                label="Doublons"
                hint="titres présents dans plusieurs services"
                loading={duplicatesLoading}
                onClick={() => onOpen("duplicates")}
                value={duplicates !== undefined ? <AnimatedNumber value={duplicates} /> : null}
            />
            <MetricTile
                icon={ArrowUpCircle}
                iconClass="bg-warning/15 text-warning ring-warning/25"
                label="Upgrades possibles"
                hint="films sous le 1080p Bluray"
                loading={upgradesLoading}
                onClick={() => onOpen("quality")}
                value={upgrades !== undefined ? <AnimatedNumber value={upgrades} /> : null}
            />
        </motion.div>
    );
}

function MetricTile({
    icon: Icon,
    iconClass,
    label,
    hint,
    value,
    loading,
    onClick,
}: {
    icon: LucideIcon;
    iconClass: string;
    label: string;
    hint: string;
    value: ReactNode;
    loading: boolean;
    onClick: () => void;
}) {
    return (
        <motion.button
            type="button"
            variants={fadeUp}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.98 }}
            onClick={onClick}
            className="group flex min-w-0 flex-col justify-between gap-2 rounded-2xl border border-white/[0.06] bg-background/40 p-3 text-left backdrop-blur transition-colors hover:border-white/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 sm:gap-3 sm:p-4"
        >
            <div className="flex items-center justify-between">
                <span className={cn("flex h-8 w-8 items-center justify-center rounded-xl ring-1", iconClass)}>
                    <Icon className="h-4 w-4" />
                </span>
                <ChevronRight className="hidden h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground sm:block" />
            </div>
            <div>
                {loading ? (
                    <Shimmer className="h-8 w-20 rounded-lg" />
                ) : (
                    <p className="whitespace-nowrap text-lg font-bold tracking-tight sm:text-2xl">
                        {value ?? <span className="text-muted-foreground">—</span>}
                    </p>
                )}
                <p className="text-[11px] font-medium leading-tight sm:text-xs">{label}</p>
                <p className="hidden text-[11px] text-muted-foreground sm:block">
                    {value === null && !loading ? "analyse indisponible" : hint}
                </p>
            </div>
        </motion.button>
    );
}
