"use client";

/**
 * « Imports bloqués » : téléchargements SABnzbd terminés que Radarr/Sonarr
 * n'ont jamais importés (mauvaise catégorie, nom non reconnu…).
 * ----------------------------------------------------------------
 * Pour chaque ligne : choisir Film ou Série, puis importer seul ou en lot.
 * Corrections par rapport à l'ancienne page /fichiers :
 *  - l'import groupé est une TÂCHE DE FOND côté backend → les lignes passent
 *    à « Import lancé » (et non « Importé ✓ », qui était faux) ;
 *  - l'import unitaire affiche enfin un toast (succès ou erreur) ;
 *  - « Tout désélectionner » ;
 *  - liste relue toutes les 60 s : une ligne importée disparaît (animée) ;
 *  - cases à cocher et boutons Film/Série accessibles (role, aria-*).
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Check, CheckCircle2, Film, Loader2, Rocket, Tv, X, XCircle } from "lucide-react";
import { toast } from "sonner";
import { useBulkImport, useManualImport, useStuckDownloads, type StuckDownload } from "@/hooks/use-files";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { plural } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { frenchSize } from "./queue-meta";

type RowStatus = "idle" | "pending" | "launched" | "error";
type MediaType = "movie" | "series";

export function StuckImports() {
    const { data, isLoading, isError, error, refetch } = useStuckDownloads();
    const manualImport = useManualImport();
    const bulkImport = useBulkImport();

    // Choix de type faits par l'utilisateur (prioritaires sur la détection auto).
    const [typeOverrides, setTypeOverrides] = useState<Record<string, MediaType>>({});
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [statuses, setStatuses] = useState<Record<string, { status: RowStatus; message?: string }>>({});

    const stuck = useMemo(() => data?.items ?? [], [data]);

    const typeOf = (item: StuckDownload): string => typeOverrides[item.nzo_id] ?? item.media_type;
    const isReady = (item: StuckDownload) => typeOf(item) === "movie" || typeOf(item) === "series";

    const selectedItems = stuck.filter((it) => selected.has(it.nzo_id));
    const readyCount = selectedItems.filter(isReady).length;
    const bulkPending = bulkImport.isPending;

    const setRow = (ids: string[], status: RowStatus, message?: string) =>
        setStatuses((prev) => {
            const next = { ...prev };
            for (const id of ids) next[id] = { status, message };
            return next;
        });

    const toggleSelect = (id: string) =>
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });

    /** « Tout en Film / Série » : applique le type à toutes les lignes et les sélectionne. */
    const selectAllAs = (type: MediaType) => {
        const overrides: Record<string, MediaType> = {};
        for (const it of stuck) overrides[it.nzo_id] = type;
        setTypeOverrides((prev) => ({ ...prev, ...overrides }));
        setSelected(new Set(stuck.map((it) => it.nzo_id)));
    };

    const importOne = async (item: StuckDownload) => {
        const mediaType = typeOf(item);
        if (!isReady(item)) return;
        setRow([item.nzo_id], "pending");
        try {
            const res = await manualImport.mutateAsync({ download_path: item.storage_path, media_type: mediaType });
            if (res.success) {
                const detail = [
                    res.files_count ? plural(res.files_count, "fichier") : null,
                    res.service ? `envoyé à ${res.service}` : null,
                ]
                    .filter(Boolean)
                    .join(" · ");
                setRow([item.nzo_id], "launched", res.message);
                toast.success(`Import lancé : ${item.name}`, { description: res.message || detail || undefined });
            } else {
                setRow([item.nzo_id], "error", res.error || "Import refusé");
                toast.error(`Import impossible : ${item.name}`, { description: res.error || undefined });
            }
        } catch (e) {
            const msg = e instanceof Error ? e.message : "Erreur réseau";
            setRow([item.nzo_id], "error", msg);
            toast.error(`Import impossible : ${item.name}`, { description: msg });
        }
    };

    const importSelected = async () => {
        const batch = selectedItems.filter(isReady);
        if (batch.length === 0) return;
        const ids = batch.map((it) => it.nzo_id);
        setRow(ids, "pending");
        const t = toast.loading(`Lancement de l'import de ${plural(batch.length, "élément")}…`);
        try {
            const res = await bulkImport.mutateAsync({
                items: batch.map((it) => ({ download_path: it.storage_path, media_type: typeOf(it) })),
            });
            if (res.success) {
                setRow(ids, "launched", "Traitement en arrière-plan");
                setSelected(new Set());
                toast.success("Import groupé lancé", {
                    id: t,
                    description: "Radarr / Sonarr traitent les fichiers en arrière-plan ; la liste se mettra à jour toute seule.",
                });
            } else {
                setRow(ids, "error", res.message);
                toast.error("Le lancement de l'import groupé a échoué", { id: t, description: res.message || undefined });
            }
        } catch (e) {
            const msg = e instanceof Error ? e.message : "Erreur réseau";
            setRow(ids, "error", msg);
            toast.error("Le lancement de l'import groupé a échoué", { id: t, description: msg });
        }
    };

    const count = stuck.length;

    return (
        <Panel
            title="Imports bloqués"
            icon={AlertTriangle}
            iconClassName={count > 0 ? "text-amber-400" : "text-emerald-400"}
            action={
                count > 0 ? (
                    <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300 ring-1 ring-inset ring-amber-400/25">
                        {plural(count, "élément")}
                    </span>
                ) : null
            }
            bodyClassName="p-0"
        >
            {isLoading ? (
                <div className="space-y-2 p-4">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Shimmer key={i} className="h-16 w-full" />
                    ))}
                </div>
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} title="Impossible de lister les imports bloqués" />
            ) : count === 0 ? (
                <EmptyState
                    compact
                    tone="success"
                    icon={CheckCircle2}
                    title="Rien à débloquer"
                    description="Tous les téléchargements terminés ont bien été importés par Radarr et Sonarr."
                />
            ) : (
                <>
                    {/* Barre d'outils */}
                    <div className="flex flex-col gap-3 border-b border-white/[0.05] px-4 py-3 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
                        <p className="text-xs text-muted-foreground lg:max-w-md">
                            Choisis <strong className="text-foreground/90">Film</strong> ou{" "}
                            <strong className="text-foreground/90">Série</strong>, coche les lignes puis lance l&apos;import :
                            Radarr / Sonarr s&apos;occupent du déplacement, du renommage, des sous-titres et de Jellyfin.
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                            <Button size="sm" variant="outline" onClick={() => selectAllAs("movie")} disabled={bulkPending}>
                                <Film /> Tout en Film
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => selectAllAs("series")} disabled={bulkPending}>
                                <Tv /> Tout en Série
                            </Button>
                            {selected.size > 0 && (
                                <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} disabled={bulkPending}>
                                    <X /> Tout désélectionner
                                </Button>
                            )}
                            <Button size="sm" onClick={importSelected} disabled={readyCount === 0 || bulkPending}>
                                {bulkPending ? <Loader2 className="animate-spin" /> : <ArrowRight />}
                                {bulkPending ? "Lancement…" : `Importer ${readyCount > 0 ? `(${readyCount})` : "la sélection"}`}
                            </Button>
                        </div>
                    </div>
                    {selected.size > readyCount && (
                        <p className="flex items-center gap-1.5 border-b border-white/[0.05] bg-amber-500/[0.05] px-5 py-2 text-[11px] text-amber-300">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {plural(selected.size - readyCount, "ligne sélectionnée", "lignes sélectionnées")} sans type : choisis
                            Film ou Série pour les inclure.
                        </p>
                    )}

                    <ul className="divide-y divide-white/[0.04]">
                        <AnimatePresence initial={false}>
                            {stuck.map((item, i) => (
                                <StuckRow
                                    key={item.nzo_id}
                                    item={item}
                                    index={i}
                                    type={typeOf(item)}
                                    selected={selected.has(item.nzo_id)}
                                    state={statuses[item.nzo_id]}
                                    disabled={bulkPending}
                                    onToggle={() => toggleSelect(item.nzo_id)}
                                    onType={(t) => setTypeOverrides((prev) => ({ ...prev, [item.nzo_id]: t }))}
                                    onImport={() => importOne(item)}
                                />
                            ))}
                        </AnimatePresence>
                    </ul>
                </>
            )}
        </Panel>
    );
}

function StuckRow({
    item,
    index,
    type,
    selected,
    state,
    disabled,
    onToggle,
    onType,
    onImport,
}: {
    item: StuckDownload;
    index: number;
    type: string;
    selected: boolean;
    state?: { status: RowStatus; message?: string };
    disabled: boolean;
    onToggle: () => void;
    onType: (t: MediaType) => void;
    onImport: () => void;
}) {
    const status = state?.status ?? "idle";
    const ready = type === "movie" || type === "series";

    return (
        <motion.li
            layout
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE_OUT, delay: Math.min(index, 15) * 0.03 } }}
            exit={{ opacity: 0, x: 40, transition: { duration: 0.25 } }}
            className={cn(
                "flex flex-wrap items-center gap-3 px-4 py-3 transition-colors sm:flex-nowrap sm:px-5",
                selected ? "bg-primary/[0.06]" : "hover:bg-white/[0.02]",
                status === "launched" && "bg-emerald-500/[0.05]",
                status === "error" && "bg-red-500/[0.05]",
            )}
        >
            {/* Case à cocher */}
            <button
                type="button"
                role="checkbox"
                aria-checked={selected}
                aria-label={`Sélectionner ${item.name}`}
                onClick={onToggle}
                disabled={disabled}
                className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all",
                    selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-muted-foreground/40 hover:border-primary",
                )}
            >
                {selected && <Check className="h-3 w-3" strokeWidth={3} />}
            </button>

            {/* Type Film / Série */}
            <div className="flex shrink-0 overflow-hidden rounded-lg ring-1 ring-white/[0.08]" role="group" aria-label="Type de média">
                {(
                    [
                        { t: "movie" as const, label: "Film", icon: Film, on: "bg-violet-500/20 text-violet-300" },
                        { t: "series" as const, label: "Série", icon: Tv, on: "bg-sky-500/20 text-sky-300" },
                    ]
                ).map(({ t, label, icon: Icon, on }) => (
                    <button
                        key={t}
                        type="button"
                        aria-pressed={type === t}
                        title={t === "movie" ? "Film (Radarr)" : "Série (Sonarr)"}
                        onClick={() => onType(t)}
                        disabled={disabled}
                        className={cn(
                            "flex items-center gap-1 px-2 py-1.5 text-[11px] font-medium transition-colors",
                            type === t ? on : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground",
                        )}
                    >
                        <Icon className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">{label}</span>
                    </button>
                ))}
            </div>

            {/* Nom + chemin */}
            <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                <p className="truncate text-sm font-medium" title={item.name}>
                    {item.name}
                </p>
                <code className="block truncate font-mono text-[10px] text-muted-foreground" title={item.storage_path}>
                    {item.storage_path}
                </code>
                {status === "error" && state?.message && (
                    <p className="mt-1 line-clamp-2 text-[11px] text-red-300" title={state.message}>
                        {state.message}
                    </p>
                )}
                {!ready && status === "idle" && (
                    <p className="mt-1 text-[11px] text-amber-300/90">Type non détecté : choisis Film ou Série.</p>
                )}
            </div>

            {/* Catégorie + taille */}
            <div className="flex shrink-0 items-center gap-2">
                {item.category && (
                    <span
                        className={cn(
                            "rounded-md px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset",
                            item.category === "software"
                                ? "bg-amber-500/10 text-amber-300 ring-amber-400/25"
                                : "bg-white/[0.04] text-muted-foreground ring-white/[0.08]",
                        )}
                    >
                        {item.category}
                    </span>
                )}
                <span className="w-16 text-right text-xs tabular-nums text-muted-foreground">{frenchSize(item.size_human)}</span>
            </div>

            {/* Action / état */}
            <div className="ml-auto flex w-full shrink-0 justify-end sm:w-36">
                {status === "pending" ? (
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary ring-1 ring-inset ring-primary/25">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" /> En cours…
                    </span>
                ) : status === "launched" ? (
                    <span
                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300 ring-1 ring-inset ring-emerald-400/25"
                        title={state?.message}
                    >
                        <Rocket className="h-3.5 w-3.5" /> Import lancé
                    </span>
                ) : (
                    <Button
                        size="sm"
                        variant={status === "error" ? "outline" : "glow"}
                        disabled={!ready || disabled}
                        onClick={onImport}
                        className="w-full sm:w-auto"
                    >
                        {status === "error" ? <XCircle className="text-red-400" /> : <ArrowRight />}
                        {status === "error" ? "Réessayer" : "Importer"}
                    </Button>
                )}
            </div>
        </motion.li>
    );
}
