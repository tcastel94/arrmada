"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Download,
    ArrowDownToLine,
    ArrowUpCircle,
    XCircle,
    Trash2,
    FileCheck,
    FileEdit,
    Activity,
    Film,
    Tv,
    RefreshCw,
    Clock,
    Zap,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useActivityFeed, type ActivityItem } from "@/hooks/use-activity";

const ICON_MAP: Record<string, any> = {
    grab: Download,
    download: ArrowDownToLine,
    import: FileCheck,
    upgrade: ArrowUpCircle,
    fail: XCircle,
    delete: Trash2,
    rename: FileEdit,
};

const STATUS_CONFIG: Record<string, { gradient: string; dot: string; text: string; border: string }> = {
    success: {
        gradient: "from-emerald-500/20 to-emerald-500/5",
        dot: "bg-emerald-400",
        text: "text-emerald-400",
        border: "border-l-emerald-500/60",
    },
    warning: {
        gradient: "from-amber-500/20 to-amber-500/5",
        dot: "bg-amber-400",
        text: "text-amber-400",
        border: "border-l-amber-500/60",
    },
    error: {
        gradient: "from-red-500/20 to-red-500/5",
        dot: "bg-red-400",
        text: "text-red-400",
        border: "border-l-red-500/60",
    },
    info: {
        gradient: "from-blue-500/20 to-blue-500/5",
        dot: "bg-blue-400",
        text: "text-blue-400",
        border: "border-l-blue-500/60",
    },
};

function timeAgo(dateStr: string): string {
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMin = Math.floor(diffMs / 60000);

        if (diffMin < 1) return "À l'instant";
        if (diffMin < 60) return `${diffMin}min`;
        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `${diffH}h`;
        const diffD = Math.floor(diffH / 24);
        if (diffD < 7) return `${diffD}j`;
        return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    } catch {
        return "";
    }
}

function formatSize(bytes: number | null): string {
    if (!bytes || bytes <= 0) return "";
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
}

export function ActivityFeedCard() {
    const { data, isLoading, isFetching } = useActivityFeed(25);

    return (
        <Card className="bg-card/50 border-border/50 overflow-hidden">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                        <Zap className="h-4 w-4 text-amber-400" />
                        Activité récente
                    </span>
                    <div className="flex items-center gap-2">
                        {isFetching && (
                            <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
                        )}
                        {data && (
                            <Badge
                                variant="outline"
                                className="text-[10px] px-1.5 h-5 font-mono tabular-nums"
                            >
                                {data.total} évènements
                            </Badge>
                        )}
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 pb-2">
                {isLoading ? (
                    <div className="space-y-2 py-2">
                        {[...Array(6)].map((_, i) => (
                            <div
                                key={i}
                                className="flex items-center gap-3 p-3 rounded-lg"
                            >
                                <div className="w-8 h-8 rounded-full bg-muted/40 animate-pulse" />
                                <div className="flex-1 space-y-1.5">
                                    <div className="h-3.5 w-32 bg-muted/40 rounded animate-pulse" />
                                    <div className="h-3 w-48 bg-muted/30 rounded animate-pulse" />
                                </div>
                                <div className="h-3 w-12 bg-muted/30 rounded animate-pulse" />
                            </div>
                        ))}
                    </div>
                ) : !data?.items.length ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Activity className="h-8 w-8 mb-3 opacity-30" />
                        <p className="text-sm">Aucune activité récente</p>
                        <p className="text-xs opacity-50 mt-1">
                            Les grabs, imports et upgrades apparaîtront ici
                        </p>
                    </div>
                ) : (
                    <div className="relative">
                        {/* Timeline line */}
                        <div className="absolute left-[19px] top-4 bottom-4 w-px bg-gradient-to-b from-muted-foreground/20 via-muted-foreground/10 to-transparent" />

                        <div className="space-y-0.5 max-h-[520px] overflow-y-auto scrollbar-thin pr-1">
                            <AnimatePresence mode="popLayout">
                                {data.items.map((item, idx) => (
                                    <ActivityRow
                                        key={item.id}
                                        item={item}
                                        index={idx}
                                    />
                                ))}
                            </AnimatePresence>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

function ActivityRow({ item, index }: { item: ActivityItem; index: number }) {
    const Icon = ICON_MAP[item.icon_type] || Download;
    const SourceIcon = item.source === "sonarr" ? Tv : Film;
    const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.info;
    const sizeStr = formatSize(item.size_bytes);

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.25, delay: Math.min(index * 0.02, 0.3) }}
            className="flex items-start gap-3 py-2 px-1 group relative"
        >
            {/* Timeline dot + icon */}
            <div className="relative z-10 shrink-0">
                <div
                    className={`w-9 h-9 rounded-full flex items-center justify-center bg-gradient-to-br ${config.gradient} ring-1 ring-white/5`}
                >
                    <Icon className={`h-4 w-4 ${config.text}`} />
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0 pt-0.5">
                {/* Title row */}
                <div className="flex items-center gap-1.5 mb-0.5">
                    <SourceIcon className="h-3 w-3 text-muted-foreground/60 shrink-0" />
                    <p className="text-sm font-medium truncate leading-tight">
                        {item.title}
                    </p>
                </div>

                {/* Subtitle + badges */}
                <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-xs font-medium ${config.text}`}>
                        {item.event_label}
                    </span>
                    {item.subtitle && (
                        <span className="text-xs text-muted-foreground truncate">
                            · {item.subtitle}
                        </span>
                    )}
                </div>

                {/* Tags row */}
                <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {item.quality && (
                        <Badge
                            variant="outline"
                            className="text-[10px] px-1 py-0 h-4 border-muted-foreground/20"
                        >
                            {item.quality}
                        </Badge>
                    )}
                    {item.languages && (
                        <Badge
                            variant="outline"
                            className="text-[10px] px-1 py-0 h-4 border-muted-foreground/20"
                        >
                            {item.languages}
                        </Badge>
                    )}
                    {item.indexer && (
                        <span className="text-[10px] text-muted-foreground/50">
                            via {item.indexer}
                        </span>
                    )}
                </div>
            </div>

            {/* Right side — time + size */}
            <div className="text-right shrink-0 pt-1">
                <div className="flex items-center gap-1 justify-end text-[11px] text-muted-foreground">
                    <Clock className="h-3 w-3 opacity-40" />
                    <span className="tabular-nums">{timeAgo(item.date)}</span>
                </div>
                {sizeStr && (
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5 tabular-nums">
                        {sizeStr}
                    </p>
                )}
            </div>
        </motion.div>
    );
}
