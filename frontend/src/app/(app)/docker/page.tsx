"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Container,
    Play,
    Square,
    RotateCw,
    Box,
    ScrollText,
    Sparkles,
    Loader2,
    AlertTriangle,
    Wrench,
} from "lucide-react";
import {
    useDockerContainers,
    useDockerAction,
    useDockerLogs,
    useAnalyzeLogs,
    type DockerLogEntry,
    type LogProblem,
} from "@/hooks/use-files";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

const LEVEL_STYLES: Record<
    DockerLogEntry["level"],
    { text: string; dot: string; label: string }
> = {
    error: { text: "text-red-400", dot: "bg-red-500", label: "ERR" },
    warning: { text: "text-orange-400", dot: "bg-orange-500", label: "WARN" },
    info: { text: "text-yellow-300", dot: "bg-yellow-400", label: "INFO" },
    other: { text: "text-muted-foreground/70", dot: "bg-white/20", label: "" },
};

const SEVERITY_ACCENT: Record<string, string> = {
    error: "border-l-red-500",
    warning: "border-l-orange-500",
    info: "border-l-yellow-400",
};

function ProblemCard({ problem }: { problem: LogProblem }) {
    const accent = SEVERITY_ACCENT[problem.severity] || "border-l-white/20";
    return (
        <div
            className={cn(
                "rounded-md border border-white/5 border-l-2 bg-card/50 p-3",
                accent
            )}
        >
            <div className="flex items-center gap-2 flex-wrap">
                <AlertTriangle
                    className={cn(
                        "h-3.5 w-3.5 shrink-0",
                        problem.severity === "error"
                            ? "text-red-400"
                            : problem.severity === "warning"
                              ? "text-orange-400"
                              : "text-yellow-400"
                    )}
                />
                <span className="font-semibold text-sm">{problem.title}</span>
                {(problem.services || []).map((s) => (
                    <Badge
                        key={s}
                        variant="outline"
                        className="text-[10px] h-4 px-1.5 border-white/10 text-sky-400/80"
                    >
                        {s}
                    </Badge>
                ))}
                {problem.occurrences ? (
                    <Badge
                        variant="outline"
                        className="text-[10px] h-4 px-1.5 border-white/10 text-muted-foreground"
                    >
                        ×{problem.occurrences}
                    </Badge>
                ) : null}
            </div>
            {problem.cause && (
                <p className="text-xs text-muted-foreground mt-2">
                    <span className="text-foreground/70">Cause : </span>
                    {problem.cause}
                </p>
            )}
            {problem.solution && (
                <p className="text-xs mt-1.5 flex gap-1.5">
                    <Wrench className="h-3 w-3 text-emerald-400 mt-0.5 shrink-0" />
                    <span>
                        <span className="text-emerald-400/90">Solution : </span>
                        <span className="text-muted-foreground">
                            {problem.solution}
                        </span>
                    </span>
                </p>
            )}
        </div>
    );
}

export default function DockerPage() {
    const { data, isLoading } = useDockerContainers();
    const actionMutation = useDockerAction();
    const { data: logsData, isLoading: logsLoading } = useDockerLogs();
    const analyze = useAnalyzeLogs();
    const analysis = analyze.data;

    const handleAction = (containerId: string, action: string) => {
        actionMutation.mutate({ container_id: containerId, action });
    };

    if (isLoading) {
        return (
            <>
                <Header title="Docker" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    return (
        <>
            <Header title="Docker" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-sky-600/20 via-blue-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="rounded-xl bg-sky-500/20 p-3">
                                    <Box className="h-6 w-6 text-sky-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold tracking-tight">
                                        Containers Docker
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">
                                        Containers Unraid des services enregistrés
                                    </p>
                                </div>
                            </div>
                            {data && (
                                <div className="flex gap-2">
                                    <Badge
                                        variant="outline"
                                        className="gap-1.5 border-emerald-500/30 text-emerald-400"
                                    >
                                        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                                        {data.running} running
                                    </Badge>
                                    <Badge
                                        variant="outline"
                                        className="border-white/10"
                                    >
                                        {data.total} total
                                    </Badge>
                                </div>
                            )}
                        </div>
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-sky-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Container List */}
                {!data || data.containers.length === 0 ? (
                    <motion.div variants={fadeUp}>
                        <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                            <EmptyState
                                icon={Container}
                                title="Aucun container"
                                description="Aucun container Unraid ne correspond à vos services"
                            />
                        </div>
                    </motion.div>
                ) : (
                    <motion.div className="space-y-2" variants={container}>
                        {data.containers.map((c) => {
                            const isRunning = c.status === "running";
                            return (
                                <motion.div key={c.id} variants={fadeUp}>
                                    <Card
                                        className={cn(
                                            "border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden hover:ring-white/10 transition-all"
                                        )}
                                    >
                                        <CardContent className="p-4 flex items-center gap-4">
                                            {/* Status */}
                                            <div className="relative shrink-0">
                                                <span
                                                    className={cn(
                                                        "block h-3 w-3 rounded-full",
                                                        isRunning
                                                            ? "bg-emerald-400"
                                                            : "bg-red-400"
                                                    )}
                                                />
                                                {isRunning && (
                                                    <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-30" />
                                                )}
                                            </div>

                                            {/* Info */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <p className="font-semibold">
                                                        {c.name}
                                                    </p>
                                                    {(c as any).service_type && (
                                                        <Badge
                                                            variant="outline"
                                                            className="text-[10px] h-4 px-1.5 border-white/10"
                                                        >
                                                            {
                                                                (c as any)
                                                                    .service_type
                                                            }
                                                        </Badge>
                                                    )}
                                                </div>
                                                <p className="text-xs text-muted-foreground/60 truncate font-mono">
                                                    {c.image}
                                                </p>
                                            </div>

                                            {/* Ports */}
                                            <div className="hidden md:flex gap-1 shrink-0">
                                                {(c.ports || [])
                                                    .slice(0, 3)
                                                    .map((port, j) => (
                                                        <Badge
                                                            key={j}
                                                            variant="outline"
                                                            className="text-[10px] font-mono border-white/10"
                                                        >
                                                            {port}
                                                        </Badge>
                                                    ))}
                                            </div>

                                            {/* Status badge */}
                                            <Badge
                                                className={cn(
                                                    "shrink-0 border-0",
                                                    isRunning
                                                        ? "bg-emerald-500/20 text-emerald-400"
                                                        : "bg-red-500/20 text-red-400"
                                                )}
                                            >
                                                {isRunning
                                                    ? "En cours"
                                                    : "Arrêté"}
                                            </Badge>

                                            {/* Actions */}
                                            <div className="flex gap-1 shrink-0">
                                                {isRunning ? (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="h-8 w-8 hover:bg-white/5"
                                                            onClick={() =>
                                                                handleAction(
                                                                    c.id,
                                                                    "restart"
                                                                )
                                                            }
                                                            disabled={
                                                                actionMutation.isPending
                                                            }
                                                            title="Redémarrer"
                                                        >
                                                            <RotateCw className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                                            onClick={() =>
                                                                handleAction(
                                                                    c.id,
                                                                    "stop"
                                                                )
                                                            }
                                                            disabled={
                                                                actionMutation.isPending
                                                            }
                                                            title="Arrêter"
                                                        >
                                                            <Square className="h-4 w-4" />
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                                                        onClick={() =>
                                                            handleAction(
                                                                c.id,
                                                                "start"
                                                            )
                                                        }
                                                        disabled={
                                                            actionMutation.isPending
                                                        }
                                                        title="Démarrer"
                                                    >
                                                        <Play className="h-4 w-4" />
                                                    </Button>
                                                )}
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </motion.div>
                )}

                {/* Aggregated logs */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
                            <div className="flex items-center gap-2">
                                <ScrollText className="h-4 w-4 text-sky-400" />
                                <h3 className="font-semibold text-sm">
                                    Logs agrégés
                                </h3>
                                {logsData && (
                                    <Badge
                                        variant="outline"
                                        className="text-[10px] h-4 px-1.5 border-white/10 text-muted-foreground"
                                    >
                                        {logsData.count} lignes
                                    </Badge>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="hidden sm:flex items-center gap-3 text-[11px] text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                        <span className="h-2 w-2 rounded-full bg-red-500" />
                                        Erreur
                                    </span>
                                    <span className="flex items-center gap-1">
                                        <span className="h-2 w-2 rounded-full bg-orange-500" />
                                        Warning
                                    </span>
                                    <span className="flex items-center gap-1">
                                        <span className="h-2 w-2 rounded-full bg-yellow-400" />
                                        Info
                                    </span>
                                </div>
                                <Button
                                    size="sm"
                                    className="h-7 gap-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white border-0"
                                    onClick={() => analyze.mutate(150)}
                                    disabled={analyze.isPending}
                                    title="Analyser les logs avec l'IA locale (Ollama)"
                                >
                                    {analyze.isPending ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <Sparkles className="h-3.5 w-3.5" />
                                    )}
                                    {analyze.isPending
                                        ? "Analyse en cours…"
                                        : "Analyser avec l'IA"}
                                </Button>
                            </div>
                        </div>

                        {/* AI analysis result */}
                        {(analyze.isPending || analysis) && (
                            <div className="border-b border-white/5 bg-violet-500/[0.04] px-4 py-4">
                                {analyze.isPending ? (
                                    <p className="text-sm text-muted-foreground flex items-center gap-2">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        L'IA locale analyse les logs… (quelques
                                        dizaines de secondes)
                                    </p>
                                ) : analysis?.error ? (
                                    <p className="text-sm text-red-400">
                                        {analysis.error}
                                    </p>
                                ) : (
                                    <div className="space-y-3">
                                        <div className="flex items-start gap-2">
                                            <Sparkles className="h-4 w-4 text-violet-400 mt-0.5 shrink-0" />
                                            <div>
                                                <p className="text-sm">
                                                    {analysis?.summary}
                                                </p>
                                                <p className="text-[11px] text-muted-foreground mt-1">
                                                    {analysis?.analyzed_lines}{" "}
                                                    lignes analysées
                                                    {analysis?.engine
                                                        ? ` · ${analysis.engine}`
                                                        : ""}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="grid gap-2">
                                            {(analysis?.problems || []).map(
                                                (p, i) => (
                                                    <ProblemCard
                                                        key={i}
                                                        problem={p}
                                                    />
                                                )
                                            )}
                                            {analysis?.problems?.length === 0 && (
                                                <p className="text-sm text-emerald-400">
                                                    Aucun problème notable
                                                    détecté. 🎉
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        <CardContent className="p-0">
                            <div className="max-h-[420px] overflow-auto font-mono text-xs leading-relaxed">
                                {logsLoading ? (
                                    <div className="p-4 text-muted-foreground">
                                        Chargement des logs…
                                    </div>
                                ) : !logsData || logsData.logs.length === 0 ? (
                                    <div className="p-4 text-muted-foreground">
                                        Aucun log disponible.
                                    </div>
                                ) : (
                                    <ul className="divide-y divide-white/[0.03]">
                                        {logsData.logs.map((l, idx) => {
                                            const s = LEVEL_STYLES[l.level];
                                            return (
                                                <li
                                                    key={idx}
                                                    className="flex items-start gap-2 px-4 py-1 hover:bg-white/[0.02]"
                                                >
                                                    <span
                                                        className={cn(
                                                            "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                                                            s.dot
                                                        )}
                                                    />
                                                    <span className="shrink-0 text-muted-foreground/50 tabular-nums">
                                                        {l.time}
                                                    </span>
                                                    <span className="shrink-0 w-24 truncate text-sky-400/70">
                                                        {l.service}
                                                    </span>
                                                    <span
                                                        className={cn(
                                                            "min-w-0 break-all",
                                                            s.text
                                                        )}
                                                    >
                                                        {l.message}
                                                    </span>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </motion.div>
        </>
    );
}
