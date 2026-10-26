"use client";

/**
 * Carte d'un service *arr (page Paramètres → Services *arr).
 * ----------------------------------------------------------------
 * - Bouton « Tester » visible (avant : caché dans un menu « ⋮ »), avec son
 *   PROPRE état de chargement (avant : un isPending global grisait toutes
 *   les cartes en même temps).
 * - Interrupteur Activé/Désactivé direct (mise à jour optimiste).
 * - Statut en français + date du dernier contrôle.
 * - Suppression → confirmation gérée par la page (ConfirmDialog).
 * - Test en échec : la CAUSE reste affichée sur la carte (délai dépassé,
 *   connexion refusée, clé refusée…). Si l'appli répond sur son nom Docker
 *   (cas typique du Synology, où l'IP du NAS est injoignable depuis un
 *   conteneur), un bouton propose de passer à cette adresse en un clic.
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Clock, Loader2, Pencil, Trash2, Wand2, X, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { StatusDot } from "@/components/fx/status-dot";
import { TypeIcon } from "@/components/services/service-config";
import { serviceVisual, statusLabel } from "@/components/services/service-meta";
import { useTestConnection, useUpdateService } from "@/hooks/use-services";
import { formatLongDateTime, timeAgo } from "@/lib/format";
import { scaleIn } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { ArrService, TestConnectionResult } from "@/types/service";

interface ServiceCardProps {
    service: ArrService;
    onEdit: (service: ArrService) => void;
    onDelete: (service: ArrService) => void;
}

export function ServiceCard({ service, onEdit, onDelete }: ServiceCardProps) {
    const visual = serviceVisual(service.type);
    const test = useTestConnection();
    const update = useUpdateService();

    const disabled = !service.is_enabled;
    const status = disabled ? "unknown" : service.last_status ?? "unknown";
    const lastCheck = service.last_health_check;

    // Dernier test en échec qui a un diagnostic : reste affiché jusqu'au test suivant
    const [diagnosis, setDiagnosis] = useState<TestConnectionResult | null>(null);

    const runTest = () =>
        test.mutate(service.id, {
            onSuccess: (r) => {
                setDiagnosis(!r.success && (r.diagnosis || r.suggested_url) ? r : null);
                if (r.success) {
                    toast.success(`${service.name} répond`, {
                        description: [r.latency_ms != null ? `${r.latency_ms} ms` : null, r.version ? `v${r.version}` : null]
                            .filter(Boolean)
                            .join(" · "),
                    });
                } else {
                    toast.error(`${service.name} ne répond pas`, { description: r.diagnosis ?? r.error ?? statusLabel(r.status) });
                }
            },
            onError: (e) => toast.error(`Test de ${service.name} impossible`, { description: e.message }),
        });

    // Passe à l'adresse proposée (nom Docker), puis re-teste pour confirmer
    const applySuggested = (url: string) =>
        update.mutate(
            { id: service.id, data: { url } },
            {
                onSuccess: () => {
                    toast.success("Adresse mise à jour", { description: url });
                    setDiagnosis(null);
                    runTest();
                },
                onError: (e) => toast.error("Changement refusé", { description: e.message }),
            },
        );

    const toggle = (next: boolean) =>
        update.mutate(
            { id: service.id, data: { is_enabled: next } },
            {
                onSuccess: () => toast.success(next ? `${service.name} réactivé` : `${service.name} désactivé`),
                onError: (e) => toast.error("Changement refusé", { description: e.message }),
            },
        );

    return (
        <motion.div layout variants={scaleIn} exit={{ opacity: 0, scale: 0.94, transition: { duration: 0.2 } }}>
            <SpotlightCard interactive className={cn("group relative h-full overflow-hidden", disabled && "opacity-70")}>

                <div className="relative z-[2] flex h-full flex-col gap-4 p-4">
                    {/* En-tête : icône, nom, interrupteur */}
                    <div className="flex items-start gap-3">
                        <TypeIcon type={service.type} />
                        <div className="min-w-0 flex-1">
                            <h3 className="truncate font-semibold leading-tight">{service.name}</h3>
                            {/* Type + rôle ; le type est omis s'il est déjà le nom (« Radarr / Radarr »). */}
                            <p className="truncate text-xs text-muted-foreground">
                                {service.name.trim().toLowerCase() === visual.label.toLowerCase() ? visual.role : `${visual.label} · ${visual.role}`}
                            </p>
                        </div>
                        <Switch
                            checked={service.is_enabled}
                            onCheckedChange={toggle}
                            disabled={update.isPending}
                            aria-label={service.is_enabled ? `Désactiver ${service.name}` : `Activer ${service.name}`}
                        />
                    </div>

                    <p className="truncate rounded-lg bg-background/40 px-2.5 py-1.5 font-mono text-xs text-muted-foreground" title={service.url}>
                        {service.url}
                    </p>

                    {/* Statut + latence + version */}
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span
                            className={cn(
                                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-medium",
                                disabled
                                    ? "bg-slate-500/10 text-slate-300"
                                    : status === "online"
                                      ? "bg-success/10 text-success"
                                      : status === "offline"
                                        ? "bg-destructive/10 text-destructive"
                                        : status === "degraded"
                                          ? "bg-warning/10 text-warning"
                                          : "bg-slate-500/10 text-slate-300",
                            )}
                        >
                            <StatusDot tone={status} size="sm" />
                            {disabled ? "Désactivé" : statusLabel(status)}
                        </span>
                        {!disabled && status === "online" && service.last_latency_ms != null && (
                            <span className="rounded-full bg-white/[0.04] px-2 py-0.5 tabular-nums text-muted-foreground">
                                {service.last_latency_ms} ms
                            </span>
                        )}
                        {service.version && (
                            <span className="rounded-full bg-white/[0.04] px-2 py-0.5 font-mono text-muted-foreground">v{service.version}</span>
                        )}
                    </div>

                    {diagnosis && !disabled && (
                        <div
                            data-testid="service-diagnosis"
                            role="status"
                            className="flex flex-col gap-2 rounded-lg border border-warning/25 bg-warning/10 p-2.5 text-xs text-warning"
                        >
                            <div className="flex items-start gap-2">
                                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                <p className="min-w-0 flex-1 break-words leading-relaxed">
                                    {diagnosis.diagnosis ?? "La connexion a échoué."}
                                    {diagnosis.suggested_url && (
                                        <>
                                            {" "}
                                            {service.name} répond en revanche sur{" "}
                                            <span className="font-mono">{diagnosis.suggested_url}</span>.
                                        </>
                                    )}
                                </p>
                                <button
                                    type="button"
                                    onClick={() => setDiagnosis(null)}
                                    className="shrink-0 rounded p-0.5 opacity-70 hover:opacity-100"
                                    aria-label="Masquer le diagnostic"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            </div>
                            {diagnosis.suggested_url && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="self-start"
                                    onClick={() => applySuggested(diagnosis.suggested_url!)}
                                    disabled={update.isPending || test.isPending}
                                >
                                    {update.isPending ? <Loader2 className="animate-spin" /> : <Wand2 />}
                                    Utiliser {diagnosis.suggested_url}
                                </Button>
                            )}
                        </div>
                    )}

                    <div className="mt-auto flex items-center gap-1.5 border-t border-white/[0.05] pt-3">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <span className="mr-auto flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
                                    <Clock className="h-3 w-3 shrink-0" />
                                    <span className="truncate">{lastCheck ? timeAgo(lastCheck) : "Jamais vérifié"}</span>
                                </span>
                            </TooltipTrigger>
                            {lastCheck && <TooltipContent>Dernier contrôle : {formatLongDateTime(lastCheck)}</TooltipContent>}
                        </Tooltip>
                        <Button size="sm" variant="outline" onClick={runTest} disabled={test.isPending || disabled}>
                            {test.isPending ? <Loader2 className="animate-spin" /> : <Zap />}
                            Tester
                        </Button>
                        <Button size="icon-sm" variant="ghost" onClick={() => onEdit(service)} aria-label={`Modifier ${service.name}`}>
                            <Pencil />
                        </Button>
                        <Button
                            size="icon-sm"
                            variant="ghost"
                            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => onDelete(service)}
                            aria-label={`Supprimer ${service.name}`}
                        >
                            <Trash2 />
                        </Button>
                    </div>
                </div>
            </SpotlightCard>
        </motion.div>
    );
}
