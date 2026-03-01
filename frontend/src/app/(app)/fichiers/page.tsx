"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    FolderOpen,
    AlertTriangle,
    CheckCircle,
    CheckCircle2,
    XCircle,
    Clock,
    HardDrive,
    ArrowRight,
    Loader2,
    Film,
    Tv,
    Check,
} from "lucide-react";
import {
    useSabnzbdHistory,
    useStuckDownloads,
    usePathMappings,
    useManualImport,
} from "@/hooks/use-files";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState, useCallback } from "react";

function statusIcon(status: string) {
    switch (status.toLowerCase()) {
        case "completed":
            return <CheckCircle className="h-4 w-4 text-green-500" />;
        case "failed":
            return <XCircle className="h-4 w-4 text-red-500" />;
        case "extracting":
        case "repairing":
        case "verifying":
            return <Clock className="h-4 w-4 text-yellow-500" />;
        default:
            return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
}

function statusColor(status: string) {
    switch (status.toLowerCase()) {
        case "completed":
            return "text-green-500";
        case "failed":
            return "text-red-500";
        default:
            return "text-yellow-500";
    }
}

// Import status per item
type ImportStatus = "idle" | "pending" | "success" | "error";

export default function FichiersPage() {
    const { data: historyData, isLoading: historyLoading } = useSabnzbdHistory(100);
    const { data: stuckData, isLoading: stuckLoading } = useStuckDownloads();
    const { data: pathData } = usePathMappings();
    const importMutation = useManualImport();

    // Per-item media type overrides
    const [typeOverrides, setTypeOverrides] = useState<Record<string, string>>({});
    // Per-item import status
    const [importStatuses, setImportStatuses] = useState<Record<string, ImportStatus>>({});
    // Selected items for batch import
    const [selected, setSelected] = useState<Set<string>>(new Set());
    // Per-item messages from the API
    const [importMessages, setImportMessages] = useState<Record<string, string>>({});

    const isLoading = historyLoading || stuckLoading;

    if (isLoading) {
        return (
            <>
                <Header title="Fichiers" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    const stuck = stuckData?.items || [];
    const items = historyData?.items || [];
    const stuckCount = stuck.length;

    const getMediaType = (item: typeof stuck[0]) =>
        typeOverrides[item.nzo_id] || item.media_type;

    const toggleType = (nzoId: string, type: string) => {
        setTypeOverrides((prev) => ({ ...prev, [nzoId]: type }));
    };

    const toggleSelect = (nzoId: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(nzoId)) {
                next.delete(nzoId);
            } else {
                next.add(nzoId);
            }
            return next;
        });
    };

    const selectAllAsSeries = () => {
        const newOverrides: Record<string, string> = {};
        const newSelected = new Set<string>();
        stuck.forEach((item) => {
            newOverrides[item.nzo_id] = "series";
            newSelected.add(item.nzo_id);
        });
        setTypeOverrides((prev) => ({ ...prev, ...newOverrides }));
        setSelected(newSelected);
    };

    const selectAllAsMovies = () => {
        const newOverrides: Record<string, string> = {};
        const newSelected = new Set<string>();
        stuck.forEach((item) => {
            newOverrides[item.nzo_id] = "movie";
            newSelected.add(item.nzo_id);
        });
        setTypeOverrides((prev) => ({ ...prev, ...newOverrides }));
        setSelected(newSelected);
    };


    const importSingle = async (item: typeof stuck[0]) => {
        const mediaType = getMediaType(item);
        if (mediaType === "unknown") return;

        setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "pending" }));
        setImportMessages((prev) => ({ ...prev, [item.nzo_id]: "" }));
        try {
            const result = await importMutation.mutateAsync({
                download_path: item.storage_path,
                media_type: mediaType,
            });
            if (result.success) {
                setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "success" }));
                setImportMessages((prev) => ({ ...prev, [item.nzo_id]: result.message || "Importé" }));
            } else {
                setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "error" }));
                setImportMessages((prev) => ({ ...prev, [item.nzo_id]: result.error || "Erreur" }));
            }
        } catch {
            setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "error" }));
            setImportMessages((prev) => ({ ...prev, [item.nzo_id]: "Erreur réseau" }));
        }
    };

    const importSelected = async () => {
        const toImport = stuck.filter(
            (item) => selected.has(item.nzo_id) && getMediaType(item) !== "unknown"
        );
        if (toImport.length === 0) return;

        // Set all to pending
        const pendingStatuses: Record<string, ImportStatus> = {};
        toImport.forEach((item) => {
            pendingStatuses[item.nzo_id] = "pending";
        });
        setImportStatuses((prev) => ({ ...prev, ...pendingStatuses }));

        // Import sequentially to avoid hammering the API
        for (const item of toImport) {
            try {
                const result = await importMutation.mutateAsync({
                    download_path: item.storage_path,
                    media_type: getMediaType(item),
                });
                if (result.success) {
                    setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "success" }));
                    setImportMessages((prev) => ({ ...prev, [item.nzo_id]: result.message || "Importé" }));
                } else {
                    setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "error" }));
                    setImportMessages((prev) => ({ ...prev, [item.nzo_id]: result.error || "Erreur" }));
                }
            } catch {
                setImportStatuses((prev) => ({ ...prev, [item.nzo_id]: "error" }));
                setImportMessages((prev) => ({ ...prev, [item.nzo_id]: "Erreur réseau" }));
            }
        }
    };

    const selectedCount = selected.size;
    const readyToImport = stuck.filter(
        (item) => selected.has(item.nzo_id) && getMediaType(item) !== "unknown"
    ).length;

    const successCount = Object.values(importStatuses).filter((s) => s === "success").length;
    const pendingCount = Object.values(importStatuses).filter((s) => s === "pending").length;

    return (
        <>
            <Header title="Fichiers" />
            <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">
                            Gestion des fichiers
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Chemins NAS, téléchargements bloqués et import manuel
                        </p>
                    </div>
                    <div className="flex gap-2">
                        {successCount > 0 && (
                            <Badge className="gap-1.5 bg-green-500/20 text-green-400 border-green-500/30">
                                <CheckCircle2 className="h-3 w-3" />
                                {successCount} importé{successCount > 1 ? "s" : ""}
                            </Badge>
                        )}
                        {stuckCount > 0 && (
                            <Badge variant="destructive" className="gap-1.5">
                                <AlertTriangle className="h-3 w-3" />
                                {stuckCount} bloqué{stuckCount > 1 ? "s" : ""}
                            </Badge>
                        )}
                        <Badge variant="outline">
                            {items.length} fichiers
                        </Badge>
                    </div>
                </div>

                {/* NAS Path Mappings */}
                {pathData && (pathData.movies_host_path || pathData.series_host_path) && (
                    <Card className="border-blue-500/20">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium flex items-center gap-2">
                                <HardDrive className="h-4 w-4 text-blue-400" />
                                Chemins NAS
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {pathData.downloads_host_path && (
                                    <div className="bg-muted/30 rounded-lg p-3">
                                        <p className="text-xs text-muted-foreground mb-1">📥 Downloads</p>
                                        <code className="text-xs font-mono text-foreground">
                                            {pathData.downloads_host_path}
                                        </code>
                                    </div>
                                )}
                                {pathData.movies_host_path && (
                                    <div className="bg-muted/30 rounded-lg p-3">
                                        <p className="text-xs text-muted-foreground mb-1">🎬 Films</p>
                                        <code className="text-xs font-mono text-foreground">
                                            {pathData.movies_host_path}
                                        </code>
                                    </div>
                                )}
                                {pathData.series_host_path && (
                                    <div className="bg-muted/30 rounded-lg p-3">
                                        <p className="text-xs text-muted-foreground mb-1">📺 Séries</p>
                                        <code className="text-xs font-mono text-foreground">
                                            {pathData.series_host_path}
                                        </code>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Stuck Downloads — Import Section */}
                {stuckCount > 0 && (
                    <Card className="border-yellow-500/30">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                    Téléchargements à importer ({stuckCount})
                                </CardTitle>

                                {/* Batch actions */}
                                <div className="flex items-center gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-xs gap-1.5 h-7"
                                        onClick={selectAllAsSeries}
                                    >
                                        <Tv className="h-3 w-3" />
                                        Tout = Série
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-xs gap-1.5 h-7"
                                        onClick={selectAllAsMovies}
                                    >
                                        <Film className="h-3 w-3" />
                                        Tout = Film
                                    </Button>

                                    {selectedCount > 0 && (
                                        <Button
                                            size="sm"
                                            variant="default"
                                            className="gap-1.5 h-7"
                                            onClick={importSelected}
                                            disabled={readyToImport === 0 || pendingCount > 0}
                                        >
                                            {pendingCount > 0 ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : (
                                                <ArrowRight className="h-3 w-3" />
                                            )}
                                            {pendingCount > 0
                                                ? `Import en cours...`
                                                : `Importer ${readyToImport} fichier${readyToImport > 1 ? "s" : ""}`
                                            }
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <p className="text-xs text-muted-foreground mb-3">
                                Sélectionnez le type (🎬 Film ou 📺 Série), cochez les fichiers, puis cliquez sur
                                &quot;Importer&quot;. Radarr/Sonarr se chargera du déplacement, renommage, sous-titres et Jellyfin.
                            </p>
                            {stuck.map((item, i) => {
                                const currentType = getMediaType(item);
                                const status = importStatuses[item.nzo_id] || "idle";
                                const isSelected = selected.has(item.nzo_id);
                                return (
                                    <motion.div
                                        key={item.nzo_id || i}
                                        initial={{ opacity: 0, y: 3 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.03 }}
                                        className={cn(
                                            "flex items-center gap-3 p-3 rounded-lg transition-colors",
                                            status === "success"
                                                ? "bg-green-500/10 border border-green-500/20"
                                                : status === "error"
                                                    ? "bg-red-500/10 border border-red-500/20"
                                                    : status === "pending"
                                                        ? "bg-blue-500/10 border border-blue-500/20"
                                                        : isSelected
                                                            ? "bg-muted/40 border border-primary/20"
                                                            : "bg-muted/20 hover:bg-muted/40 border border-transparent"
                                        )}
                                    >
                                        {/* Checkbox */}
                                        <button
                                            onClick={() => toggleSelect(item.nzo_id)}
                                            className={cn(
                                                "h-5 w-5 rounded border-2 shrink-0 flex items-center justify-center transition-colors",
                                                isSelected
                                                    ? "bg-primary border-primary text-primary-foreground"
                                                    : "border-muted-foreground/40 hover:border-primary"
                                            )}
                                        >
                                            {isSelected && <Check className="h-3 w-3" />}
                                        </button>

                                        {/* Type toggle buttons */}
                                        <div className="flex gap-0.5 shrink-0">
                                            <button
                                                onClick={() => toggleType(item.nzo_id, "movie")}
                                                className={cn(
                                                    "p-1.5 rounded-l-md border transition-colors",
                                                    currentType === "movie"
                                                        ? "bg-blue-500/20 border-blue-500/50 text-blue-400"
                                                        : "border-border text-muted-foreground hover:text-foreground hover:bg-muted/40"
                                                )}
                                                title="Film (Radarr)"
                                            >
                                                <Film className="h-3.5 w-3.5" />
                                            </button>
                                            <button
                                                onClick={() => toggleType(item.nzo_id, "series")}
                                                className={cn(
                                                    "p-1.5 rounded-r-md border border-l-0 transition-colors",
                                                    currentType === "series"
                                                        ? "bg-purple-500/20 border-purple-500/50 text-purple-400"
                                                        : "border-border text-muted-foreground hover:text-foreground hover:bg-muted/40"
                                                )}
                                                title="Série (Sonarr)"
                                            >
                                                <Tv className="h-3.5 w-3.5" />
                                            </button>
                                        </div>

                                        {/* Name & path */}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium truncate">{item.name}</p>
                                            <code className="text-[10px] text-muted-foreground font-mono truncate block">
                                                {item.storage_path}
                                            </code>
                                        </div>

                                        {/* Category badge */}
                                        <Badge variant="outline" className={cn(
                                            "text-[10px] shrink-0",
                                            item.category === "software" && "border-yellow-500/50 text-yellow-500"
                                        )}>
                                            {item.category}
                                        </Badge>

                                        {/* Size */}
                                        <span className="text-xs text-muted-foreground shrink-0 w-16 text-right tabular-nums">
                                            {item.size_human}
                                        </span>

                                        {/* Status / Action */}
                                        <div className="w-36 shrink-0 flex flex-col items-end gap-1">
                                            {status === "pending" ? (
                                                <Badge className="gap-1 bg-blue-500/20 text-blue-400 border-blue-500/30">
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                    En cours...
                                                </Badge>
                                            ) : status === "success" ? (
                                                <Badge className="gap-1 bg-green-500/20 text-green-400 border-green-500/30"
                                                    title={importMessages[item.nzo_id] || ""}
                                                >
                                                    <CheckCircle2 className="h-3 w-3" />
                                                    Importé ✓
                                                </Badge>
                                            ) : status === "error" ? (
                                                <>
                                                    <Badge className="gap-1 bg-red-500/20 text-red-400 border-red-500/30"
                                                        title={importMessages[item.nzo_id] || ""}
                                                    >
                                                        <XCircle className="h-3 w-3" />
                                                        Erreur
                                                    </Badge>
                                                    {importMessages[item.nzo_id] && (
                                                        <span className="text-[10px] text-red-400/80 max-w-[200px] text-right truncate">
                                                            {importMessages[item.nzo_id]}
                                                        </span>
                                                    )}
                                                </>
                                            ) : (
                                                <Button
                                                    size="sm"
                                                    variant="default"
                                                    className="gap-1.5"
                                                    disabled={currentType === "unknown"}
                                                    onClick={() => importSingle(item)}
                                                >
                                                    <ArrowRight className="h-3 w-3" />
                                                    {currentType === "unknown" ? "Choisir ←" : "Importer"}
                                                </Button>
                                            )}
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </CardContent>
                    </Card>
                )}

                {/* Full History */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">
                            Historique complet ({items.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        {items.length === 0 ? (
                            <div className="p-6">
                                <EmptyState
                                    icon={FolderOpen}
                                    title="Aucun historique"
                                    description="L'historique SABnzbd est vide ou le service n'est pas configuré"
                                />
                            </div>
                        ) : (
                            <div className="divide-y divide-border">
                                {items.map((item, i) => (
                                    <motion.div
                                        key={item.nzo_id || i}
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: i * 0.01 }}
                                        className={cn(
                                            "p-4 hover:bg-muted/20 transition-colors",
                                            item.is_stuck && "bg-yellow-500/5"
                                        )}
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="mt-0.5 shrink-0">
                                                {statusIcon(item.status)}
                                            </div>

                                            <div className="flex-1 min-w-0 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <p className="font-medium text-sm truncate">
                                                        {item.name}
                                                    </p>
                                                    {item.is_stuck && (
                                                        <Badge variant="destructive" className="text-[10px] shrink-0">
                                                            Bloqué
                                                        </Badge>
                                                    )}
                                                </div>

                                                {item.storage_path && (
                                                    <div className="flex items-center gap-1.5">
                                                        <HardDrive className="h-3 w-3 text-muted-foreground shrink-0" />
                                                        <code className="text-xs text-muted-foreground font-mono truncate block">
                                                            {item.storage_path}
                                                        </code>
                                                    </div>
                                                )}

                                                {item.download_path && item.download_path !== item.storage_path && (
                                                    <div className="flex items-center gap-1.5">
                                                        <FolderOpen className="h-3 w-3 text-orange-400 shrink-0" />
                                                        <code className="text-xs text-orange-400/80 font-mono truncate block">
                                                            {item.download_path}
                                                        </code>
                                                    </div>
                                                )}

                                                {item.fail_message && (
                                                    <p className="text-xs text-red-400">
                                                        ⚠ {item.fail_message}
                                                    </p>
                                                )}
                                            </div>

                                            <div className="flex flex-col items-end gap-1 shrink-0">
                                                <Badge variant="outline" className="text-[10px]">
                                                    {item.category || "*"}
                                                </Badge>
                                                <span className="text-xs text-muted-foreground tabular-nums">
                                                    {item.size_human}
                                                </span>
                                                <span className={cn("text-xs font-medium", statusColor(item.status))}>
                                                    {item.status}
                                                </span>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </>
    );
}
