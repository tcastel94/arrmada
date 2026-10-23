"use client";

/**
 * Onglet « Profils par média » de /trash-guides (ex-page
 * /settings/profile-overrides).
 * ----------------------------------------------------------------
 * Un override force un profil TRaSH pour UN film / UNE série. Il doit
 * ensuite être appliqué pour que Sonarr/Radarr basculent réellement :
 * d'où « Appliquer » par ligne et « Tout appliquer » (l'ancienne page
 * créait des overrides… jamais appliqués).
 * Autres corrections : suppression confirmée avec retour visuel, nom
 * lisible du profil, service et lien vers la fiche affichés.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Film, Loader2, Plus, Search, Target, Trash2, Tv, Zap } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    useApplyOverride,
    useAvailableProfiles,
    useDeleteOverride,
    useProfileOverrides,
    type ProfileOverride,
} from "@/hooks/use-profile-overrides";
import { useServices } from "@/hooks/use-services";
import { useDebounce } from "@/hooks/use-debounce";
import { plural, timeAgo } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { usePrimaryInstance } from "@/components/health/use-primary-instance";
import { AddOverrideDialog } from "./add-override-dialog";
import { notifyApplyResult } from "./notify";

/** Repli lisible quand le nom du profil n'est pas (encore) connu. */
function prettifyProfile(filename: string): string {
    return filename.replace(/[-_]/g, " ");
}

export function OverridesPanel() {
    const { data: overrides, isLoading, isError, error, refetch } = useProfileOverrides();
    const { data: services } = useServices();
    const { data: sonarrProfiles } = useAvailableProfiles("sonarr");
    const { data: radarrProfiles } = useAvailableProfiles("radarr");
    const applyOverride = useApplyOverride();
    const deleteOverride = useDeleteOverride();
    const { isActionable } = usePrimaryInstance();

    const [search, setSearch] = useState("");
    const debounced = useDebounce(search, 200);
    const [addOpen, setAddOpen] = useState(false);
    const [pending, setPending] = useState<Record<number, "apply" | "delete" | undefined>>({});
    const [applied, setApplied] = useState<Set<number>>(new Set());
    const [toDelete, setToDelete] = useState<ProfileOverride | null>(null);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [bulkRunning, setBulkRunning] = useState(false);

    // Index nom de fichier → nom lisible, et ID → service.
    const profileNames = useMemo(() => {
        const map = new Map<string, string>();
        for (const p of [...(sonarrProfiles ?? []), ...(radarrProfiles ?? [])]) map.set(p.filename, p.display_name);
        return map;
    }, [sonarrProfiles, radarrProfiles]);
    const serviceById = useMemo(() => new Map((services ?? []).map((s) => [s.id, s])), [services]);

    const filtered = useMemo(() => {
        const q = debounced.trim().toLowerCase();
        const list = overrides ?? [];
        return q ? list.filter((o) => o.title.toLowerCase().includes(q)) : list;
    }, [overrides, debounced]);

    const profileLabel = (o: ProfileOverride) => profileNames.get(o.profile_name) ?? prettifyProfile(o.profile_name);

    const applyOne = async (o: ProfileOverride, silent = false): Promise<boolean> => {
        setPending((p) => ({ ...p, [o.id]: "apply" }));
        try {
            const res = await applyOverride.mutateAsync(o.id);
            if (!silent) notifyApplyResult(o.title, profileLabel(o), res);
            if (res.success) setApplied((s) => new Set(s).add(o.id));
            return res.success;
        } catch (e) {
            if (!silent) toast.error(`Échec pour « ${o.title} »`, { description: e instanceof Error ? e.message : undefined });
            return false;
        } finally {
            setPending((p) => ({ ...p, [o.id]: undefined }));
        }
    };

    /** Applique tous les overrides un par un (pour ne pas saturer Sonarr/Radarr). */
    const applyAll = async () => {
        const list = overrides ?? [];
        if (list.length === 0) return;
        setBulkRunning(true);
        const id = toast.loading(`Application 0/${list.length}…`);
        let ok = 0;
        for (let i = 0; i < list.length; i++) {
            toast.loading(`Application ${i + 1}/${list.length} : ${list[i].title}`, { id });
            if (await applyOne(list[i], true)) ok++;
        }
        setBulkRunning(false);
        const failed = list.length - ok;
        if (failed === 0) toast.success(`${plural(ok, "override appliqué", "overrides appliqués")}`, { id });
        else toast.warning(`${ok}/${list.length} appliqués, ${plural(failed, "échec")}`, { id, description: "Applique les lignes en échec une par une pour voir le détail." });
    };

    const confirmDelete = async () => {
        if (!toDelete) return;
        const o = toDelete;
        setPending((p) => ({ ...p, [o.id]: "delete" }));
        try {
            await deleteOverride.mutateAsync(o.id);
            toast.success(`Override supprimé pour « ${o.title} »`, {
                description: "Le média reviendra au profil par défaut lors de la prochaine application TRaSH.",
            });
        } catch (e) {
            toast.error("Suppression impossible", { description: e instanceof Error ? e.message : undefined });
            throw e;
        } finally {
            setPending((p) => ({ ...p, [o.id]: undefined }));
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-3">
                <Shimmer className="h-12 w-full rounded-2xl" />
                {Array.from({ length: 4 }).map((_, i) => (
                    <Shimmer key={i} className="h-20 w-full rounded-2xl" />
                ))}
            </div>
        );
    }
    if (isError) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Overrides indisponibles" />
            </Panel>
        );
    }

    const total = overrides?.length ?? 0;

    return (
        <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative w-full sm:max-w-xs">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        placeholder="Chercher un titre…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9"
                        aria-label="Filtrer les overrides"
                    />
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={applyAll} disabled={total === 0 || bulkRunning}>
                        {bulkRunning ? <Loader2 className="animate-spin" /> : <Zap />}
                        Tout appliquer
                    </Button>
                    <Button onClick={() => setAddOpen(true)}>
                        <Plus />
                        Ajouter
                    </Button>
                </div>
            </div>

            <Panel
                title="Profils forcés par média"
                icon={Target}
                iconClassName="text-orange-300"
                bodyClassName="p-0"
                action={<span className="text-xs text-muted-foreground tabular-nums">{plural(total, "override")}</span>}
            >
                {total === 0 ? (
                    <EmptyState
                        icon={Target}
                        title="Aucun profil forcé"
                        description="Tous tes médias suivent le profil TRaSH par défaut. Force un profil pour un titre précis (ex : un anime en 1080p seulement)."
                        action={{ label: "Ajouter un override", onClick: () => setAddOpen(true) }}
                    />
                ) : filtered.length === 0 ? (
                    <EmptyState compact icon={Search} title="Aucun résultat" description={`Aucun override pour « ${debounced} ».`} />
                ) : (
                    <ul className="divide-y divide-white/[0.04]">
                        <AnimatePresence initial={false} mode="popLayout">
                            {filtered.map((o) => {
                                const svc = serviceById.get(o.service_id);
                                const isSeries = o.media_type === "series";
                                const Icon = isSeries ? Tv : Film;
                                const p = pending[o.id];
                                const href = isActionable(svc?.name, o.media_type) ? `/media/${o.media_type}/${o.external_id}` : undefined;
                                return (
                                    <motion.li
                                        key={o.id}
                                        layout
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: p === "delete" ? 0.5 : 1, y: 0 }}
                                        exit={{ opacity: 0, x: -24 }}
                                        transition={{ duration: 0.3, ease: EASE_OUT }}
                                        className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:px-5"
                                    >
                                        <div className="flex min-w-0 flex-1 items-start gap-3">
                                            <span
                                                className={cn(
                                                    "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1",
                                                    isSeries ? "bg-primary/15 text-primary ring-primary/25" : "bg-primary/15 text-primary ring-primary/25",
                                                )}
                                            >
                                                <Icon className="h-4 w-4" />
                                            </span>
                                            <div className="min-w-0">
                                                {href ? (
                                                    <Link href={href} className="block truncate text-sm font-semibold transition-colors hover:text-primary">
                                                        {o.title}
                                                    </Link>
                                                ) : (
                                                    <p className="truncate text-sm font-semibold">{o.title}</p>
                                                )}
                                                <p className="mt-0.5 text-xs text-muted-foreground">
                                                    {[isSeries ? "Série" : "Film", svc?.name ?? `Service #${o.service_id}`, o.created_at && `ajouté ${timeAgo(o.created_at).toLowerCase()}`]
                                                        .filter(Boolean)
                                                        .join(" · ")}
                                                </p>
                                                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                                    <span className="rounded-md border border-orange-400/30 bg-orange-500/10 px-1.5 py-0.5 text-[11px] font-medium text-orange-200">
                                                        {profileLabel(o)}
                                                    </span>
                                                    {o.note && <span className="text-xs text-muted-foreground">{o.note}</span>}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex shrink-0 items-center justify-end gap-1.5">
                                            <Button variant="outline" size="sm" disabled={!!p || bulkRunning} onClick={() => applyOne(o)}>
                                                {p === "apply" ? (
                                                    <Loader2 className="animate-spin" />
                                                ) : applied.has(o.id) ? (
                                                    <Check className="text-success" />
                                                ) : (
                                                    <Zap />
                                                )}
                                                {applied.has(o.id) ? "Appliqué" : "Appliquer"}
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon-sm"
                                                disabled={!!p || bulkRunning}
                                                onClick={() => {
                                                    setToDelete(o);
                                                    setDeleteOpen(true);
                                                }}
                                                aria-label={`Supprimer l'override de ${o.title}`}
                                                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                            >
                                                {p === "delete" ? <Loader2 className="animate-spin" /> : <Trash2 />}
                                            </Button>
                                        </div>
                                    </motion.li>
                                );
                            })}
                        </AnimatePresence>
                    </ul>
                )}
            </Panel>

            <AddOverrideDialog open={addOpen} onOpenChange={setAddOpen} existing={overrides ?? []} />

            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                destructive
                title="Supprimer cet override ?"
                description={
                    toDelete
                        ? `« ${toDelete.title} » ne sera plus forcé sur « ${profileLabel(toDelete)} ». Le profil actuel dans Sonarr/Radarr ne change pas tant que tu ne réappliques pas TRaSH.`
                        : undefined
                }
                confirmLabel="Supprimer"
                onConfirm={confirmDelete}
            />
        </div>
    );
}
