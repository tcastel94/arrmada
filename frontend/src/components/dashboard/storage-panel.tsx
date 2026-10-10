"use client";

/**
 * Panneau « Stockage » : jauges des disques remontés par Radarr/Sonarr,
 * avec alerte visuelle au-delà de 90 % d'occupation.
 */
import { HardDrive } from "lucide-react";
import { motion } from "framer-motion";
import { useSystemOverview } from "@/hooks/use-system";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { stagger, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function StoragePanel() {
    const { data, isLoading } = useSystemOverview();
    // Dédoublonnage par capacité+libre (un même FS peut être vu par plusieurs services).
    const disks = Array.from(
        new Map((data?.disks ?? []).map((d) => [`${d.total_bytes}-${d.free_bytes}`, d])).values(),
    ).slice(0, 4);

    return (
        <Panel title="Stockage" icon={HardDrive} iconClassName="text-emerald-300" href="/system" hrefLabel="Serveur">
            {isLoading ? (
                <div className="space-y-4">
                    {[0, 1].map((i) => (
                        <Shimmer key={i} className="h-10" />
                    ))}
                </div>
            ) : disks.length === 0 ? (
                <EmptyState compact icon={HardDrive} title="Aucun disque remonté" description="Radarr/Sonarr n'exposent pas d'espace disque." />
            ) : (
                <motion.ul variants={stagger(0.05, 0.06)} initial="hidden" animate="show" className="space-y-4">
                    {disks.map((d) => {
                        const pct = d.usage_percent;
                        const tone = pct >= 90 ? "rose" : pct >= 75 ? "amber" : "emerald";
                        return (
                            <motion.li key={d.path} variants={fadeUp} className="space-y-1.5">
                                <div className="flex items-baseline justify-between gap-2">
                                    <p className="truncate text-sm font-medium" title={d.path}>
                                        {d.label || d.path}
                                    </p>
                                    <span className={cn("shrink-0 text-xs font-bold tabular-nums", pct >= 90 ? "text-rose-400" : pct >= 75 ? "text-amber-300" : "text-emerald-300")}>
                                        {Math.round(pct)}%
                                    </span>
                                </div>
                                <GradientProgress value={pct} tone={tone} />
                                <p className="text-[11px] text-muted-foreground">
                                    <span className="text-foreground/80">{d.free_human}</span> libres sur {d.total_human}
                                </p>
                            </motion.li>
                        );
                    })}
                </motion.ul>
            )}
        </Panel>
    );
}
