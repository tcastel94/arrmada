"use client";

import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
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
    Trash2,
    Ban,
    RotateCw,
    Loader2,
} from "lucide-react";
import {
    useDownloads,
    useRemoveQueueItem,
    useRetryQueueItem,
    type DownloadItem,
} from "@/hooks/use-downloads";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";
import { toast } from "sonner";

type PendingAction =
    | { kind: "remove"; item: DownloadItem }
    | { kind: "blocklist"; item: DownloadItem }
    | { kind: "retry"; item: DownloadItem };

const ACTION_COPY: Record<PendingAction["kind"], { title: string; description: string; confirm: string }> = {
    remove: {
        title: "Supprimer de la queue",
        description: "Le téléchargement sera retiré du client et de la queue *arr. Le release n'est pas blocklisté.",
        confirm: "Supprimer",
    },
    blocklist: {
        title: "Supprimer + Blocklist",
        description: "Le téléchargement sera supprimé ET le release blocklisté pour ne plus être re-grabé.",
        confirm: "Supprimer + Blocklist",
    },
    retry: {
        title: "Relancer (Retry)",
        description: "Le release actuel sera blocklisté puis retiré, et une nouvelle recherche automatique sera lancée.",
        confirm: "Relancer",
    },
};

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
    const removeItem = useRemoveQueueItem();
    const retryItem = useRetryQueueItem();
    const [pending, setPending] = useState<PendingAction | null>(null);

    const isBusy = removeItem.isPending || retryItem.isPending;

    const runAction = async () => {
        if (!pending) return;
        const { kind, item } = pending;
        const type = item.service_type; // "radarr" | "sonarr"
        try {
            if (kind === "retry") {
                await retryItem.mutateAsync({
                    type,
                    id: item.id,
                    movie_id: item.movie_id,
                    series_id: item.series_id,
                });
                toast.success("Relance lancée — nouvelle recherche en cours.");
            } else {
                await removeItem.mutateAsync({
                    type,
                    id: item.id,
                    removeFromClient: true,
                    blocklist: kind === "blocklist",
                });
                toast.success(kind === "blocklist" ? "Supprimé et blocklisté." : "Supprimé de la queue.");
            }
            setPending(null);
        } catch (e) {
            toast.error("Erreur : " + (e as Error).message);
        }
    };

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
                                                <div className="w-14 flex flex-col items-end gap-1 shrink-0">
                                                    <span className="text-sm font-bold tabular-nums">
                                                        {dl.progress.toFixed(0)}%
                                                    </span>
                                                </div>

                                                {/* Actions */}
                                                <div className="flex items-center gap-1 shrink-0">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                                                        title="Relancer (blocklist + recherche)"
                                                        onClick={() => setPending({ kind: "retry", item: dl })}
                                                    >
                                                        <RotateCw className="h-4 w-4" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-orange-400 hover:text-orange-300 hover:bg-orange-500/10"
                                                        title="Supprimer + Blocklist"
                                                        onClick={() => setPending({ kind: "blocklist", item: dl })}
                                                    >
                                                        <Ban className="h-4 w-4" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                                        title="Supprimer de la queue"
                                                        onClick={() => setPending({ kind: "remove", item: dl })}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
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

            {/* Confirmation dialog */}
            <Dialog open={!!pending} onOpenChange={(open) => !open && !isBusy && setPending(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{pending ? ACTION_COPY[pending.kind].title : ""}</DialogTitle>
                        <DialogDescription>
                            {pending ? ACTION_COPY[pending.kind].description : ""}
                        </DialogDescription>
                    </DialogHeader>
                    {pending && (
                        <p className="text-sm text-muted-foreground truncate">
                            <span className="font-medium text-foreground">{pending.item.title}</span>
                        </p>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setPending(null)} disabled={isBusy}>
                            Annuler
                        </Button>
                        <Button
                            variant={pending?.kind === "retry" ? "default" : "destructive"}
                            onClick={runAction}
                            disabled={isBusy}
                        >
                            {isBusy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            {pending ? ACTION_COPY[pending.kind].confirm : ""}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
