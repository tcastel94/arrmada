"use client";

/**
 * Bandeau d'état des services *arr : une pastille par service avec voyant
 * pulsé, latence et version. Clic → page de configuration des services.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Server, Settings2 } from "lucide-react";
import { useServices, useGlobalHealth } from "@/hooks/use-services";
import { SERVICE_META } from "@/lib/constants";
import { StatusDot } from "@/components/fx/status-dot";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { stagger, scaleIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<string, string> = {
    online: "En ligne",
    offline: "Hors ligne",
    degraded: "Dégradé",
    unknown: "Inconnu",
};

export function ServicesStrip() {
    const { data: services, isLoading } = useServices();
    const { data: health } = useGlobalHealth();

    // Seuls les services *arr connus (Kodi/Yamaha sont des appareils, pas des services).
    const list = (services ?? []).filter((s) => s.type in SERVICE_META);
    const statusOf = (id: number, fallback: string) => health?.find((h) => h.service_id === id)?.status ?? fallback;
    const online = list.filter((s) => statusOf(s.id, s.last_status) === "online").length;
    const allGood = list.length > 0 && online === list.length;

    return (
        <Panel
            title="Services"
            icon={Server}
            iconClassName={allGood ? "text-emerald-400" : "text-amber-400"}
            action={
                list.length > 0 && (
                    <span
                        className={cn(
                            "rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums",
                            allGood ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300",
                        )}
                    >
                        {online}/{list.length} en ligne
                    </span>
                )
            }
            href="/settings/services"
            hrefLabel="Gérer"
            bodyClassName="p-3"
        >
            {isLoading ? (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Shimmer key={i} className="h-[72px]" />
                    ))}
                </div>
            ) : list.length === 0 ? (
                <EmptyState
                    compact
                    icon={Settings2}
                    title="Aucun service connecté"
                    description="Ajoute Radarr, Sonarr, Prowlarr… pour remplir ton tableau de bord."
                    action={{ label: "Ajouter un service", href: "/settings/services" }}
                />
            ) : (
                <motion.div
                    variants={stagger(0.1, 0.05)}
                    initial="hidden"
                    animate="show"
                    className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6"
                >
                    {list.map((svc) => {
                        const meta = SERVICE_META[svc.type];
                        const h = health?.find((x) => x.service_id === svc.id);
                        const status = h?.status ?? svc.last_status ?? "unknown";
                        const latency = h?.latency_ms ?? svc.last_latency_ms;
                        return (
                            <motion.div key={svc.id} variants={scaleIn}>
                                <Link
                                    href="/settings/services"
                                    className="group relative flex h-full items-center gap-3 overflow-hidden rounded-xl border border-white/[0.06] bg-background/40 p-3 transition-all hover:-translate-y-0.5 hover:border-white/[0.12]"
                                    style={{ boxShadow: status === "online" ? undefined : "inset 0 0 0 1px rgb(239 68 68 / 0.15)" }}
                                >
                                    {/* Lueur aux couleurs du service */}
                                    <span
                                        aria-hidden
                                        className="absolute -left-6 -top-6 h-16 w-16 rounded-full opacity-25 blur-xl transition-opacity group-hover:opacity-50"
                                        style={{ background: meta.color }}
                                    />
                                    <StatusDot tone={status} size="md" className="relative" />
                                    <div className="relative min-w-0">
                                        <p className="truncate text-sm font-semibold">{svc.name}</p>
                                        <p className="truncate text-[11px] text-muted-foreground">
                                            {status === "online" && latency != null ? (
                                                <span className="tabular-nums">{latency} ms</span>
                                            ) : (
                                                <span className={status === "offline" ? "text-red-400" : ""}>{STATUS_LABEL[status] ?? status}</span>
                                            )}
                                            {svc.version && <span className="font-mono text-muted-foreground/60"> · v{svc.version}</span>}
                                        </p>
                                    </div>
                                </Link>
                            </motion.div>
                        );
                    })}
                </motion.div>
            )}
        </Panel>
    );
}
