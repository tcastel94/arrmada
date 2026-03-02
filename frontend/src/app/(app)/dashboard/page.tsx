"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Film,
    Tv,
    HardDrive,
    Server,
    Download,
    ShieldCheck,
    Zap,
    ArrowUpRight,
    TrendingUp,
    ChevronRight,
} from "lucide-react";
import { useServices, useGlobalHealth } from "@/hooks/use-services";
import { useDashboardStats } from "@/hooks/use-dashboard";
import { useDownloads } from "@/hooks/use-downloads";
import { useTrashCompliance } from "@/hooks/use-trash-guides";
import { cn } from "@/lib/utils";
import { STATUS_COLORS, SERVICE_META } from "@/lib/constants";
import { motion } from "framer-motion";
import { ActivityFeedCard } from "@/components/dashboard/activity-feed";
import Link from "next/link";

function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

const container = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: { staggerChildren: 0.06 },
    },
};

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

// ── Stat Card Gradients ─────────────────────────────────────

const STAT_CONFIGS = [
    {
        key: "movies",
        label: "Films",
        icon: Film,
        gradient: "from-violet-600/20 via-purple-600/10 to-transparent",
        iconBg: "bg-violet-500/20",
        iconColor: "text-violet-400",
        ring: "ring-violet-500/20",
    },
    {
        key: "series",
        label: "Séries",
        icon: Tv,
        gradient: "from-blue-600/20 via-cyan-600/10 to-transparent",
        iconBg: "bg-blue-500/20",
        iconColor: "text-blue-400",
        ring: "ring-blue-500/20",
    },
    {
        key: "storage",
        label: "Stockage",
        icon: HardDrive,
        gradient: "from-emerald-600/20 via-green-600/10 to-transparent",
        iconBg: "bg-emerald-500/20",
        iconColor: "text-emerald-400",
        ring: "ring-emerald-500/20",
    },
    {
        key: "downloads",
        label: "Downloads",
        icon: Download,
        gradient: "from-amber-600/20 via-yellow-600/10 to-transparent",
        iconBg: "bg-amber-500/20",
        iconColor: "text-amber-400",
        ring: "ring-amber-500/20",
    },
];

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

    const statValues = [
        {
            value: stats?.movies?.total ?? "—",
            sub: stats?.movies ? `${stats.movies.with_files} sur disque` : undefined,
        },
        {
            value: stats?.series?.total ?? "—",
            sub: stats?.series
                ? `${stats.series.have_episodes} / ${stats.series.total_episodes} épisodes`
                : undefined,
        },
        {
            value: stats?.total_size_human ?? "—",
            sub: stats ? `${stats.total_items} fichiers` : undefined,
        },
        {
            value: activeDownloads,
            sub: activeDownloads > 0 ? "en cours" : "file vide",
        },
    ];

    return (
        <>
            <Header title="Dashboard" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* ── Hero Stats ────────────────────────────────── */}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {STAT_CONFIGS.map((cfg, idx) => {
                        const sv = statValues[idx];
                        const Icon = cfg.icon;
                        return (
                            <motion.div key={cfg.key} variants={fadeUp}>
                                <Card
                                    className={cn(
                                        "relative overflow-hidden border-0",
                                        "bg-gradient-to-br",
                                        cfg.gradient,
                                        "backdrop-blur-sm",
                                        "ring-1",
                                        cfg.ring,
                                        "hover:scale-[1.02] transition-transform duration-300"
                                    )}
                                >
                                    <CardContent className="p-5">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                                    {cfg.label}
                                                </p>
                                                <p className="text-3xl font-bold mt-1 tabular-nums tracking-tight">
                                                    {sv.value}
                                                </p>
                                                {sv.sub && (
                                                    <p className="text-xs text-muted-foreground mt-1.5 flex items-center gap-1">
                                                        <TrendingUp className="h-3 w-3" />
                                                        {sv.sub}
                                                    </p>
                                                )}
                                            </div>
                                            <div
                                                className={cn(
                                                    "rounded-xl p-2.5",
                                                    cfg.iconBg
                                                )}
                                            >
                                                <Icon
                                                    className={cn(
                                                        "h-5 w-5",
                                                        cfg.iconColor
                                                    )}
                                                />
                                            </div>
                                        </div>
                                    </CardContent>
                                    {/* Decorative glow */}
                                    <div
                                        className={cn(
                                            "absolute -top-12 -right-12 w-32 h-32 rounded-full blur-3xl opacity-20",
                                            cfg.iconBg
                                        )}
                                    />
                                </Card>
                            </motion.div>
                        );
                    })}
                </div>

                {/* ── Services Health Strip ──────────────────────── */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <CardContent className="p-0">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                    <Server className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-sm font-semibold">
                                        Services
                                    </span>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={cn(
                                        "text-xs tabular-nums",
                                        onlineCount === totalServices
                                            ? "border-emerald-500/30 text-emerald-400"
                                            : "border-amber-500/30 text-amber-400"
                                    )}
                                >
                                    {onlineCount}/{totalServices} en ligne
                                </Badge>
                            </div>
                            {!services || services.length === 0 ? (
                                <div className="p-6">
                                    <EmptyState
                                        icon={Server}
                                        title="Aucun service"
                                        description="Ajoutez vos services *arr"
                                    />
                                </div>
                            ) : (
                                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-0 divide-x divide-white/5">
                                    {services.map((svc) => {
                                        const meta = SERVICE_META[svc.type];
                                        const health = healthResults?.find(
                                            (h) => h.service_id === svc.id
                                        );
                                        const status =
                                            health?.status ?? svc.last_status;
                                        const isOnline = status === "online";

                                        return (
                                            <div
                                                key={svc.id}
                                                className="flex flex-col items-center gap-1.5 py-4 px-3 group hover:bg-white/[0.02] transition-colors relative"
                                            >
                                                {/* Pulse for online */}
                                                <div className="relative">
                                                    <span
                                                        className={cn(
                                                            "block h-3 w-3 rounded-full",
                                                            STATUS_COLORS[status] ??
                                                            STATUS_COLORS.unknown
                                                        )}
                                                    />
                                                    {isOnline && (
                                                        <span
                                                            className={cn(
                                                                "absolute inset-0 rounded-full animate-ping opacity-40",
                                                                STATUS_COLORS[status]
                                                            )}
                                                        />
                                                    )}
                                                </div>
                                                <span className="text-sm font-medium">
                                                    {svc.name}
                                                </span>
                                                <div className="flex items-center gap-1.5">
                                                    {health?.latency_ms != null && (
                                                        <span className="text-[10px] text-muted-foreground tabular-nums">
                                                            {health.latency_ms}ms
                                                        </span>
                                                    )}
                                                    {svc.version && (
                                                        <span className="text-[10px] text-muted-foreground/60 font-mono">
                                                            v{svc.version}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>

                {/* ── Main Content: Activity + Downloads ──────── */}
                <div className="grid gap-5 lg:grid-cols-5">
                    {/* Activity Feed — takes 3 cols */}
                    <motion.div
                        variants={fadeUp}
                        className="lg:col-span-3"
                    >
                        <ActivityFeedCard />
                    </motion.div>

                    {/* Right sidebar — Downloads + Quick Actions */}
                    <motion.div
                        variants={fadeUp}
                        className="lg:col-span-2 space-y-5"
                    >
                        {/* Downloads Queue */}
                        <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                    <div className="flex items-center gap-2">
                                        <Download className="h-4 w-4 text-amber-400" />
                                        <span className="text-sm font-semibold">
                                            Téléchargements
                                        </span>
                                    </div>
                                    {activeDownloads > 0 && (
                                        <Badge className="bg-amber-500/20 text-amber-400 border-0 text-[10px]">
                                            {activeDownloads} actifs
                                        </Badge>
                                    )}
                                </div>
                                <div className="p-4">
                                    {!downloads?.items ||
                                        downloads.items.length === 0 ? (
                                        <div className="flex flex-col items-center py-8 text-muted-foreground">
                                            <Download className="h-8 w-8 mb-2 opacity-20" />
                                            <p className="text-xs">
                                                Aucun téléchargement en cours
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            {downloads.items
                                                .slice(0, 6)
                                                .map((dl) => (
                                                    <div
                                                        key={dl.id}
                                                        className="space-y-1.5"
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <p className="text-sm font-medium truncate max-w-[70%]">
                                                                {dl.title}
                                                            </p>
                                                            <span className="text-xs font-bold tabular-nums">
                                                                {dl.progress.toFixed(
                                                                    0
                                                                )}
                                                                %
                                                            </span>
                                                        </div>
                                                        <div className="relative">
                                                            <Progress
                                                                value={
                                                                    dl.progress
                                                                }
                                                                className="h-1.5 bg-muted/30"
                                                            />
                                                            {/* Gradient overlay */}
                                                            <div
                                                                className="absolute inset-0 h-1.5 rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400 opacity-80"
                                                                style={{
                                                                    width: `${dl.progress}%`,
                                                                }}
                                                            />
                                                        </div>
                                                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                                            <span>
                                                                {
                                                                    dl.source_service
                                                                }
                                                            </span>
                                                            {dl.quality && (
                                                                <Badge
                                                                    variant="outline"
                                                                    className="text-[9px] px-1 py-0 h-3.5"
                                                                >
                                                                    {dl.quality}
                                                                </Badge>
                                                            )}
                                                            {dl.time_left && (
                                                                <span className="ml-auto tabular-nums">
                                                                    ⏱{" "}
                                                                    {
                                                                        dl.time_left
                                                                    }
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* TRaSH Compliance */}
                        {compliance && compliance.length > 0 && (
                            <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                                <CardContent className="p-0">
                                    <Link href="/trash-guides">
                                        <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 group cursor-pointer">
                                            <div className="flex items-center gap-2">
                                                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                                                <span className="text-sm font-semibold">
                                                    TRaSH Guides
                                                </span>
                                            </div>
                                            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                                        </div>
                                    </Link>
                                    <div className="p-4 space-y-3">
                                        {compliance.map((item) => {
                                            const pct = item.compliance_pct;
                                            const color =
                                                pct >= 80
                                                    ? "text-emerald-400"
                                                    : pct >= 50
                                                        ? "text-amber-400"
                                                        : "text-red-400";
                                            const barColor =
                                                pct >= 80
                                                    ? "from-emerald-500 to-emerald-400"
                                                    : pct >= 50
                                                        ? "from-amber-500 to-yellow-400"
                                                        : "from-red-500 to-red-400";

                                            return (
                                                <div
                                                    key={item.service_id}
                                                    className="space-y-1.5"
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <p className="text-sm font-medium">
                                                            {item.service_name}
                                                        </p>
                                                        <span
                                                            className={cn(
                                                                "text-lg font-bold tabular-nums",
                                                                color
                                                            )}
                                                        >
                                                            {item.trash_total >
                                                                0
                                                                ? `${pct}%`
                                                                : "—"}
                                                        </span>
                                                    </div>
                                                    {item.trash_total > 0 && (
                                                        <>
                                                            <div className="relative">
                                                                <Progress
                                                                    value={pct}
                                                                    className="h-1.5 bg-muted/30"
                                                                />
                                                                <div
                                                                    className={cn(
                                                                        "absolute inset-0 h-1.5 rounded-full bg-gradient-to-r opacity-80",
                                                                        barColor
                                                                    )}
                                                                    style={{
                                                                        width: `${pct}%`,
                                                                    }}
                                                                />
                                                            </div>
                                                            <p className="text-[10px] text-muted-foreground">
                                                                {
                                                                    item.trash_found
                                                                }{" "}
                                                                /{" "}
                                                                {
                                                                    item.trash_total
                                                                }{" "}
                                                                CFs ·{" "}
                                                                {item.applied_profiles
                                                                    .slice(0, 2)
                                                                    .map((p) =>
                                                                        p.replace(
                                                                            /-/g,
                                                                            " "
                                                                        )
                                                                    )
                                                                    .join(", ")}
                                                            </p>
                                                        </>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </motion.div>
                </div>
            </motion.div>
        </>
    );
}
