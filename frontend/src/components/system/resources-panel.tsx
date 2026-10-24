"use client";

/**
 * Onglet « Ressources » de /system : RAM, CPU, charge, disponibilité,
 * disques, et renvoi vers le Salon pour la lecture en cours.
 * ----------------------------------------------------------------
 * - Rafraîchi toutes les 15 s (l'ancienne page ne relisait jamais rien).
 * - CPU : /proc/stat ne donne que des compteurs cumulés ; la charge (%)
 *   est calculée entre deux relevés successifs. Tant qu'on n'a qu'un
 *   relevé, on n'invente rien (« mesure en cours »).
 * - Disques : un même volume vu sous plusieurs chemins (Sonarr /tv,
 *   Radarr /movies…) n'est affiché qu'une fois ; alerte au-delà de 90 %.
 * - La section « En cours de lecture » (doublon du Salon) est remplacée
 *   par un lien vers /remote.
 */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Cpu, Gauge, HardDrive, MemoryStick, Power, Sofa, type LucideIcon } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { RingGauge, type GaugeTone } from "@/components/fx/ring-gauge";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { StatusDot } from "@/components/fx/status-dot";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import {
    cpuPercentBetween,
    groupDisks,
    useDiskSpace,
    useSystemResources,
    type CpuTicks,
    type DiskGroup,
} from "@/hooks/use-system";
import { formatBytes, formatLongDateTime, plural } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Seuils d'alerte communs (RAM, disques). */
export function usageTone(pct: number): GaugeTone {
    if (pct > 90) return "rose";
    if (pct > 75) return "amber";
    return "emerald";
}

/** Durée de fonctionnement avec les jours (formatDuration s'arrête aux heures). */
function formatUptime(seconds: number): string {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d} j ${h} h`;
    if (h > 0) return `${h} h ${String(m).padStart(2, "0")}`;
    return `${m} min`;
}

/**
 * Charge CPU (%) calculée entre deux relevés successifs. `pct` reste null
 * tant qu'on n'a pas deux relevés différents ; `stalled` passe à true si
 * plusieurs relevés d'affilée sont identiques (compteurs figés : la
 * mesure est alors impossible, on le dit plutôt que d'attendre en vain).
 */
export function useCpuPercent(cpu: CpuTicks | undefined): { pct: number | null; stalled: boolean } {
    const prev = useRef<CpuTicks | undefined>(undefined);
    const samples = useRef(0);
    const [pct, setPct] = useState<number | null>(null);
    const [stalled, setStalled] = useState(false);
    useEffect(() => {
        if (!cpu) return;
        samples.current += 1;
        const value = cpuPercentBetween(prev.current, cpu);
        if (value !== null) {
            setPct(value);
            setStalled(false);
        } else if (samples.current >= 3) {
            setStalled(true);
        }
        prev.current = cpu;
    }, [cpu]);
    return { pct, stalled };
}

export function ResourcesPanel() {
    const resources = useSystemResources();
    const disks = useDiskSpace();
    const res = resources.data;
    const { pct: cpuPct, stalled: cpuStalled } = useCpuPercent(res?.cpu);
    const groups = groupDisks(disks.data?.disks ?? []);
    const critical = groups.filter((g) => g.usage_percent > 90);

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            {/* Ressources de l'hôte */}
            <motion.div variants={fadeUp}>
                <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-sm font-semibold tracking-tight">Ressources du serveur</h2>
                    {res?.available && (
                        <span className="flex items-center gap-2 text-[11px] text-muted-foreground">
                            <StatusDot tone="online" size="sm" />
                            En direct · toutes les 15 s
                        </span>
                    )}
                </div>
                {resources.isLoading ? (
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Shimmer key={i} className="h-40 rounded-2xl" />
                        ))}
                    </div>
                ) : resources.isError && !res ? (
                    <Panel>
                        <ErrorState compact error={resources.error} onRetry={() => resources.refetch()} title="Ressources indisponibles" />
                    </Panel>
                ) : !res?.available ? (
                    <Panel>
                        <EmptyState
                            compact
                            icon={Cpu}
                            title="Mesures de l'hôte indisponibles"
                            description="Le backend ne peut pas lire /proc (il ne tourne probablement pas sous Linux)."
                        />
                    </Panel>
                ) : (
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        {res.memory && (
                            <GaugeCard
                                icon={MemoryStick}
                                label="Mémoire vive"
                                value={res.memory.usage_percent}
                                tone={usageTone(res.memory.usage_percent)}
                                detail={`${formatBytes(res.memory.used_bytes)} sur ${formatBytes(res.memory.total_bytes)}`}
                                sub={`${formatBytes(res.memory.free_bytes)} disponibles`}
                            />
                        )}
                        {res.cpu && (
                            <GaugeCard
                                icon={Cpu}
                                label="Processeur"
                                value={cpuPct}
                                tone={cpuPct === null ? "primary" : usageTone(cpuPct)}
                                detail={plural(res.cpu.cores, "cœur")}
                                sub={
                                    cpuPct !== null
                                        ? "Moyenne sur les 15 dernières secondes"
                                        : cpuStalled
                                          ? "Charge non mesurable : les compteurs CPU ne bougent pas"
                                          : "Mesure en cours (2 relevés nécessaires)…"
                                }
                            />
                        )}
                        {res.load_average && res.cpu && (
                            <LoadCard load={res.load_average} cores={res.cpu.cores} />
                        )}
                        {res.uptime && (
                            <InfoCard
                                icon={Power}
                                label="Allumé depuis"
                                value={formatUptime(res.uptime.seconds)}
                                sub={`Démarré ${formatLongDateTime(Date.now() - res.uptime.seconds * 1000)}`}
                            />
                        )}
                    </div>
                )}
            </motion.div>

            {/* Disques */}
            <motion.div variants={fadeUp}>
                <Panel
                    title="Espace disque"
                    icon={HardDrive}
                    iconClassName="text-primary"
                    action={
                        groups.length > 0 ? (
                            <span className="text-xs text-muted-foreground tabular-nums">
                                {formatBytes(groups.reduce((s, g) => s + g.free_bytes, 0))} libres au total
                            </span>
                        ) : undefined
                    }
                >
                    {disks.isLoading ? (
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Shimmer key={i} className="h-32 rounded-2xl" />
                            ))}
                        </div>
                    ) : disks.isError && !disks.data ? (
                        <ErrorState compact error={disks.error} onRetry={() => disks.refetch()} title="Espace disque indisponible" />
                    ) : groups.length === 0 ? (
                        <EmptyState
                            compact
                            icon={HardDrive}
                            title="Aucun disque remonté"
                            description="Les disques sont lus via Sonarr et Radarr : vérifie qu'ils sont configurés."
                        />
                    ) : (
                        <div className="space-y-4">
                            {critical.length > 0 && (
                                <div className="flex items-start gap-3 rounded-xl bg-destructive/10 p-3 text-sm ring-1 ring-destructive/25">
                                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                                    <p>
                                        <span className="font-semibold text-destructive">
                                            {critical.length === 1 ? "Un disque est presque plein" : `${critical.length} disques sont presque pleins`}
                                        </span>{" "}
                                        <span className="text-muted-foreground">
                                            ({critical.map((c) => c.label).join(", ")}). Les téléchargements risquent d&apos;échouer : fais
                                            de la place depuis{" "}
                                            <Link href="/health?tab=cleanup" className="text-primary hover:underline">
                                                Santé médiathèque › Nettoyage
                                            </Link>
                                            .
                                        </span>
                                    </p>
                                </div>
                            )}
                            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                                {groups.map((g) => (
                                    <DiskCard key={g.key} disk={g} />
                                ))}
                            </ul>
                        </div>
                    )}
                </Panel>
            </motion.div>

            {/* Renvoi vers le Salon */}
            <motion.div variants={fadeUp}>
                <Link
                    href="/remote"
                    className="glass glass-hover group flex items-center gap-4 rounded-2xl p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-fuchsia-500/10 text-primary ring-1 ring-primary/30">
                        <Sofa className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold">Lecture en cours et télécommandes</span>
                        <span className="block text-xs text-muted-foreground">
                            Les sessions Kodi et l&apos;ampli se pilotent désormais depuis le Salon.
                        </span>
                    </span>
                    <Button asChild variant="ghost" size="sm" className="pointer-events-none hidden sm:inline-flex">
                        <span>
                            Ouvrir le Salon
                            <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
                        </span>
                    </Button>
                    <ArrowRight className="h-4 w-4 text-muted-foreground sm:hidden" />
                </Link>
            </motion.div>
        </motion.div>
    );
}

/* ── Cartes ────────────────────────────────────────────────── */

function CardShell({ icon: Icon, label, children }: { icon: LucideIcon; label: string; children: React.ReactNode }) {
    return (
        <div className="glass spotlight flex h-full flex-col rounded-2xl p-4">
            <div className="mb-3 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/25">
                    <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="text-xs font-medium text-muted-foreground">{label}</span>
            </div>
            {children}
        </div>
    );
}

function GaugeCard({
    icon,
    label,
    value,
    tone,
    detail,
    sub,
}: {
    icon: LucideIcon;
    label: string;
    value: number | null;
    tone: GaugeTone;
    detail: string;
    sub: string;
}) {
    return (
        <CardShell icon={icon} label={label}>
            <div className="flex items-center gap-4">
                <RingGauge value={value ?? 0} size={76} stroke={7} tone={tone}>
                    {value === null ? (
                        <Gauge className="h-4 w-4 animate-pulse text-muted-foreground" />
                    ) : (
                        <span className="text-sm font-bold">
                            <AnimatedNumber value={Math.round(value)} suffix=" %" />
                        </span>
                    )}
                </RingGauge>
                <div className="min-w-0">
                    <p className="text-sm font-semibold">{detail}</p>
                    <p className="text-[11px] text-muted-foreground">{sub}</p>
                </div>
            </div>
        </CardShell>
    );
}

function LoadCard({ load, cores }: { load: { "1min": number; "5min": number; "15min": number }; cores: number }) {
    // La charge Linux se lit par rapport au nombre de cœurs : 4,0 sur 4
    // cœurs = processeur occupé à 100 %.
    const ratio = (load["1min"] / Math.max(1, cores)) * 100;
    const tone = ratio > 100 ? "rose" : ratio > 75 ? "amber" : "emerald";
    return (
        <CardShell icon={Gauge} label="Charge moyenne">
            <div className="grid grid-cols-3 gap-2">
                {(["1min", "5min", "15min"] as const).map((k, i) => (
                    <div key={k}>
                        <p className={cn("text-lg font-bold tabular-nums", i === 0 ? "text-foreground" : "text-muted-foreground")}>
                            {load[k].toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </p>
                        <p className="text-[10px] text-muted-foreground">{k.replace("min", " min")}</p>
                    </div>
                ))}
            </div>
            <GradientProgress value={Math.min(100, ratio)} tone={tone} className="mt-3" glow={false} />
            <p className="mt-1.5 text-[11px] text-muted-foreground">
                {Math.round(ratio)} % de la capacité ({plural(cores, "cœur")})
            </p>
        </CardShell>
    );
}

function InfoCard({ icon, label, value, sub }: { icon: LucideIcon; label: string; value: string; sub: string }) {
    return (
        <CardShell icon={icon} label={label}>
            <p className="text-2xl font-bold tracking-tight">{value}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">{sub}</p>
        </CardShell>
    );
}

function DiskCard({ disk }: { disk: DiskGroup }) {
    const tone = usageTone(disk.usage_percent);
    const alert = disk.usage_percent > 90;
    return (
        <li
            className={cn(
                "flex items-center gap-4 rounded-2xl bg-white/[0.025] p-4 ring-1 transition-colors",
                alert ? "ring-destructive/30" : "ring-white/[0.06] hover:ring-white/[0.12]",
            )}
        >
            <RingGauge value={disk.usage_percent} size={72} stroke={7} tone={tone}>
                <span className="text-xs font-bold tabular-nums">{Math.round(disk.usage_percent)} %</span>
            </RingGauge>
            <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate text-sm font-semibold">
                    {alert && <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />}
                    <span className="truncate" title={disk.label}>
                        {disk.label}
                    </span>
                </p>
                <p className="truncate font-mono text-[10px] text-muted-foreground" title={disk.paths.join("\n")}>
                    {disk.paths.join(" · ")}
                </p>
                <p className="mt-1.5 text-xs tabular-nums">
                    <span className="font-semibold">{formatBytes(disk.free_bytes)}</span>
                    <span className="text-muted-foreground"> libres sur {formatBytes(disk.total_bytes)}</span>
                </p>
                <p className="text-[10px] text-muted-foreground/80">via {disk.services.join(", ")}</p>
            </div>
        </li>
    );
}
