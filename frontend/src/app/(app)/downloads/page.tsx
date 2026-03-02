"use client";

import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Download,
    ArrowDownToLine,
    Pause,
    Clock,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    HardDrive,
    Zap,
    RefreshCw,
} from "lucide-react";
import { useDownloads } from "@/hooks/use-downloads";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

const STATUS_CONFIGS: Record<string, { icon: any; color: string; gradient: string; label: string }> = {
    downloading: {
        icon: ArrowDownToLine,
        color: "text-blue-400",
        gradient: "from-blue-500/20 to-cyan-500/10",
        label: "Téléchargement",
    },
    completed: {
        icon: CheckCircle2,
        color: "text-emerald-400",
        gradient: "from-emerald-500/20 to-green-500/10",
        label: "Terminé",
    },
    paused: {
        icon: Pause,
        color: "text-amber-400",
        gradient: "from-amber-500/20 to-yellow-500/10",
        label: "En pause",
    },
    queued: {
        icon: Clock,
        color: "text-slate-400",
        gradient: "from-slate-500/20 to-slate-500/10",
        label: "En attente",
    },
    warning: {
        icon: AlertTriangle,
        color: "text-orange-400",
        gradient: "from-orange-500/20 to-orange-500/10",
        label: "Avertissement",
    },
    failed: {
        icon: XCircle,
        color: "text-red-400",
        gradient: "from-red-500/20 to-red-500/10",
        label: "Échec",
    },
};

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

export default function DownloadsPage() {
    const { data, isLoading, isFetching } = useDownloads();

    return (
        <>
            <Header title="Downloads" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-cyan-600/20 via-blue-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="rounded-xl bg-cyan-500/20 p-3">
                                    <Download className="h-6 w-6 text-cyan-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold tracking-tight">
                                        Téléchargements
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">
                                        Queue de téléchargement unifiée de tous vos services
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                {isFetching && (
                                    <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                                )}
                                {data && data.total > 0 && (
                                    <Badge className="bg-cyan-500/20 text-cyan-400 border-0 gap-1.5 px-3 py-1">
                                        <Zap className="h-3 w-3" />
                                        {data.total} actif{data.total > 1 ? "s" : ""}
                                    </Badge>
                                )}
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-cyan-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Downloads List */}
                {isLoading ? (
                    <div className="space-y-3">
                        {[...Array(5)].map((_, i) => (
                            <div
                                key={i}
                                className="h-24 rounded-xl bg-muted/20 animate-pulse ring-1 ring-white/5"
                            />
                        ))}
                    </div>
                ) : !data || data.items.length === 0 ? (
                    <motion.div variants={fadeUp}>
                        <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                            <EmptyState
                                icon={Download}
                                title="Aucun téléchargement en cours"
                                description="La queue est vide — les téléchargements actifs apparaîtront ici"
                            />
                        </div>
                    </motion.div>
                ) : (
                    <motion.div className="space-y-2" variants={container}>
                        {data.items.map((dl, idx) => {
                            const cfg =
                                STATUS_CONFIGS[dl.status.toLowerCase()] ||
                                STATUS_CONFIGS.queued;
                            const StatusIcon = cfg.icon;

                            return (
                                <motion.div key={dl.id} variants={fadeUp}>
                                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden hover:ring-white/10 transition-all">
                                        <CardContent className="p-0">
                                            <div className="flex items-center gap-4 p-4">
                                                {/* Status icon */}
                                                <div
                                                    className={cn(
                                                        "rounded-lg p-2.5 bg-gradient-to-br shrink-0",
                                                        cfg.gradient
                                                    )}
                                                >
                                                    <StatusIcon
                                                        className={cn(
                                                            "h-4 w-4",
                                                            cfg.color
                                                        )}
                                                    />
                                                </div>

                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-semibold truncate">
                                                        {dl.title}
                                                    </p>
                                                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                                                        <Badge
                                                            variant="outline"
                                                            className={cn(
                                                                "text-[10px] px-1.5 py-0 h-4 gap-1 border-0",
                                                                cfg.color,
                                                                cfg.gradient.replace("from-", "bg-").split(" ")[0] + "/20"
                                                            )}
                                                        >
                                                            {cfg.label}
                                                        </Badge>
                                                        <span className="text-xs text-muted-foreground">
                                                            {dl.source_service}
                                                        </span>
                                                        {dl.quality && (
                                                            <Badge
                                                                variant="outline"
                                                                className="text-[10px] px-1.5 h-4"
                                                            >
                                                                {dl.quality}
                                                            </Badge>
                                                        )}
                                                        {dl.indexer && (
                                                            <span className="text-[10px] text-muted-foreground/50">
                                                                via {dl.indexer}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Size */}
                                                <div className="text-right shrink-0 hidden sm:block">
                                                    <p className="text-xs text-muted-foreground flex items-center gap-1 justify-end">
                                                        <HardDrive className="h-3 w-3" />
                                                        {formatBytes(
                                                            dl.size_bytes -
                                                            dl.size_left_bytes
                                                        )}{" "}
                                                        / {formatBytes(dl.size_bytes)}
                                                    </p>
                                                    {dl.time_left && (
                                                        <p className="text-[10px] text-muted-foreground/60 mt-0.5 flex items-center gap-1 justify-end">
                                                            <Clock className="h-2.5 w-2.5" />
                                                            {dl.time_left}
                                                        </p>
                                                    )}
                                                </div>

                                                {/* Progress */}
                                                <div className="w-20 flex flex-col items-end gap-1 shrink-0">
                                                    <span className="text-sm font-bold tabular-nums">
                                                        {dl.progress.toFixed(0)}%
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Progress bar — full width bottom */}
                                            <div className="relative h-1">
                                                <div className="absolute inset-0 bg-muted/20" />
                                                <div
                                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400 transition-all duration-500"
                                                    style={{
                                                        width: `${dl.progress}%`,
                                                    }}
                                                />
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </motion.div>
                )}
            </motion.div>
        </>
    );
}
