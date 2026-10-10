"use client";

/**
 * Boîte « Appliquer les recommandations TRaSH » (Dialog shadcn).
 * ----------------------------------------------------------------
 * Remplace l'ancienne modale faite main. Pour chaque Sonarr/Radarr :
 *  1. « Aperçu » : simulation (`dry_run`) → combien de formats seraient
 *     créés / mis à jour, sans rien modifier ;
 *  2. « Appliquer » : écriture réelle, avec le détail du résultat (y
 *     compris les erreurs, qui n'étaient jamais montrées).
 * L'état « en cours » est suivi PAR SERVICE (avant : un seul `isPending`
 * partagé bloquait/animait tous les boutons à la fois).
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Eye, Film, Loader2, Tv, XCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusDot } from "@/components/fx/status-dot";
import { useServices } from "@/hooks/use-services";
import { useTrashApply, type ApplyResult, type RecommendedProfile } from "@/hooks/use-trash-guides";
import { plural } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Pending = "preview" | "apply";

interface ServiceState {
    preview?: ApplyResult;
    applied?: ApplyResult;
}

export function ApplyDialog({
    open,
    onOpenChange,
    recommendations,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    recommendations: RecommendedProfile[];
}) {
    const { data: services, isLoading } = useServices();
    const apply = useTrashApply();
    const [pending, setPending] = useState<Record<number, Pending | undefined>>({});
    const [results, setResults] = useState<Record<number, ServiceState>>({});

    // Filtre calculé une seule fois (l'ancien code le refaisait 2× par rendu).
    const arrServices = useMemo(
        () => (services ?? []).filter((s) => ["sonarr", "radarr"].includes(s.type.toLowerCase())),
        [services],
    );
    const busy = Object.values(pending).some(Boolean);

    const run = async (serviceId: number, serviceName: string, profileIds: string[], dryRun: boolean) => {
        setPending((p) => ({ ...p, [serviceId]: dryRun ? "preview" : "apply" }));
        try {
            const res = await apply.mutateAsync({ service_id: serviceId, recommendations: profileIds, dry_run: dryRun });
            setResults((r) => ({ ...r, [serviceId]: { ...r[serviceId], [dryRun ? "preview" : "applied"]: res } }));
            if (dryRun) return;
            if (res.success) {
                toast.success(`${serviceName} : configuration appliquée`, {
                    description: `${plural(res.cfs_created, "format créé", "formats créés")}, ${plural(res.cfs_updated, "format mis à jour", "formats mis à jour")}.`,
                });
            } else {
                toast.warning(`${serviceName} : appliqué avec ${plural(res.errors.length, "erreur")}`, {
                    description: res.errors[0],
                });
            }
        } catch (e) {
            toast.error(`${serviceName} : échec`, { description: e instanceof Error ? e.message : undefined });
        } finally {
            setPending((p) => ({ ...p, [serviceId]: undefined }));
        }
    };

    const handleOpenChange = (next: boolean) => {
        if (busy) return; // on ne ferme pas au milieu d'une écriture
        if (!next) setResults({});
        onOpenChange(next);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Zap className="h-5 w-5 text-orange-300" />
                        Appliquer à tes services
                    </DialogTitle>
                    <DialogDescription>
                        Fais d&apos;abord un aperçu pour voir ce qui changera : rien n&apos;est modifié tant que tu ne
                        cliques pas sur « Appliquer ».
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="flex items-center justify-center py-10">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : arrServices.length === 0 ? (
                    <EmptyState
                        compact
                        icon={Tv}
                        title="Aucun Sonarr ou Radarr configuré"
                        description="Ajoute un service pour pouvoir y appliquer les profils."
                        action={{ label: "Ajouter un service", href: "/settings/services" }}
                    />
                ) : (
                    <ul className="space-y-2.5">
                        {arrServices.map((svc) => {
                            const type = svc.type.toLowerCase();
                            const recs = recommendations.filter((r) => r.service_type === type);
                            const profileIds = recs.map((r) => r.profile_id);
                            const state = results[svc.id] ?? {};
                            const p = pending[svc.id];
                            const Icon = type === "sonarr" ? Tv : Film;
                            return (
                                <li key={svc.id} className="rounded-2xl bg-white/[0.03] p-3.5 ring-1 ring-white/[0.06]">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <span
                                            className={cn(
                                                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1",
                                                type === "sonarr"
                                                    ? "bg-sky-500/15 text-sky-300 ring-sky-400/25"
                                                    : "bg-violet-500/15 text-violet-300 ring-violet-400/25",
                                            )}
                                        >
                                            <Icon className="h-4 w-4" />
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <p className="flex items-center gap-2 text-sm font-semibold">
                                                <StatusDot tone={svc.last_status === "online" ? "online" : svc.last_status === "offline" ? "offline" : "unknown"} size="sm" />
                                                <span className="truncate">{svc.name}</span>
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {recs.length === 0
                                                    ? "Aucun profil recommandé pour ce type de service"
                                                    : plural(recs.length, "profil à appliquer", "profils à appliquer")}
                                            </p>
                                        </div>
                                        <div className="flex gap-1.5">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                disabled={!!p || recs.length === 0}
                                                onClick={() => run(svc.id, svc.name, profileIds, true)}
                                            >
                                                {p === "preview" ? <Loader2 className="animate-spin" /> : <Eye />}
                                                Aperçu
                                            </Button>
                                            <Button
                                                size="sm"
                                                disabled={!!p || recs.length === 0}
                                                onClick={() => run(svc.id, svc.name, profileIds, false)}
                                            >
                                                {p === "apply" ? <Loader2 className="animate-spin" /> : <Zap />}
                                                {state.applied ? "Réappliquer" : "Appliquer"}
                                            </Button>
                                        </div>
                                    </div>

                                    <AnimatePresence initial={false}>
                                        {(state.preview || state.applied) && (
                                            <motion.div
                                                initial={{ opacity: 0, height: 0 }}
                                                animate={{ opacity: 1, height: "auto" }}
                                                exit={{ opacity: 0, height: 0 }}
                                                transition={{ duration: 0.3, ease: EASE_OUT }}
                                                className="overflow-hidden"
                                            >
                                                <div className="mt-3 space-y-2">
                                                    {state.preview && !state.applied && <ResultLine result={state.preview} dryRun />}
                                                    {state.applied && <ResultLine result={state.applied} />}
                                                </div>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </li>
                            );
                        })}
                    </ul>
                )}

                <DialogFooter>
                    <Button variant="ghost" onClick={() => handleOpenChange(false)} disabled={busy}>
                        Fermer
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/** Détail d'un résultat (aperçu ou application réelle). */
function ResultLine({ result, dryRun }: { result: ApplyResult; dryRun?: boolean }) {
    const ok = result.success;
    const parts = [
        dryRun ? plural(result.cfs_created, "format à créer", "formats à créer") : plural(result.cfs_created, "format créé", "formats créés"),
        dryRun
            ? plural(result.cfs_updated, "format à mettre à jour", "formats à mettre à jour")
            : plural(result.cfs_updated, "format mis à jour", "formats mis à jour"),
    ];
    if (result.profiles_created) parts.push(plural(result.profiles_created, "profil créé", "profils créés"));
    if (result.profiles_updated) parts.push(plural(result.profiles_updated, "profil mis à jour", "profils mis à jour"));

    return (
        <div
            className={cn(
                "rounded-xl px-3 py-2 text-xs ring-1",
                dryRun
                    ? "bg-primary/10 text-primary ring-primary/20"
                    : ok
                      ? "bg-emerald-500/10 text-emerald-300 ring-emerald-400/20"
                      : "bg-amber-500/10 text-amber-300 ring-amber-400/20",
            )}
        >
            <p className="flex items-center gap-1.5 font-medium">
                {dryRun ? (
                    <Eye className="h-3.5 w-3.5" />
                ) : ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                    <AlertTriangle className="h-3.5 w-3.5" />
                )}
                {dryRun ? "Aperçu : " : ok ? "Appliqué : " : "Appliqué partiellement : "}
                {parts.join(" · ")}
            </p>
            {result.errors.length > 0 && (
                <ul className="mt-1.5 max-h-28 space-y-1 overflow-y-auto pr-1 text-[11px] text-red-300">
                    {result.errors.map((err, i) => (
                        <li key={`${i}:${err}`} className="flex gap-1.5">
                            <XCircle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span className="break-words">{err}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
