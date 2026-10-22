"use client";

/**
 * Sous-titres d'un film (Bazarr) : état FR, pistes présentes / manquantes,
 * téléchargement automatique, synchronisation, suppression (avec
 * confirmation) et recherche manuelle chez les providers.
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { CircleAlert, CircleCheck, CloudDownload, Loader2, RotateCw, Search } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import type { MediaDetail } from "@/hooks/use-media";
import {
    DEFAULT_SUB_LANG,
    useAutoDownloadMovieSub,
    useDeleteMovieSub,
    useDownloadMovieProviderSub,
    useMovieSubProviders,
    useSyncMovieSub,
    type MovieSubtitleInfo,
    type ProviderSubtitle,
    type SubtitleTrack,
} from "@/hooks/use-subtitles";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { subLangLabel, subTrackKey } from "../labels";
import { MissingSubChip, SubTrackChip } from "./chips";
import { ProviderResults, providerKey } from "./provider-results";

export function MovieSubtitlePanel({ media, block }: { media: MediaDetail; block: MovieSubtitleInfo }) {
    const present = block.subtitles ?? [];
    const missing = block.missing ?? [];
    const hasFr = present.some((s) => s.code2 === DEFAULT_SUB_LANG);

    const auto = useAutoDownloadMovieSub();
    const del = useDeleteMovieSub();
    const sync = useSyncMovieSub();
    const [syncing, setSyncing] = useState<string | null>(null);
    const [toDelete, setToDelete] = useState<SubtitleTrack | null>(null);

    const [manual, setManual] = useState(false);
    const providers = useMovieSubProviders(media.id, manual);
    const dl = useDownloadMovieProviderSub();
    const [dlKey, setDlKey] = useState<string | null>(null);

    const runAuto = () =>
        auto.mutate(
            { radarrId: media.id },
            {
                onSuccess: () =>
                    toast.success("Recherche de sous-titres FR lancée", { description: "Bazarr choisit automatiquement le meilleur." }),
                onError: (e) => toast.error("Recherche impossible", { description: e.message }),
            },
        );

    const runDownload = (s: ProviderSubtitle) => {
        setDlKey(providerKey(s));
        dl.mutate(
            { radarrId: media.id, sub: s },
            {
                onSuccess: () => toast.success("Sous-titre téléchargé", { description: s.release_info }),
                onError: (e) => toast.error("Téléchargement impossible", { description: e.message }),
                onSettled: () => setDlKey(null),
            },
        );
    };

    const runSync = (t: SubtitleTrack) => {
        setSyncing(subTrackKey(t));
        sync.mutate(
            { radarrId: media.id, track: t },
            {
                onSuccess: () =>
                    toast.success("Synchronisation lancée", {
                        description: "Calage sur l'audio de la vidéo : quelques minutes selon la taille du fichier.",
                    }),
                onError: (e) => toast.error("Synchronisation impossible", { description: e.message }),
                onSettled: () => setSyncing(null),
            },
        );
    };

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            {/* État FR + action principale */}
            <motion.div
                variants={fadeUp}
                className={cn(
                    "glass flex flex-col gap-4 rounded-2xl p-4 sm:flex-row sm:items-center",
                    hasFr ? "border-emerald-500/25" : "border-amber-500/25",
                )}
            >
                <div className="flex flex-1 items-center gap-3">
                    <span
                        className={cn(
                            "flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ring-1",
                            hasFr
                                ? "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30"
                                : "bg-amber-500/15 text-amber-300 ring-amber-400/30",
                        )}
                    >
                        {hasFr ? <CircleCheck className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
                    </span>
                    <div>
                        <p className="font-semibold">{hasFr ? "Sous-titres français présents" : "Pas encore de sous-titre français"}</p>
                        <p className="text-xs text-muted-foreground">
                            {hasFr ? "Tu peux en télécharger un meilleur si le timing ne colle pas." : "Bazarr peut en chercher un automatiquement."}
                        </p>
                    </div>
                </div>
                <Button variant={hasFr ? "outline" : "default"} onClick={runAuto} disabled={auto.isPending}>
                    {auto.isPending ? <Loader2 className="animate-spin" /> : <CloudDownload />}
                    {hasFr ? "Re-télécharger (auto)" : "Télécharger en FR (auto)"}
                </Button>
            </motion.div>

            {/* Pistes */}
            <motion.div variants={fadeUp} className="grid gap-5 lg:grid-cols-2">
                <Panel title="Présents" icon={CircleCheck} iconClassName="text-emerald-400">
                    {present.length ? (
                        <div className="flex flex-wrap gap-2">
                            {present.map((t, i) => (
                                <SubTrackChip
                                    // Pas d'id côté Bazarr : chemin/langue + rang (deux pistes intégrées peuvent être identiques).
                                    key={`${subTrackKey(t)}-${i}`}
                                    track={t}
                                    onDelete={() => setToDelete(t)}
                                    deleting={del.isPending && toDelete === t}
                                    onSync={() => runSync(t)}
                                    syncing={syncing === subTrackKey(t)}
                                />
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">Aucun sous-titre téléchargé.</p>
                    )}
                </Panel>
                <Panel title="Manquants (suivis par Bazarr)" icon={CircleAlert} iconClassName="text-amber-400">
                    {missing.length ? (
                        <div className="flex flex-wrap gap-2">
                            {missing.map((t, i) => (
                                <MissingSubChip key={`${subTrackKey(t)}-${i}`} track={t} />
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">Rien ne manque.</p>
                    )}
                </Panel>
            </motion.div>

            {/* Recherche manuelle */}
            <motion.div variants={fadeUp}>
                <Panel
                    title="Recherche manuelle"
                    icon={Search}
                    action={
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={providers.isFetching}
                            onClick={() => (manual ? providers.refetch() : setManual(true))}
                        >
                            {providers.isFetching ? <Loader2 className="animate-spin" /> : manual ? <RotateCw /> : <Search />}
                            {manual ? "Relancer" : "Chercher chez les providers"}
                        </Button>
                    }
                >
                    {manual ? (
                        <ProviderResults
                            items={providers.data?.items}
                            isLoading={providers.isFetching && !providers.data}
                            error={providers.error}
                            onRetry={() => providers.refetch()}
                            onDownload={runDownload}
                            downloadingKey={dlKey}
                        />
                    ) : (
                        <p className="text-sm text-muted-foreground">
                            Choisis toi-même la release de sous-titre la plus proche de ton fichier.
                        </p>
                    )}
                </Panel>
            </motion.div>

            <ConfirmDialog
                open={!!toDelete}
                onOpenChange={(o) => !o && setToDelete(null)}
                destructive
                title="Supprimer ce sous-titre ?"
                description={
                    toDelete
                        ? `Le fichier ${subLangLabel(toDelete)}${toDelete.forced ? " (forcés)" : ""}${toDelete.hi ? " (SDH)" : ""} sera supprimé du disque. Bazarr pourra en re-télécharger un plus tard.`
                        : undefined
                }
                confirmLabel="Supprimer"
                onConfirm={async () => {
                    if (!toDelete) return;
                    try {
                        await del.mutateAsync({ radarrId: media.id, track: toDelete });
                        toast.success("Sous-titre supprimé");
                    } catch (e) {
                        toast.error("Suppression impossible", { description: e instanceof Error ? e.message : String(e) });
                        throw e;
                    }
                }}
            />
        </motion.div>
    );
}
