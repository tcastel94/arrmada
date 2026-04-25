"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    HardDrive,
    Cpu,
    MemoryStick,
    Clock,
    Activity,
    Play,
    Pause,
    Monitor,
} from "lucide-react";
import { useSystemOverview, useKodiSessions, DiskInfo, KodiSession } from "@/hooks/use-new-features";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

function DiskCard({ disk }: { disk: DiskInfo }) {
    const color = disk.usage_percent > 90
        ? "from-red-500 to-red-400"
        : disk.usage_percent > 75
            ? "from-amber-500 to-yellow-400"
            : "from-emerald-500 to-emerald-400";

    const textColor = disk.usage_percent > 90
        ? "text-red-400"
        : disk.usage_percent > 75
            ? "text-amber-400"
            : "text-emerald-400";

    return (
        <div className="space-y-2 p-4 rounded-lg bg-white/[0.02] ring-1 ring-white/5">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <HardDrive className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium truncate max-w-[200px]" title={disk.path}>
                        {disk.label || disk.path}
                    </span>
                </div>
                <span className={cn("text-lg font-bold tabular-nums", textColor)}>
                    {disk.usage_percent}%
                </span>
            </div>
            <div className="relative">
                <Progress value={disk.usage_percent} className="h-2 bg-muted/30" />
                <div
                    className={cn("absolute inset-0 h-2 rounded-full bg-gradient-to-r opacity-80", color)}
                    style={{ width: `${disk.usage_percent}%` }}
                />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>{disk.used_human} utilisé</span>
                <span>{disk.free_human} libre</span>
                <span>{disk.total_human} total</span>
            </div>
        </div>
    );
}

function KodiSessionCard({ session }: { session: KodiSession }) {
    const elapsed = `${Math.floor(session.elapsed_seconds / 3600)}:${String(Math.floor((session.elapsed_seconds % 3600) / 60)).padStart(2, "0")}:${String(session.elapsed_seconds % 60).padStart(2, "0")}`;
    const total = `${Math.floor(session.total_seconds / 3600)}:${String(Math.floor((session.total_seconds % 3600) / 60)).padStart(2, "0")}:${String(session.total_seconds % 60).padStart(2, "0")}`;

    return (
        <div className="p-4 rounded-lg bg-gradient-to-br from-orange-600/10 via-amber-600/5 to-transparent ring-1 ring-orange-500/20">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Monitor className="h-4 w-4 text-orange-400" />
                    <span className="text-xs font-medium text-orange-400">{session.instance}</span>
                </div>
                {session.is_paused ? (
                    <Badge className="bg-amber-500/20 text-amber-400 border-0 text-[10px]">
                        <Pause className="h-3 w-3 mr-0.5" /> Pause
                    </Badge>
                ) : (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">
                        <Play className="h-3 w-3 mr-0.5" /> En cours
                    </Badge>
                )}
            </div>
            <p className="text-sm font-semibold truncate">{session.title}</p>
            <div className="mt-2 space-y-1">
                <div className="relative">
                    <Progress value={session.progress_percent} className="h-1.5 bg-muted/30" />
                    <div
                        className="absolute inset-0 h-1.5 rounded-full bg-gradient-to-r from-orange-500 to-amber-400 opacity-80"
                        style={{ width: `${session.progress_percent}%` }}
                    />
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
                    <span>{elapsed}</span>
                    <span>{session.progress_percent.toFixed(1)}%</span>
                    <span>{total}</span>
                </div>
            </div>
        </div>
    );
}

export default function SystemPage() {
    const { data, isLoading } = useSystemOverview();
    const { data: kodiData } = useKodiSessions();

    if (isLoading) {
        return (
            <>
                <Header title="Système" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    const resources = data?.resources as Record<string, any> ?? {};
    const memory = resources.memory as Record<string, any> | undefined;
    const loadAvg = resources.load_average as Record<string, number> | undefined;
    const uptime = resources.uptime as Record<string, any> | undefined;
    const sessions = kodiData?.sessions ?? data?.kodi_sessions ?? [];

    return (
        <>
            <Header title="Système" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-cyan-600/20 via-teal-600/10 to-transparent p-6 ring-1 ring-cyan-500/20">
                        <div className="flex items-center gap-3">
                            <div className="rounded-xl p-2.5 bg-cyan-500/20">
                                <Activity className="h-6 w-6 text-cyan-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold">Moniteur système</h2>
                                <p className="text-sm text-muted-foreground">
                                    Disques, ressources et sessions Kodi
                                </p>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-cyan-500/30" />
                    </div>
                </motion.div>

                {/* Resource Stats (if available) */}
                {resources.available && (
                    <motion.div variants={fadeUp}>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            {/* Memory */}
                            {memory && (
                                <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-blue-600/10 to-transparent">
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <MemoryStick className="h-4 w-4 text-blue-400" />
                                                <span className="text-xs font-medium text-muted-foreground">RAM</span>
                                            </div>
                                            <span className="text-lg font-bold text-blue-400 tabular-nums">
                                                {memory.usage_percent}%
                                            </span>
                                        </div>
                                        <div className="relative">
                                            <Progress value={memory.usage_percent as number} className="h-1.5" />
                                            <div
                                                className="absolute inset-0 h-1.5 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 opacity-80"
                                                style={{ width: `${memory.usage_percent}%` }}
                                            />
                                        </div>
                                        <p className="text-[10px] text-muted-foreground mt-1">
                                            {memory.used_human} / {memory.total_human}
                                        </p>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Load Average */}
                            {loadAvg && (
                                <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-purple-600/10 to-transparent">
                                    <CardContent className="p-4">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Cpu className="h-4 w-4 text-purple-400" />
                                            <span className="text-xs font-medium text-muted-foreground">Load Average</span>
                                        </div>
                                        <div className="flex gap-3 tabular-nums">
                                            <div>
                                                <p className="text-lg font-bold text-purple-400">{loadAvg["1min"]?.toFixed(2)}</p>
                                                <p className="text-[10px] text-muted-foreground">1 min</p>
                                            </div>
                                            <div>
                                                <p className="text-lg font-bold text-purple-300">{loadAvg["5min"]?.toFixed(2)}</p>
                                                <p className="text-[10px] text-muted-foreground">5 min</p>
                                            </div>
                                            <div>
                                                <p className="text-lg font-bold text-purple-200">{loadAvg["15min"]?.toFixed(2)}</p>
                                                <p className="text-[10px] text-muted-foreground">15 min</p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Uptime */}
                            {uptime && (
                                <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-emerald-600/10 to-transparent">
                                    <CardContent className="p-4">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Clock className="h-4 w-4 text-emerald-400" />
                                            <span className="text-xs font-medium text-muted-foreground">Uptime</span>
                                        </div>
                                        <p className="text-lg font-bold text-emerald-400">{uptime.human}</p>
                                    </CardContent>
                                </Card>
                            )}

                            {/* CPU Cores */}
                            {resources.cpu && (
                                <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-amber-600/10 to-transparent">
                                    <CardContent className="p-4">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Cpu className="h-4 w-4 text-amber-400" />
                                            <span className="text-xs font-medium text-muted-foreground">CPU</span>
                                        </div>
                                        <p className="text-lg font-bold text-amber-400">{(resources.cpu as any).cores} cœurs</p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    </motion.div>
                )}

                {/* Kodi Sessions */}
                {sessions.length > 0 && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-orange-500/20 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                    <Monitor className="h-4 w-4 text-orange-400" />
                                    <span className="text-sm font-semibold">En cours de lecture</span>
                                    <Badge className="bg-orange-500/20 text-orange-400 border-0 text-[10px]">
                                        {sessions.length} session{sessions.length > 1 ? "s" : ""}
                                    </Badge>
                                </div>
                                <div className="grid gap-3 p-4 sm:grid-cols-2">
                                    {sessions.map((session: KodiSession, idx: number) => (
                                        <KodiSessionCard key={idx} session={session} />
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}

                {/* Disk Space */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                        <CardContent className="p-0">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                    <HardDrive className="h-4 w-4 text-cyan-400" />
                                    <span className="text-sm font-semibold">Espace disque</span>
                                </div>
                            </div>
                            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
                                {(data?.disks ?? []).map((disk: DiskInfo, idx: number) => (
                                    <DiskCard key={idx} disk={disk} />
                                ))}
                                {(!data?.disks || data.disks.length === 0) && (
                                    <div className="col-span-full text-center py-8 text-muted-foreground text-sm">
                                        Aucune information de disque disponible
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </motion.div>
        </>
    );
}
