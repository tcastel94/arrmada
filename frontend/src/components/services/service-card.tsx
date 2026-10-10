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
 */
import { motion } from "framer-motion";
import { Clock, Loader2, Pencil, Trash2, Zap } from "lucide-react";
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
import type { ArrService } from "@/types/service";

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

    const runTest = () =>
        test.mutate(service.id, {
            onSuccess: (r) =>
                r.success
                    ? toast.success(`${service.name} répond`, {
                          description: [r.latency_ms != null ? `${r.latency_ms} ms` : null, r.version ? `v${r.version}` : null]
                              .filter(Boolean)
                              .join(" · "),
                      })
                    : toast.error(`${service.name} ne répond pas`, { description: r.error ?? statusLabel(r.status) }),
            onError: (e) => toast.error(`Test de ${service.name} impossible`, { description: e.message }),
        });

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
                {/* Lueur aux couleurs de l'application */}
                <span
                    aria-hidden
                    className="pointer-events-none absolute -left-10 -top-10 h-32 w-32 rounded-full opacity-20 blur-2xl transition-opacity duration-500 group-hover:opacity-40"
                    style={{ background: visual.color }}
                />

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
                                      ? "bg-emerald-500/10 text-emerald-300"
                                      : status === "offline"
                                        ? "bg-red-500/10 text-red-300"
                                        : status === "degraded"
                                          ? "bg-amber-500/10 text-amber-300"
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
                            className="text-muted-foreground hover:bg-red-500/10 hover:text-red-400"
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
