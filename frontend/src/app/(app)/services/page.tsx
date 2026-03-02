"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { ServiceCard } from "@/components/services/service-card";
import { ServiceConfigDialog } from "@/components/services/service-config";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Server, Zap, Wifi, WifiOff } from "lucide-react";
import {
    useServices,
    useCreateService,
    useUpdateService,
    useDeleteService,
    useTestConnection,
    useGlobalHealth,
} from "@/hooks/use-services";
import { ArrService, CreateServicePayload } from "@/types/service";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.07 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

export default function ServicesPage() {
    const { data: services, isLoading } = useServices();
    const { data: healthResults } = useGlobalHealth();
    const createMutation = useCreateService();
    const updateMutation = useUpdateService();
    const deleteMutation = useDeleteService();
    const testMutation = useTestConnection();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingService, setEditingService] = useState<ArrService | null>(null);

    const handleCreate = async (data: CreateServicePayload) => {
        try {
            await createMutation.mutateAsync(data);
            setDialogOpen(false);
        } catch (err: any) {
            console.error("Failed to create service:", err);
        }
    };

    const handleEdit = (service: ArrService) => {
        setEditingService(service);
        setDialogOpen(true);
    };

    const handleUpdate = async (data: CreateServicePayload) => {
        if (!editingService) return;
        try {
            await updateMutation.mutateAsync({
                id: editingService.id,
                data: {
                    name: data.name,
                    url: data.url,
                    api_key: data.api_key || undefined,
                    is_enabled: data.is_enabled,
                },
            });
            setDialogOpen(false);
            setEditingService(null);
        } catch (err: any) {
            console.error("Failed to update service:", err);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm("Supprimer ce service ?")) return;
        try {
            await deleteMutation.mutateAsync(id);
        } catch (err: any) {
            console.error("Failed to delete service:", err);
        }
    };

    const handleTest = async (id: number) => {
        try {
            const result = await testMutation.mutateAsync(id);
            alert(
                result.success
                    ? `✅ Connexion réussie (${result.latency_ms}ms) — v${result.version || "?"}`
                    : `❌ Échec : ${result.error}`
            );
        } catch (err: any) {
            alert(`❌ Erreur : ${err.message}`);
        }
    };

    const onlineCount = healthResults?.filter((h) => h.status === "online").length ?? 0;
    const totalServices = services?.length ?? 0;

    return (
        <>
            <Header title="Services" />
            <motion.div
                className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-indigo-600/20 via-purple-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="rounded-xl bg-indigo-500/20 p-3">
                                    <Server className="h-6 w-6 text-indigo-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold tracking-tight">
                                        Services *arr
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">
                                        Gérez vos connexions aux services Sonarr, Radarr, Lidarr et plus
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                {totalServices > 0 && (
                                    <Badge
                                        variant="outline"
                                        className={cn(
                                            "gap-1.5 px-3 py-1",
                                            onlineCount === totalServices
                                                ? "border-emerald-500/30 text-emerald-400"
                                                : "border-amber-500/30 text-amber-400"
                                        )}
                                    >
                                        {onlineCount === totalServices ? (
                                            <Wifi className="h-3 w-3" />
                                        ) : (
                                            <WifiOff className="h-3 w-3" />
                                        )}
                                        {onlineCount}/{totalServices} en ligne
                                    </Badge>
                                )}
                                <Button
                                    onClick={() => {
                                        setEditingService(null);
                                        setDialogOpen(true);
                                    }}
                                    id="add-service-btn"
                                    className="gap-2 bg-indigo-600 hover:bg-indigo-500"
                                >
                                    <Plus className="h-4 w-4" />
                                    Ajouter
                                </Button>
                            </div>
                        </div>
                        {/* Decorative */}
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-indigo-500/10 blur-3xl" />
                        <div className="absolute -bottom-8 -left-8 w-32 h-32 rounded-full bg-purple-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Services Grid */}
                {isLoading ? (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div
                                key={i}
                                className="h-40 rounded-xl bg-muted/20 animate-pulse ring-1 ring-white/5"
                            />
                        ))}
                    </div>
                ) : !services || services.length === 0 ? (
                    <motion.div variants={fadeUp}>
                        <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                            <EmptyState
                                icon={Server}
                                title="Aucun service configuré"
                                description="Ajoutez votre premier service *arr pour commencer à utiliser ArrMada"
                                action={{
                                    label: "Ajouter un service",
                                    onClick: () => setDialogOpen(true),
                                }}
                            />
                        </div>
                    </motion.div>
                ) : (
                    <motion.div
                        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                        variants={container}
                    >
                        {services.map((service) => (
                            <motion.div key={service.id} variants={fadeUp}>
                                <ServiceCard
                                    service={service}
                                    onTest={handleTest}
                                    onEdit={handleEdit}
                                    onDelete={handleDelete}
                                    isTesting={testMutation.isPending}
                                />
                            </motion.div>
                        ))}
                    </motion.div>
                )}

                {/* Config Dialog */}
                <ServiceConfigDialog
                    open={dialogOpen}
                    onOpenChange={(open) => {
                        setDialogOpen(open);
                        if (!open) setEditingService(null);
                    }}
                    onSubmit={editingService ? handleUpdate : handleCreate}
                    service={editingService}
                    isLoading={createMutation.isPending || updateMutation.isPending}
                />
            </motion.div>
        </>
    );
}
