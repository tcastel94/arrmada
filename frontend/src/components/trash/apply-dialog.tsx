"use client";

/**
 * Boîte « Appliquer les recommandations TRaSH » (Dialog shadcn).
 * ----------------------------------------------------------------
 * Pour chaque Sonarr/Radarr :
 *  1. « Aperçu » (OBLIGATOIRE avant d'appliquer) : simulation `dry_run` qui
 *     détaille tout ce qui serait écrit — formats à créer / modifier, profil
 *     qualité (palier d'arrêt, scores minimum et d'arrêt, score de chaque
 *     format), tailles de qualité. Rien n'est modifié.
 *  2. « Appliquer » : écriture réelle, avec le détail du résultat.
 *  3. Ensuite, « Basculer la bibliothèque » : propose de passer les films /
 *     séries existants sur le nouveau profil (compte d'abord, puis
 *     confirmation). Jamais fait d'office : un profil ne joue que sur les
 *     prochaines recherches, rien n'est re-téléchargé.
 *
 * Retour d'installation réelle : l'ancien « Appliquer » ne créait que des
 * formats à score 0 (aucun effet) et l'aperçu n'affichait qu'un compteur.
 */
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRightLeft, CheckCircle2, ChevronDown, Eye, Film, Loader2, Tv, XCircle, Zap } from "lucide-react";
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
import {
    useTrashApply,
    useTrashAssign,
    type ApplyResult,
    type AssignResult,
    type MediaPreferences,
    type ProfileChange,
    type RecommendedProfile,
} from "@/hooks/use-trash-guides";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

type Pending = "preview" | "apply" | "assign";

interface ServiceState {
    preview?: ApplyResult;
    applied?: ApplyResult;
    /** Compte de la bascule (dry_run), puis résultat réel. */
    assign?: AssignResult;
    assignDone?: AssignResult;
}

const ACTION_LABEL: Record<ProfileChange["action"], { preview: string; done: string }> = {
    created: { preview: "sera créé", done: "créé" },
    updated: { preview: "sera mis à jour", done: "mis à jour" },
    unchanged: { preview: "déjà à jour", done: "déjà à jour" },
};

export function ApplyDialog({
    open,
    onOpenChange,
    recommendations,
    prefs,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    recommendations: RecommendedProfile[];
    /** Réponses de l'assistant : choisissent les groupes liés à l'écran et à l'audio. */
    prefs?: MediaPreferences;
}) {
    const { data: services, isLoading } = useServices();
    const apply = useTrashApply();
    const assign = useTrashAssign();
    const [pending, setPending] = useState<Record<number, Pending | undefined>>({});
    const [results, setResults] = useState<Record<number, ServiceState>>({});

    const arrServices = useMemo(
        () => (services ?? []).filter((s) => ["sonarr", "radarr"].includes(s.type.toLowerCase())),
        [services],
    );
    const busy = Object.values(pending).some(Boolean);

    const update = (id: number, patch: Partial<ServiceState>) => setResults((r) => ({ ...r, [id]: { ...r[id], ...patch } }));

    const run = async (serviceId: number, serviceName: string, profileIds: string[], dryRun: boolean) => {
        setPending((p) => ({ ...p, [serviceId]: dryRun ? "preview" : "apply" }));
        try {
            const res = await apply.mutateAsync({ service_id: serviceId, recommendations: profileIds, dry_run: dryRun, prefs });
            if (dryRun) {
                update(serviceId, { preview: res, applied: undefined, assign: undefined, assignDone: undefined });
                return;
            }
            update(serviceId, { applied: res });
            if (res.success) {
                toast.success(`${serviceName} : configuration appliquée`, {
                    description: `${plural(res.cfs_created, "format créé", "formats créés")}, profil ${res.profiles[0]?.name ?? ""} ${ACTION_LABEL[res.profiles[0]?.action ?? "unchanged"].done}.`,
                });
                // Combien de titres n'utilisent pas encore ce profil ?
                const profile = res.profiles[0];
                if (profile) {
                    const count = await assign.mutateAsync({ service_id: serviceId, profile_name: profile.name, dry_run: true });
                    update(serviceId, { assign: count });
                }
            } else {
                toast.warning(`${serviceName} : appliqué avec ${plural(res.errors.length, "erreur")}`, { description: res.errors[0] });
            }
        } catch (e) {
            toast.error(`${serviceName} : échec`, { description: e instanceof Error ? e.message : undefined });
        } finally {
            setPending((p) => ({ ...p, [serviceId]: undefined }));
        }
    };

    const switchLibrary = async (serviceId: number, serviceName: string, profileName: string) => {
        setPending((p) => ({ ...p, [serviceId]: "assign" }));
        try {
            const res = await assign.mutateAsync({ service_id: serviceId, profile_name: profileName, dry_run: false });
            update(serviceId, { assignDone: res });
            toast.success(`${serviceName} : ${plural(res.changed, "titre basculé", "titres basculés")} sur ${res.profile}`);
        } catch (e) {
            toast.error(`${serviceName} : bascule impossible`, { description: e instanceof Error ? e.message : undefined });
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
            <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Zap className="h-5 w-5 text-orange-300" />
                        Appliquer à tes services
                    </DialogTitle>
                    <DialogDescription>
                        Commence par l&apos;aperçu : il détaille les formats, le profil qualité (avec le score de chaque
                        format) et les tailles qui seront écrits. Rien n&apos;est modifié avant « Appliquer ».
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
                    <ul className="space-y-3">
                        {arrServices.map((svc) => {
                            const type = svc.type.toLowerCase();
                            const recs = recommendations.filter((r) => r.service_type === type);
                            const profileIds = recs.map((r) => r.profile_id);
                            const state = results[svc.id] ?? {};
                            const p = pending[svc.id];
                            const Icon = type === "sonarr" ? Tv : Film;
                            const shown = state.applied ?? state.preview;
                            const profileName = state.applied?.profiles[0]?.name;
                            return (
                                <li key={svc.id} className="rounded-2xl bg-white/[0.03] p-3.5 ring-1 ring-white/[0.06]">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25">
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
                                                    : recs.map((r) => r.trash_name || r.profile_name).join(" · ")}
                                            </p>
                                        </div>
                                        <div className="flex gap-1.5">
                                            <Button variant="outline" size="sm" disabled={!!p || recs.length === 0} onClick={() => run(svc.id, svc.name, profileIds, true)}>
                                                {p === "preview" ? <Loader2 className="animate-spin" /> : <Eye />}
                                                Aperçu
                                            </Button>
                                            <Button
                                                size="sm"
                                                disabled={!!p || recs.length === 0 || !state.preview}
                                                title={state.preview ? undefined : "Fais d'abord l'aperçu"}
                                                onClick={() => run(svc.id, svc.name, profileIds, false)}
                                            >
                                                {p === "apply" ? <Loader2 className="animate-spin" /> : <Zap />}
                                                {state.applied ? "Réappliquer" : "Appliquer"}
                                            </Button>
                                        </div>
                                    </div>

                                    {shown && <ResultDetail result={shown} dryRun={!state.applied} />}

                                    {/* Bascule de la bibliothèque, proposée après une application réussie */}
                                    {state.applied?.success && profileName && state.assign && (
                                        <div className="mt-3 rounded-xl bg-primary/[0.07] p-3 text-xs ring-1 ring-primary/20">
                                            {state.assignDone ? (
                                                <p className="flex items-center gap-1.5 font-medium text-success">
                                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                                    {plural(state.assignDone.changed, "titre basculé", "titres basculés")} sur « {state.assignDone.profile} ».
                                                </p>
                                            ) : state.assign.total === 0 ? (
                                                <p className="text-muted-foreground">
                                                    Bibliothèque encore vide : les prochains ajouts pourront choisir ce profil.
                                                </p>
                                            ) : state.assign.to_change === 0 ? (
                                                <p className="text-muted-foreground">
                                                    Les {state.assign.total} titres utilisent déjà ce profil.
                                                </p>
                                            ) : (
                                                <div className="flex flex-wrap items-center gap-3">
                                                    <p className="min-w-0 flex-1">
                                                        <span className="font-semibold text-foreground">
                                                            {plural(state.assign.to_change, "titre", "titres")} sur {state.assign.total}
                                                        </span>{" "}
                                                        <span className="text-muted-foreground">
                                                            utilisent encore un autre profil. Les basculer sur « {profileName} » ? Rien n&apos;est
                                                            re-téléchargé : le profil joue sur les prochaines recherches et mises à niveau.
                                                        </span>
                                                    </p>
                                                    <Button size="sm" variant="tinted" disabled={!!p} onClick={() => switchLibrary(svc.id, svc.name, profileName)}>
                                                        {p === "assign" ? <Loader2 className="animate-spin" /> : <ArrowRightLeft />}
                                                        Basculer {plural(state.assign.to_change, "titre", "titres")}
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    )}
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

/** Détail complet d'un aperçu ou d'une application. */
function ResultDetail({ result, dryRun }: { result: ApplyResult; dryRun: boolean }) {
    const [open, setOpen] = useState<"formats" | "scores" | "sizes" | null>(null);
    const ok = result.success;
    const profile = result.profiles[0];
    const toggle = (key: "formats" | "scores" | "sizes") => setOpen((o) => (o === key ? null : key));
    const verb = (preview: string, done: string) => (dryRun ? preview : done);

    return (
        <div
            data-testid="apply-detail"
            className={cn(
                "mt-3 space-y-2.5 rounded-xl px-3 py-2.5 text-xs ring-1",
                dryRun ? "bg-primary/[0.06] ring-primary/20" : ok ? "bg-success/[0.07] ring-success/20" : "bg-warning/10 ring-warning/20",
            )}
        >
            <p className={cn("flex items-center gap-1.5 font-semibold", dryRun ? "text-primary" : ok ? "text-success" : "text-warning")}>
                {dryRun ? <Eye className="h-3.5 w-3.5" /> : ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                {dryRun ? "Aperçu : rien n'a encore été modifié" : ok ? "Appliqué" : "Appliqué partiellement"}
            </p>

            {/* Formats */}
            <Row
                label="Formats personnalisés"
                value={`${plural(result.cfs_created, verb("à créer", "créé"), verb("à créer", "créés"))} · ${plural(
                    result.cfs_updated,
                    verb("à mettre à jour", "mis à jour"),
                    verb("à mettre à jour", "mis à jour"),
                )} · ${result.cfs_unchanged} déjà à jour`}
                expandable={result.created_formats.length + result.updated_formats.length > 0}
                expanded={open === "formats"}
                onToggle={() => toggle("formats")}
            />
            {open === "formats" && (
                <div className="flex flex-wrap gap-1 pl-1">
                    {result.created_formats.map((n) => (
                        <span key={`c:${n}`} className="rounded-md bg-success/10 px-1.5 py-0.5 font-mono text-[10px] text-success">
                            + {n}
                        </span>
                    ))}
                    {result.updated_formats.map((n) => (
                        <span key={`u:${n}`} className="rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary">
                            ~ {n}
                        </span>
                    ))}
                </div>
            )}

            {/* Profil qualité */}
            {profile && (
                <>
                    <Row
                        label="Profil qualité"
                        value={`« ${profile.name} » ${ACTION_LABEL[profile.action][dryRun ? "preview" : "done"]}`}
                    />
                    <div className="grid grid-cols-1 gap-x-4 gap-y-1 pl-1 text-muted-foreground sm:grid-cols-2">
                        <span>
                            Palier d&apos;arrêt : <span className="text-foreground">{profile.cutoff}</span>
                        </span>
                        <span>
                            Score minimum <span className="text-foreground tabular-nums">{profile.min_format_score}</span> · d&apos;arrêt{" "}
                            <span className="text-foreground tabular-nums">{profile.cutoff_format_score}</span>
                        </span>
                        <span className="sm:col-span-2">
                            Qualités : <span className="text-foreground">{profile.qualities.join(", ")}</span>
                        </span>
                        {profile.groups.length > 0 && (
                            <span className="sm:col-span-2">
                                Groupes TRaSH : <span className="text-foreground">{profile.groups.join(", ")}</span>
                            </span>
                        )}
                    </div>
                    <Row
                        label="Scores des formats"
                        value={`${plural(profile.scores.filter((s) => s.score > 0).length, "favorisé", "favorisés")} · ${plural(
                            profile.scores.filter((s) => s.score < 0).length,
                            "écarté",
                            "écartés",
                        )} · les autres formats du service passent à 0`}
                        expandable={profile.scores.length > 0}
                        expanded={open === "scores"}
                        onToggle={() => toggle("scores")}
                    />
                    {open === "scores" && (
                        <ul className="max-h-48 space-y-0.5 overflow-y-auto pl-1 pr-1">
                            {profile.scores.map((s) => (
                                <li key={s.name} className="flex items-center justify-between gap-3">
                                    <span className="truncate font-mono text-[11px]" title={s.source}>
                                        {s.name}
                                    </span>
                                    <span
                                        className={cn(
                                            "shrink-0 font-mono text-[11px] tabular-nums",
                                            s.score > 0 ? "text-success" : s.score < 0 ? "text-destructive" : "text-muted-foreground",
                                        )}
                                    >
                                        {s.score > 0 ? `+${s.score}` : s.score}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                    {profile.unknown_qualities.length > 0 && (
                        <p className="text-warning">
                            Qualités inconnues de ce service (version ancienne ?) : {profile.unknown_qualities.join(", ")}
                        </p>
                    )}
                </>
            )}

            {/* Tailles */}
            <Row
                label="Tailles de qualité"
                value={result.sizes.length === 0 ? "déjà à jour" : plural(result.sizes.length, verb("à ajuster", "ajustée"), verb("à ajuster", "ajustées"))}
                expandable={result.sizes.length > 0}
                expanded={open === "sizes"}
                onToggle={() => toggle("sizes")}
            />
            {open === "sizes" && (
                <table className="w-full text-[11px] tabular-nums">
                    <thead className="text-muted-foreground">
                        <tr>
                            <th className="text-left font-medium">Qualité (Mo/min)</th>
                            <th className="text-right font-medium">Min</th>
                            <th className="text-right font-medium">Préférée</th>
                            <th className="text-right font-medium">Max</th>
                        </tr>
                    </thead>
                    <tbody>
                        {result.sizes.map((z) => (
                            <tr key={z.quality}>
                                <td>{z.quality}</td>
                                <td className="text-right">{z.min}</td>
                                <td className="text-right">{z.preferred ?? "∞"}</td>
                                <td className="text-right">{z.max ?? "∞"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {[...result.warnings, ...result.errors].length > 0 && (
                <ul className="max-h-28 space-y-1 overflow-y-auto pr-1 text-[11px]">
                    {result.warnings.map((w, i) => (
                        <li key={`w${i}:${w}`} className="flex gap-1.5 text-warning">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span className="break-words">{w}</span>
                        </li>
                    ))}
                    {result.errors.map((err, i) => (
                        <li key={`e${i}:${err}`} className="flex gap-1.5 text-destructive">
                            <XCircle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span className="break-words">{err}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

function Row({
    label,
    value,
    expandable,
    expanded,
    onToggle,
}: {
    label: string;
    value: string;
    expandable?: boolean;
    expanded?: boolean;
    onToggle?: () => void;
}) {
    const content = (
        <>
            <span className="shrink-0 font-medium text-foreground">{label}</span>
            <span className="min-w-0 flex-1 text-muted-foreground">{value}</span>
            {expandable && <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180")} />}
        </>
    );
    return expandable ? (
        <button type="button" onClick={onToggle} className="flex w-full items-start gap-2 text-left hover:opacity-90" aria-expanded={expanded}>
            {content}
        </button>
    ) : (
        <div className="flex items-start gap-2">{content}</div>
    );
}
