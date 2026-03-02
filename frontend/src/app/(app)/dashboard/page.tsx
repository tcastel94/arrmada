"use client";

import { Header } from "@/components/layout/header";
import { StatsCard } from "@/components/shared/stats-card";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Film,
    Tv,
    HardDrive,
    Server,
    Activity,
    Download,
    TrendingUp,
    ShieldCheck,
} from "lucide-react";
import { useServices, useGlobalHealth } from "@/hooks/use-services";
import { useDashboardStats } from "@/hooks/use-dashboard";
import { useDownloads } from "@/hooks/use-downloads";
import { useTrashCompliance } from "@/hooks/use-trash-guides";
import { cn } from "@/lib/utils";
import { STATUS_COLORS, SERVICE_META } from "@/lib/constants";
import { motion } from "framer-motion";
import { ActivityFeedCard } from "@/components/dashboard/activity-feed";

function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function DashboardPage() {
    const { data: services, isLoading: servicesLoading } = useServices();
    const { data: healthResults } = useGlobalHealth();
    const { data: stats, isLoading: statsLoading } = useDashboardStats();
    const { data: downloads } = useDownloads();
    const { data: compliance } = useTrashCompliance();

    if (servicesLoading && statsLoading) {
        return (
            <>
                <Header title="Dashboard" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    const onlineCount =
        healthResults?.filter((h) => h.status === "online").length ?? 0;
    const totalServices = services?.length ?? 0;
    const activeDownloads = downloads?.items?.length ?? 0;

    return (
        <>
            <Header title="Dashboard" />
            <div className="p-6 space-y-6">
                {/* Stats Row */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <StatsCard
                        title="Films"
                        value={stats?.movies?.total ?? "—"}
                        icon={Film}
                        trend={
                            stats?.movies
                                ? {
                                    value: stats.movies.with_files,
                                    label: `sur disque`,
                                }
                                : undefined
                        }
                    />
                    <StatsCard
                        title="Séries"
                        value={stats?.series?.total ?? "—"}
                        icon={Tv}
                        trend={
                            stats?.series
                                ? {
                                    value: stats.series.have_episodes,
                                    label: `/ ${stats.series.total_episodes} épisodes`,
                                }
                                : undefined
                        }
                    />
                    <StatsCard
                        title="Stockage"
                        value={stats?.total_size_human ?? "—"}
                        icon={HardDrive}
                        trend={
                            stats
                                ? {
                                    value: stats.total_items,
                                    label: "items total",
                                }
                                : undefined
                        }
                    />
                    <StatsCard
                        title="Downloads"
                        value={activeDownloads}
                        icon={Download}
                        trend={
                            activeDownloads > 0
                                ? { value: activeDownloads, label: "en cours" }
                                : undefined
                        }
                    />
                </div>

                {/* Health & Activity Row */}
                <div className="grid gap-6 lg:grid-cols-3">
                    {/* Service Health */}
                    <Card className="lg:col-span-1">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base font-semibold flex items-center gap-2">
                                    <Server className="h-4 w-4" />
                                    Services
                                </CardTitle>
                                <Badge variant="outline" className="text-xs">
                                    {onlineCount}/{totalServices} en ligne
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-1">
                            {!services || services.length === 0 ? (
                                <EmptyState
                                    icon={Server}
                                    title="Aucun service"
                                    description="Ajoutez vos services *arr dans la section Services"
                                />
                            ) : (
                                services.map((svc) => {
                                    const meta = SERVICE_META[svc.type];
                                    const health = healthResults?.find(
                                        (h) => h.service_id === svc.id
                                    );
                                    const status = health?.status ?? svc.last_status;

                                    return (
                                        <motion.div
                                            key={svc.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="flex items-center justify-between py-2.5 px-3 rounded-md hover:bg-muted/50 transition-colors"
                                        >
                                            <div className="flex items-center gap-3">
                                                <span
                                                    className={cn(
                                                        "h-2.5 w-2.5 rounded-full",
                                                        STATUS_COLORS[status] ?? STATUS_COLORS.unknown
                                                    )}
                                                />
                                                <div>
                                                    <span className="text-sm font-medium">
                                                        {svc.name}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground ml-2">
                                                        {meta?.label}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {health?.latency_ms != null && (
                                                    <span className="text-xs text-muted-foreground tabular-nums">
                                                        {health.latency_ms}ms
                                                    </span>
                                                )}
                                                {svc.version && (
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs font-mono"
                                                    >
                                                        v{svc.version}
                                                    </Badge>
                                                )}
                                            </div>
                                        </motion.div>
                                    );
                                })
                            )}
                        </CardContent>
                    </Card>

                    {/* Downloads Queue */}
                    <Card className="lg:col-span-2">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <Activity className="h-4 w-4" />
                                Téléchargements en cours
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {!downloads?.items || downloads.items.length === 0 ? (
                                <EmptyState
                                    icon={Download}
                                    title="Aucun téléchargement"
                                    description="La queue est vide — rien à télécharger pour l'instant"
                                />
                            ) : (
                                <div className="space-y-3">
                                    {downloads.items.slice(0, 8).map((dl) => (
                                        <div
                                            key={dl.id}
                                            className="flex items-center gap-4 py-2 px-3 rounded-md hover:bg-muted/50 transition-colors"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">
                                                    {dl.title}
                                                </p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-xs text-muted-foreground">
                                                        {dl.source_service}
                                                    </span>
                                                    {dl.quality && (
                                                        <Badge variant="outline" className="text-xs">
                                                            {dl.quality}
                                                        </Badge>
                                                    )}
                                                    {dl.time_left && (
                                                        <span className="text-xs text-muted-foreground">
                                                            {dl.time_left}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="w-24 flex flex-col items-end gap-1">
                                                <span className="text-xs font-medium tabular-nums">
                                                    {dl.progress.toFixed(0)}%
                                                </span>
                                                <Progress value={dl.progress} className="h-1.5" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Activity Feed */}
                <ActivityFeedCard />

                {/* TRaSH Compliance Row */}
                {compliance && compliance.length > 0 && (
                    <Card>
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base font-semibold flex items-center gap-2">
                                    <ShieldCheck className="h-4 w-4" />
                                    Conformité TRaSH Guides
                                </CardTitle>
                                <a href="/trash-guides" className="text-xs text-primary hover:underline">
                                    Voir détails →
                                </a>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="grid gap-4 sm:grid-cols-2">
                                {compliance.map((item) => {
                                    const color =
                                        item.compliance_pct >= 80
                                            ? "text-emerald-500"
                                            : item.compliance_pct >= 50
                                                ? "text-yellow-500"
                                                : "text-red-500";
                                    const bgColor =
                                        item.compliance_pct >= 80
                                            ? "bg-emerald-500"
                                            : item.compliance_pct >= 50
                                                ? "bg-yellow-500"
                                                : "bg-red-500";

                                    return (
                                        <motion.div
                                            key={item.service_id}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="p-4 rounded-lg border bg-card"
                                        >
                                            <div className="flex items-center justify-between mb-3">
                                                <div>
                                                    <p className="text-sm font-medium">
                                                        {item.service_name}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {item.applied_profiles.length > 0
                                                            ? (() => {
                                                                const names = item.applied_profiles.map(p => p.replace(/-/g, ' '));
                                                                const shown = names.slice(0, 2).join(', ');
                                                                return names.length > 2 ? `${shown} +${names.length - 2}` : shown;
                                                            })()
                                                            : "Aucun profil détecté"}
                                                    </p>
                                                </div>
                                                <span
                                                    className={cn(
                                                        "text-2xl font-bold tabular-nums",
                                                        color
                                                    )}
                                                >
                                                    {item.trash_total > 0 ? `${item.compliance_pct}%` : "—"}
                                                </span>
                                            </div>
                                            {item.trash_total > 0 ? (
                                                <>
                                                    <Progress
                                                        value={item.compliance_pct}
                                                        className={cn("h-2 [&>div]:" + bgColor)}
                                                    />
                                                    <p className="text-xs text-muted-foreground mt-2">
                                                        {item.trash_found} / {item.trash_total} CFs conformes
                                                    </p>
                                                </>
                                            ) : (
                                                <p className="text-xs text-muted-foreground">
                                                    Appliquez un profil TRaSH pour voir la conformité
                                                </p>
                                            )}
                                        </motion.div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </>
    );
}
