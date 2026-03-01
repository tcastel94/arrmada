"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { ServiceCard } from "@/components/services/service-card";
import { ServiceConfigDialog } from "@/components/services/service-config";
import { EmptyState } from "@/components/shared/empty-state";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Plus, Server } from "lucide-react";
import {
    useServices,
    useCreateService,
    useUpdateService,
    useDeleteService,
    useTestConnection,
} from "@/hooks/use-services";
import { ArrService, CreateServicePayload } from "@/types/service";
import { motion } from "framer-motion";

export default function ServicesPage() {
    const { data: services, isLoading } = useServices();
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

    return (
        <>
            <Header title="Services" />
            <div className="p-6 space-y-6">
                {/* Header bar */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">Services *arr</h2>
                        <p className="text-sm text-muted-foreground">
                            Gérez vos connexions aux services Sonarr, Radarr, et autres
                        </p>
                    </div>
                    <Button
                        onClick={() => {
                            setEditingService(null);
                            setDialogOpen(true);
                        }}
                        id="add-service-btn"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Ajouter
                    </Button>
                </div>

                {/* Services Grid */}
                {isLoading ? (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <CardSkeleton key={i} />
                        ))}
                    </div>
                ) : !services || services.length === 0 ? (
                    <EmptyState
                        icon={Server}
                        title="Aucun service configuré"
                        description="Ajoutez votre premier service *arr pour commencer à utiliser ArrMada"
                        action={{
                            label: "Ajouter un service",
                            onClick: () => setDialogOpen(true),
                        }}
                    />
                ) : (
                    <motion.div
                        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                        initial="hidden"
                        animate="visible"
                        variants={{
                            visible: { transition: { staggerChildren: 0.05 } },
                        }}
                    >
                        {services.map((service) => (
                            <ServiceCard
                                key={service.id}
                                service={service}
                                onTest={handleTest}
                                onEdit={handleEdit}
                                onDelete={handleDelete}
                                isTesting={testMutation.isPending}
                            />
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
            </div>
        </>
    );
}
