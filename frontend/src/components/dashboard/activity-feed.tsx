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
    Activity,
    Film,
    Tv,
    RefreshCw,
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
};

const STATUS_STYLES: Record<string, string> = {
    success: "text-emerald-400 bg-emerald-500/10",
    warning: "text-amber-400 bg-amber-500/10",
    error: "text-red-400 bg-red-500/10",
    info: "text-blue-400 bg-blue-500/10",
};

const STATUS_BORDER: Record<string, string> = {
    success: "border-l-emerald-500",
    warning: "border-l-amber-500",
    error: "border-l-red-500",
    info: "border-l-blue-500",
};

function timeAgo(dateStr: string): string {
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMin = Math.floor(diffMs / 60000);

        if (diffMin < 1) return "À l'instant";
        if (diffMin < 60) return `il y a ${diffMin}m`;

        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `il y a ${diffH}h`;

        const diffD = Math.floor(diffH / 24);
        if (diffD < 7) return `il y a ${diffD}j`;

        return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    } catch {
        return "";
    }
}

function formatSize(bytes: number | null): string {
    if (!bytes) return "";
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
}

export function ActivityFeedCard() {
    const { data, isLoading, isFetching } = useActivityFeed(20);

    return (
        <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                        <Activity className="h-4 w-4" />
                        Activité récente
                    </span>
                    <div className="flex items-center gap-2">
                        {isFetching && (
                            <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
                        )}
                        {data && (
                            <Badge variant="outline" className="text-xs font-mono">
                                {data.total}
                            </Badge>
                        )}
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="space-y-3">
                        {[...Array(5)].map((_, i) => (
                            <div
                                key={i}
                                className="h-16 rounded-lg bg-muted/30 animate-pulse"
                            />
                        ))}
                    </div>
                ) : !data?.items.length ? (
                    <div className="text-center py-8 text-sm text-muted-foreground">
                        Aucune activité récente
                    </div>
                ) : (
                    <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
                        <AnimatePresence mode="popLayout">
                            {data.items.map((item, idx) => (
                                <ActivityRow key={item.id} item={item} index={idx} />
                            ))}
                        </AnimatePresence>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

function ActivityRow({ item, index }: { item: ActivityItem; index: number }) {
    const Icon = ICON_MAP[item.icon_type] || Download;
    const SourceIcon = item.source === "sonarr" ? Tv : Film;
    const statusStyle = STATUS_STYLES[item.status] || STATUS_STYLES.info;
    const borderStyle = STATUS_BORDER[item.status] || STATUS_BORDER.info;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={{ duration: 0.2, delay: index * 0.03 }}
            className={`flex items-center gap-3 p-2.5 rounded-lg border border-l-2 ${borderStyle} bg-card/30 hover:bg-card/60 transition-colors group`}
        >
            {/* Icon */}
            <div className={`rounded-full p-1.5 shrink-0 ${statusStyle}`}>
                <Icon className="h-3.5 w-3.5" />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                    <SourceIcon className="h-3 w-3 text-muted-foreground shrink-0" />
                    <p className="text-sm font-medium truncate">{item.title}</p>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-xs text-muted-foreground truncate">
                        {item.subtitle}
                    </p>
                    {item.quality && (
                        <Badge
                            variant="outline"
                            className="text-[10px] px-1 py-0 h-4 shrink-0"
                        >
                            {item.quality}
                        </Badge>
                    )}
                </div>
            </div>

            {/* Right side */}
            <div className="text-right shrink-0">
                <p className="text-[11px] text-muted-foreground whitespace-nowrap">
                    {timeAgo(item.date)}
                </p>
                {item.size_bytes && (
                    <p className="text-[10px] text-muted-foreground/70">
                        {formatSize(item.size_bytes)}
                    </p>
                )}
            </div>
        </motion.div>
    );
}
