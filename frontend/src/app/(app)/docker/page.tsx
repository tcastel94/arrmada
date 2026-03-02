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
} from "lucide-react";
import {
    useDockerContainers,
    useDockerAction,
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

export default function DockerPage() {
    const { data, isLoading } = useDockerContainers();
    const actionMutation = useDockerAction();

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
            </motion.div>
        </>
    );
}
