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
    Loader2,
} from "lucide-react";
import {
    useDockerContainers,
    useDockerAction,
} from "@/hooks/use-files";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

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
            <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">
                            Containers Docker
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Containers Unraid des services enregistrés
                        </p>
                    </div>
                    {data && (
                        <div className="flex gap-2">
                            <Badge variant="outline" className="gap-1.5">
                                <span className="h-2 w-2 rounded-full bg-green-500" />
                                {data.running} en cours
                            </Badge>
                            <Badge variant="outline">
                                {data.total} services
                            </Badge>
                        </div>
                    )}
                </div>

                {!data || data.containers.length === 0 ? (
                    <EmptyState
                        icon={Container}
                        title="Aucun container"
                        description="Aucun container Unraid ne correspond à vos services enregistrés"
                    />
                ) : (
                    <div className="grid gap-3">
                        {data.containers.map((c, i) => (
                            <motion.div
                                key={c.id}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.02 }}
                            >
                                <Card>
                                    <CardContent className="p-4 flex items-center gap-4">
                                        {/* Status dot */}
                                        <span
                                            className={cn(
                                                "h-3 w-3 rounded-full shrink-0",
                                                c.status === "running" ? "bg-green-500" : "bg-red-500"
                                            )}
                                        />

                                        {/* Name & Service info */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className="font-semibold">{c.name}</p>
                                                {(c as any).service_type && (
                                                    <Badge variant="outline" className="text-[10px]">
                                                        {(c as any).service_type}
                                                    </Badge>
                                                )}
                                            </div>
                                            <p className="text-xs text-muted-foreground truncate">
                                                {c.image}
                                            </p>
                                        </div>

                                        {/* Ports */}
                                        <div className="hidden md:flex gap-1 shrink-0">
                                            {(c.ports || []).slice(0, 3).map((port, j) => (
                                                <Badge key={j} variant="outline" className="text-[10px] font-mono">
                                                    {port}
                                                </Badge>
                                            ))}
                                        </div>

                                        {/* Status */}
                                        <Badge
                                            variant={c.status === "running" ? "default" : "destructive"}
                                            className="capitalize shrink-0"
                                        >
                                            {c.status === "running" ? "En cours" : "Arrêté"}
                                        </Badge>

                                        {/* Actions */}
                                        <div className="flex gap-1 shrink-0">
                                            {c.status === "running" ? (
                                                <>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8"
                                                        onClick={() => handleAction(c.id, "restart")}
                                                        disabled={actionMutation.isPending}
                                                        title="Redémarrer"
                                                    >
                                                        <RotateCw className="h-4 w-4" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 text-red-500 hover:text-red-400"
                                                        onClick={() => handleAction(c.id, "stop")}
                                                        disabled={actionMutation.isPending}
                                                        title="Arrêter"
                                                    >
                                                        <Square className="h-4 w-4" />
                                                    </Button>
                                                </>
                                            ) : (
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-green-500 hover:text-green-400"
                                                    onClick={() => handleAction(c.id, "start")}
                                                    disabled={actionMutation.isPending}
                                                    title="Démarrer"
                                                >
                                                    <Play className="h-4 w-4" />
                                                </Button>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>
        </>
    );
}
