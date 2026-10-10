"use client";

/**
 * Panneau « Conformité TRaSH » : % de Custom Formats TRaSH présents dans
 * chaque service, en jauges circulaires.
 */
import { ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { useTrashCompliance } from "@/hooks/use-trash-guides";
import { Panel } from "@/components/shared/panel";
import { RingGauge } from "@/components/fx/ring-gauge";
import { stagger, scaleIn } from "@/lib/motion";

export function TrashPanel() {
    const { data } = useTrashCompliance();
    const items = (data ?? []).filter((c) => c.trash_total > 0);
    if (items.length === 0) return null;

    return (
        <Panel title="Conformité TRaSH" icon={ShieldCheck} iconClassName="text-orange-300" href="/trash-guides" hrefLabel="Ajuster">
            <motion.div variants={stagger(0.05, 0.08)} initial="hidden" animate="show" className="grid grid-cols-2 gap-4">
                {items.map((c) => {
                    const tone = c.compliance_pct >= 80 ? "emerald" : c.compliance_pct >= 50 ? "amber" : "rose";
                    return (
                        <motion.div key={c.service_id} variants={scaleIn} className="flex flex-col items-center gap-2 text-center">
                            <RingGauge value={c.compliance_pct} size={84} stroke={7} tone={tone}>
                                <span className="text-lg font-bold tabular-nums">{Math.round(c.compliance_pct)}%</span>
                            </RingGauge>
                            <div>
                                <p className="text-sm font-semibold">{c.service_name}</p>
                                <p className="text-[11px] text-muted-foreground tabular-nums">
                                    {c.trash_found}/{c.trash_total} formats
                                </p>
                            </div>
                        </motion.div>
                    );
                })}
            </motion.div>
        </Panel>
    );
}
