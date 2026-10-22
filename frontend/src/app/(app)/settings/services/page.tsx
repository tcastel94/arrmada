"use client";

/**
 * Paramètres → Services *arr (ancienne page /services, qui redirige ici).
 * ----------------------------------------------------------------
 * Corrections : plus d'alert()/confirm() (→ toasts + ConfirmDialog),
 * erreurs visibles (avant : seulement dans la console), Kodi/Yamaha
 * filtrés (ce sont des appareils, réglés dans leurs propres pages),
 * test par carte, interrupteur d'activation, date du dernier contrôle.
 */
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, Loader2, Plus, Server } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { StatusDot } from "@/components/fx/status-dot";
import { ServiceCard } from "@/components/services/service-card";
import { ServiceConfigDialog } from "@/components/services/service-config";
import { useDeleteService, useGlobalHealth, useServices } from "@/hooks/use-services";
import { plural } from "@/lib/format";
import { stagger } from "@/lib/motion";
import type { ArrService } from "@/types/service";

export default function SettingsServicesPage() {
    const qc = useQueryClient();
    const { data: services, isLoading, isError, error, refetch } = useServices();
    const health = useGlobalHealth();
    const deleteService = useDeleteService();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<ArrService | null>(null);
    const [toDelete, setToDelete] = useState<ArrService | null>(null);

    // Chaque contrôle de santé global enregistre l'état en base : on relit
    // alors la liste pour mettre à jour statuts et dates sur les cartes.
    useEffect(() => {
        if (health.dataUpdatedAt) qc.invalidateQueries({ queryKey: ["services"], exact: true });
    }, [health.dataUpdatedAt, qc]);

    const counts = useMemo(() => {
        const list = services ?? [];
        const active = list.filter((s) => s.is_enabled);
        return {
            online: active.filter((s) => s.last_status === "online").length,
            offline: active.filter((s) => s.last_status === "offline" || s.last_status === "degraded").length,
            disabled: list.length - active.length,
        };
    }, [services]);

    const openCreate = () => {
        setEditing(null);
        setDialogOpen(true);
    };

    const testAll = () =>
        toast.promise(health.refetch({ throwOnError: true }), {
            loading: "Contrôle de tous les services…",
            success: (r) => {
                const list = r.data ?? [];
                const ok = list.filter((h) => h.status === "online").length;
                return `${ok}/${list.length} services répondent`;
            },
            error: (e: Error) => `Contrôle impossible : ${e.message}`,
        });

    return (
        <>
            {/* Barre d'actions + résumé */}
            <div className="glass flex flex-col gap-3 rounded-2xl p-3 sm:flex-row sm:items-center">
                <div className="flex flex-wrap items-center gap-2 px-1">
                    <span className="chip">
                        <StatusDot tone="online" size="sm" /> {counts.online} en ligne
                    </span>
                    {counts.offline > 0 && (
                        <span className="chip !text-destructive">
                            <StatusDot tone="offline" size="sm" /> {counts.offline} en panne
                        </span>
                    )}
                    {counts.disabled > 0 && (
                        <span className="chip">
                            <StatusDot tone="unknown" size="sm" /> {plural(counts.disabled, "désactivé")}
                        </span>
                    )}
                </div>
                <div className="flex gap-2 sm:ml-auto">
                    <Button variant="outline" size="sm" onClick={testAll} disabled={health.isFetching || !services?.length} className="flex-1 sm:flex-none">
                        {health.isFetching ? <Loader2 className="animate-spin" /> : <Activity />}
                        Tout tester
                    </Button>
                    <Button size="sm" onClick={openCreate} className="flex-1 sm:flex-none" id="add-service-btn">
                        <Plus /> Ajouter un service
                    </Button>
                </div>
            </div>

            {isLoading ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className="glass space-y-4 rounded-2xl p-4">
                            <div className="flex items-center gap-3">
                                <Shimmer className="h-10 w-10" />
                                <div className="flex-1 space-y-2">
                                    <Shimmer className="h-3.5 w-28 rounded-md" />
                                    <Shimmer className="h-2.5 w-16 rounded-md" />
                                </div>
                            </div>
                            <Shimmer className="h-7 w-full rounded-lg" />
                            <Shimmer className="h-8 w-full rounded-lg" />
                        </div>
                    ))}
                </div>
            ) : isError ? (
                <div className="glass rounded-2xl">
                    <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger les services" />
                </div>
            ) : !services || services.length === 0 ? (
                <div className="glass rounded-2xl">
                    <EmptyState
                        icon={Server}
                        title="Aucun service connecté"
                        description="Ajoute Sonarr, Radarr, Prowlarr… pour qu'ArrMada puisse lire et piloter ta médiathèque."
                        action={{ label: "Ajouter mon premier service", onClick: openCreate }}
                    />
                </div>
            ) : (
                <motion.div variants={stagger(0.05, 0.05)} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    <AnimatePresence>
                        {services.map((service) => (
                            <ServiceCard
                                key={service.id}
                                service={service}
                                onEdit={(s) => {
                                    setEditing(s);
                                    setDialogOpen(true);
                                }}
                                onDelete={setToDelete}
                            />
                        ))}
                    </AnimatePresence>
                </motion.div>
            )}

            <ServiceConfigDialog
                open={dialogOpen}
                onOpenChange={(open) => {
                    setDialogOpen(open);
                    if (!open) setEditing(null);
                }}
                service={editing}
            />

            <ConfirmDialog
                open={!!toDelete}
                onOpenChange={(o) => !o && setToDelete(null)}
                destructive
                title={`Supprimer ${toDelete?.name ?? "ce service"} ?`}
                description="ArrMada ne pourra plus lire ni piloter ce service. L'application elle-même (et ses fichiers) n'est pas touchée : tu pourras la reconnecter plus tard."
                confirmLabel="Supprimer"
                onConfirm={async () => {
                    if (!toDelete) return;
                    const name = toDelete.name;
                    try {
                        await deleteService.mutateAsync(toDelete.id);
                        toast.success(`${name} supprimé`);
                    } catch (e) {
                        toast.error("Suppression impossible", { description: e instanceof Error ? e.message : undefined });
                        throw e;
                    }
                }}
            />
        </>
    );
}
