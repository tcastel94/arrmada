"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Radar,
    CheckCircle,
    AlertTriangle,
    XCircle,
    ArrowUpRight,
    Search,
    Download,
    BarChart3,
    Trash2,
    FlaskConical,
    Loader2,
    ShieldCheck,
    Lock,
    Unlock,
} from "lucide-react";
import {
    useProwlarrStats,
    useTestIndexer,
    useToggleIndexer,
    useDeleteIndexer,
    IndexerStat,
    ProwlarrIndexer,
} from "@/hooks/use-new-features";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";
import { toast } from "sonner";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

function SuccessRateBar({ rate, label }: { rate: number; label: string }) {
    const color = rate >= 90 ? "from-emerald-500 to-emerald-400"
        : rate >= 70 ? "from-amber-500 to-yellow-400"
            : "from-red-500 to-red-400";
    const textColor = rate >= 90 ? "text-emerald-400"
        : rate >= 70 ? "text-amber-400"
            : "text-red-400";

    return (
        <div className="space-y-1">
            <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className={cn("font-bold tabular-nums", textColor)}>{rate}%</span>
            </div>
            <div className="relative">
                <Progress value={rate} className="h-1.5 bg-muted/30" />
                <div
                    className={cn("absolute inset-0 h-1.5 rounded-full bg-gradient-to-r opacity-80", color)}
                    style={{ width: `${rate}%` }}
                />
            </div>
        </div>
    );
}

function IndexerManagement({ indexers }: { indexers: ProwlarrIndexer[] }) {
    const testIndexer = useTestIndexer();
    const toggleIndexer = useToggleIndexer();
    const deleteIndexer = useDeleteIndexer();
    const [testingId, setTestingId] = useState<number | null>(null);
    const [togglingId, setTogglingId] = useState<number | null>(null);
    const [toDelete, setToDelete] = useState<ProwlarrIndexer | null>(null);

    const handleTest = (idx: ProwlarrIndexer) => {
        setTestingId(idx.id);
        testIndexer.mutate(
            { id: idx.id },
            {
                onSuccess: (res) => {
                    if (res.ok) toast.success(`« ${idx.name} » : test réussi.`);
                    else toast.error(`« ${idx.name} » : échec du test (HTTP ${res.status_code}).`);
                },
                onError: (e) => toast.error("Erreur : " + e.message),
                onSettled: () => setTestingId(null),
            },
        );
    };

    const handleToggle = (idx: ProwlarrIndexer) => {
        setTogglingId(idx.id);
        toggleIndexer.mutate(
            { id: idx.id, enable: !idx.enable },
            {
                onSuccess: (res) =>
                    toast.success(`« ${idx.name} » ${res.enable ? "activé" : "désactivé"}.`),
                onError: (e) => toast.error("Erreur : " + e.message),
                onSettled: () => setTogglingId(null),
            },
        );
    };

    const handleDelete = () => {
        if (!toDelete) return;
        const name = toDelete.name;
        deleteIndexer.mutate(
            { id: toDelete.id },
            {
                onSuccess: () => {
                    toast.success(`« ${name} » supprimé.`);
                    setToDelete(null);
                },
                onError: (e) => toast.error("Erreur : " + e.message),
            },
        );
    };

    return (
        <>
            <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                <CardContent className="p-0">
                    <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                        <ShieldCheck className="h-4 w-4 text-rose-400" />
                        <span className="text-sm font-semibold">Gestion des indexers</span>
                        <Badge variant="outline" className="text-[9px] px-1 h-4 ml-auto">
                            {indexers.length}
                        </Badge>
                    </div>
                    <div className="divide-y divide-white/5">
                        {indexers.map((idx) => (
                            <div key={`${idx.source}-${idx.id}`} className="flex items-center gap-3 p-4">
                                <div className="flex items-center gap-2 min-w-0 flex-1">
                                    {idx.enable ? (
                                        <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
                                    ) : (
                                        <XCircle className="h-4 w-4 text-muted-foreground shrink-0" />
                                    )}
                                    <span className="text-sm font-medium truncate">{idx.name}</span>
                                    <Badge variant="outline" className="text-[9px] px-1 h-4 shrink-0">
                                        {idx.protocol}
                                    </Badge>
                                    {idx.privacy && (
                                        <span className="text-muted-foreground shrink-0" title={idx.privacy}>
                                            {idx.privacy === "private" ? (
                                                <Lock className="h-3 w-3" />
                                            ) : (
                                                <Unlock className="h-3 w-3" />
                                            )}
                                        </span>
                                    )}
                                    {idx.status_messages && idx.status_messages.length > 0 && (
                                        <AlertTriangle
                                            className="h-3.5 w-3.5 text-amber-400 shrink-0"
                                            aria-label="Indexer en erreur"
                                        />
                                    )}
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 gap-1.5 text-sky-400 hover:text-sky-300 hover:bg-sky-500/10"
                                        disabled={testingId === idx.id}
                                        onClick={() => handleTest(idx)}
                                    >
                                        {testingId === idx.id ? (
                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        ) : (
                                            <FlaskConical className="h-3.5 w-3.5" />
                                        )}
                                        Test
                                    </Button>
                                    <div className="flex items-center gap-1.5 px-1">
                                        <Switch
                                            checked={idx.enable}
                                            disabled={togglingId === idx.id}
                                            onCheckedChange={() => handleToggle(idx)}
                                            aria-label="Activer / désactiver"
                                        />
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                        title="Supprimer l'indexer"
                                        onClick={() => setToDelete(idx)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                        {indexers.length === 0 && (
                            <div className="text-center py-8 text-muted-foreground text-sm">
                                Aucun indexer configuré
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Dialog open={!!toDelete} onOpenChange={(open) => !open && !deleteIndexer.isPending && setToDelete(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Supprimer l&apos;indexer</DialogTitle>
                        <DialogDescription>
                            L&apos;indexer sera définitivement supprimé de Prowlarr. Cette action est irréversible.
                        </DialogDescription>
                    </DialogHeader>
                    {toDelete && (
                        <p className="text-sm">
                            <span className="font-medium">{toDelete.name}</span>
                        </p>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setToDelete(null)} disabled={deleteIndexer.isPending}>
                            Annuler
                        </Button>
                        <Button variant="destructive" onClick={handleDelete} disabled={deleteIndexer.isPending}>
                            {deleteIndexer.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Supprimer
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}

export default function ProwlarrPage() {
    const { data, isLoading } = useProwlarrStats();

    if (isLoading) {
        return (
            <>
                <Header title="Indexers" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    const summary = data?.summary;
    const stats = data?.stats ?? [];
    const indexers = data?.indexers ?? [];

    return (
        <>
            <Header title="Indexers Prowlarr" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-rose-600/20 via-pink-600/10 to-transparent p-6 ring-1 ring-rose-500/20">
                        <div className="flex items-center gap-3">
                            <div className="rounded-xl p-2.5 bg-rose-500/20">
                                <Radar className="h-6 w-6 text-rose-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold">Prowlarr Indexers</h2>
                                <p className="text-sm text-muted-foreground">
                                    Performances et santé de vos indexers
                                </p>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-rose-500/30" />
                    </div>
                </motion.div>

                {/* Summary Stats */}
                {summary && (
                    <motion.div variants={fadeUp}>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-blue-600/10 to-transparent">
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Radar className="h-4 w-4 text-blue-400" />
                                        <span className="text-xs text-muted-foreground">Indexers actifs</span>
                                    </div>
                                    <p className="text-2xl font-bold tabular-nums">{summary.enabled_indexers}</p>
                                    <p className="text-[10px] text-muted-foreground">sur {summary.total_indexers}</p>
                                </CardContent>
                            </Card>
                            <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-purple-600/10 to-transparent">
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Search className="h-4 w-4 text-purple-400" />
                                        <span className="text-xs text-muted-foreground">Requêtes totales</span>
                                    </div>
                                    <p className="text-2xl font-bold tabular-nums">{summary.total_queries.toLocaleString()}</p>
                                </CardContent>
                            </Card>
                            <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-emerald-600/10 to-transparent">
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Download className="h-4 w-4 text-emerald-400" />
                                        <span className="text-xs text-muted-foreground">Grabs réussis</span>
                                    </div>
                                    <p className="text-2xl font-bold tabular-nums">{summary.total_grabs.toLocaleString()}</p>
                                </CardContent>
                            </Card>
                            <Card className="border-0 ring-1 ring-white/5 bg-gradient-to-br from-amber-600/10 to-transparent">
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-2 mb-1">
                                        <BarChart3 className="h-4 w-4 text-amber-400" />
                                        <span className="text-xs text-muted-foreground">Taux de succès</span>
                                    </div>
                                    <p className={cn(
                                        "text-2xl font-bold tabular-nums",
                                        summary.average_success_rate >= 90 ? "text-emerald-400"
                                            : summary.average_success_rate >= 70 ? "text-amber-400"
                                                : "text-red-400"
                                    )}>
                                        {summary.average_success_rate}%
                                    </p>
                                </CardContent>
                            </Card>
                        </div>
                    </motion.div>
                )}

                {/* Indexer Management */}
                <motion.div variants={fadeUp}>
                    <IndexerManagement indexers={indexers} />
                </motion.div>

                {/* Indexer List */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                        <CardContent className="p-0">
                            <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                <BarChart3 className="h-4 w-4 text-rose-400" />
                                <span className="text-sm font-semibold">Performances par indexer</span>
                            </div>
                            <div className="divide-y divide-white/5">
                                {stats.map((stat: IndexerStat) => (
                                    <div key={`${stat.indexer_name}-${stat.source}`} className="p-4 hover:bg-white/[0.02] transition-colors">
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="flex items-center gap-2">
                                                {stat.success_rate >= 90 ? (
                                                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                                                ) : stat.success_rate >= 70 ? (
                                                    <AlertTriangle className="h-4 w-4 text-amber-400" />
                                                ) : (
                                                    <XCircle className="h-4 w-4 text-red-400" />
                                                )}
                                                <span className="text-sm font-medium">{stat.indexer_name}</span>
                                                <Badge variant="outline" className="text-[9px] px-1 h-4">
                                                    {stat.source}
                                                </Badge>
                                            </div>
                                            <div className="flex items-center gap-3 text-xs text-muted-foreground tabular-nums">
                                                <span>{stat.queries} requêtes</span>
                                                <span>{stat.grabs} grabs</span>
                                                {stat.avg_response_time > 0 && (
                                                    <span>{stat.avg_response_time}ms</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="grid gap-2 sm:grid-cols-2">
                                            <SuccessRateBar rate={stat.success_rate} label="Taux de succès" />
                                            <SuccessRateBar rate={stat.grab_rate} label="Taux de grab" />
                                        </div>
                                    </div>
                                ))}
                                {stats.length === 0 && (
                                    <div className="text-center py-8 text-muted-foreground text-sm">
                                        Aucune statistique Prowlarr disponible
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
