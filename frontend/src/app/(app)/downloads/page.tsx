"use client";

import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Download, Loader2 } from "lucide-react";
import { useDownloads } from "@/hooks/use-downloads";
import { cn } from "@/lib/utils";

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function statusColor(status: string): string {
    switch (status.toLowerCase()) {
        case "downloading":
            return "bg-blue-500";
        case "completed":
            return "bg-green-500";
        case "paused":
            return "bg-yellow-500";
        case "queued":
            return "bg-gray-500";
        case "warning":
            return "bg-orange-500";
        case "failed":
            return "bg-red-500";
        default:
            return "bg-gray-500";
    }
}

export default function DownloadsPage() {
    const { data, isLoading } = useDownloads();

    return (
        <>
            <Header title="Downloads" />
            <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">
                            Téléchargements
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Queue de téléchargement unifiée de tous vos services
                        </p>
                    </div>
                    {data && data.total > 0 && (
                        <Badge variant="outline" className="text-sm">
                            {data.total} en cours
                        </Badge>
                    )}
                </div>

                <Card>
                    <CardContent className="p-0">
                        {isLoading ? (
                            <div className="p-6">
                                <TableSkeleton rows={5} />
                            </div>
                        ) : !data || data.items.length === 0 ? (
                            <div className="p-6">
                                <EmptyState
                                    icon={Download}
                                    title="Aucun téléchargement en cours"
                                    description="La queue est vide — les téléchargements actifs apparaîtront ici"
                                />
                            </div>
                        ) : (
                            <div className="divide-y divide-border">
                                {data.items.map((dl) => (
                                    <div
                                        key={dl.id}
                                        className="flex items-center gap-4 p-4 hover:bg-muted/30 transition-colors"
                                    >
                                        {/* Status dot */}
                                        <span
                                            className={cn(
                                                "h-2.5 w-2.5 rounded-full shrink-0",
                                                statusColor(dl.status)
                                            )}
                                        />

                                        {/* Title & meta */}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium truncate">
                                                {dl.title}
                                            </p>
                                            <div className="flex items-center gap-3 mt-1">
                                                <span className="text-xs text-muted-foreground">
                                                    {dl.source_service}
                                                </span>
                                                {dl.quality && (
                                                    <Badge variant="outline" className="text-[10px]">
                                                        {dl.quality}
                                                    </Badge>
                                                )}
                                                {dl.indexer && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {dl.indexer}
                                                    </span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Size */}
                                        <div className="text-right shrink-0 hidden sm:block">
                                            <p className="text-xs text-muted-foreground">
                                                {formatBytes(dl.size_bytes - dl.size_left_bytes)} /{" "}
                                                {formatBytes(dl.size_bytes)}
                                            </p>
                                        </div>

                                        {/* ETA */}
                                        <div className="w-16 text-right shrink-0 hidden md:block">
                                            {dl.time_left && (
                                                <span className="text-xs text-muted-foreground font-mono">
                                                    {dl.time_left}
                                                </span>
                                            )}
                                        </div>

                                        {/* Progress */}
                                        <div className="w-28 flex flex-col items-end gap-1 shrink-0">
                                            <span className="text-xs font-semibold tabular-nums">
                                                {dl.progress.toFixed(0)}%
                                            </span>
                                            <Progress value={dl.progress} className="h-2" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </>
    );
}
