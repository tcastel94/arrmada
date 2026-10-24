"use client";

/**
 * Sous-titres d'une série (Bazarr), épisode par épisode.
 * ----------------------------------------------------------------
 * - Résumé : couverture FR (barre de progression) + « tout télécharger ».
 * - Filtre « seulement les épisodes sans ST FR ».
 * - Puces des pistes visibles AUSSI sur mobile (avant : `hidden sm:flex`),
 *   passées à la ligne sous le titre.
 * - Suppression avec confirmation, recherche manuelle dépliable par épisode.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { CircleAlert, CircleCheck, CloudDownload, Loader2, Search } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { MediaDetail } from "@/hooks/use-media";
import {
    DEFAULT_SUB_LANG,
    useAutoDownloadEpisodeSub,
    useAutoDownloadSeriesSubs,
    useDeleteEpisodeSub,
    useDownloadEpisodeProviderSub,
    useEpisodeSubProviders,
    useSyncEpisodeSub,
    type EpisodeSubtitleInfo,
    type ProviderSubtitle,
    type SubtitleTrack,
} from "@/hooks/use-subtitles";
import { percent } from "@/lib/format";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { episodeCode, pad2, seasonLabel, subLangLabel, subTrackKey } from "../labels";
import { MissingSubChip, SubTrackChip } from "./chips";
import { ProviderResults, providerKey } from "./provider-results";

const hasFr = (e: EpisodeSubtitleInfo) => e.subtitles.some((s) => s.code2 === DEFAULT_SUB_LANG);

export function SeriesSubtitlePanel({ media, episodes }: { media: MediaDetail; episodes: EpisodeSubtitleInfo[] }) {
    const seriesAuto = useAutoDownloadSeriesSubs();
    const epAuto = useAutoDownloadEpisodeSub();
    const [autoEp, setAutoEp] = useState<number | null>(null);
    const del = useDeleteEpisodeSub();
    const [toDelete, setToDelete] = useState<{ ep: EpisodeSubtitleInfo; track: SubtitleTrack } | null>(null);
    const epSync = useSyncEpisodeSub();
    const [syncing, setSyncing] = useState<string | null>(null);
    const [openEp, setOpenEp] = useState<number | null>(null);
    const providers = useEpisodeSubProviders(openEp, openEp !== null);
    const dl = useDownloadEpisodeProviderSub();
    const [dlKey, setDlKey] = useState<string | null>(null);
    const [onlyMissing, setOnlyMissing] = useState(false);

    const withFr = episodes.filter(hasFr).length;
    const frMissing = episodes.length - withFr;

    // Regroupement par saison (spéciaux en dernier).
    const bySeason = useMemo(() => {
        const map = new Map<number, EpisodeSubtitleInfo[]>();
        for (const e of episodes) {
            if (onlyMissing && hasFr(e)) continue;
            const list = map.get(e.season) ?? [];
            list.push(e);
            map.set(e.season, list);
        }
        return Array.from(map.entries())
            .sort(([a], [b]) => (a === 0 ? 1 : b === 0 ? -1 : a - b))
            .map(([season, list]) => [season, [...list].sort((a, b) => a.episode - b.episode)] as const);
    }, [episodes, onlyMissing]);

    const runSeriesAuto = () =>
        seriesAuto.mutate(
            { seriesId: media.id },
            {
                onSuccess: (d) =>
                    toast.success(`Recherche lancée pour ${d.triggered} épisode${d.triggered > 1 ? "s" : ""}`, {
                        description: "Bazarr télécharge les meilleurs sous-titres FR trouvés.",
                    }),
                onError: (e) => toast.error("Recherche impossible", { description: e.message }),
            },
        );

    const runEpAuto = (e: EpisodeSubtitleInfo) => {
        setAutoEp(e.episode_id);
        epAuto.mutate(
            { seriesId: media.id, episodeId: e.episode_id },
            {
                onSuccess: () => toast.success(`Recherche de sous-titres FR lancée (${episodeCode(e.season, e.episode)})`),
                onError: (err) => toast.error("Recherche impossible", { description: err.message }),
                onSettled: () => setAutoEp(null),
            },
        );
    };

    const runDownload = (s: ProviderSubtitle) => {
        if (openEp === null) return;
        setDlKey(providerKey(s));
        dl.mutate(
            { seriesId: media.id, episodeId: openEp, sub: s },
            {
                onSuccess: () => toast.success("Sous-titre téléchargé", { description: s.release_info }),
                onError: (err) => toast.error("Téléchargement impossible", { description: err.message }),
                onSettled: () => setDlKey(null),
            },
        );
    };

    const runSync = (e: EpisodeSubtitleInfo, t: SubtitleTrack) => {
        const key = `${e.episode_id}:${subTrackKey(t)}`;
        setSyncing(key);
        epSync.mutate(
            { seriesId: media.id, episodeId: e.episode_id, track: t },
            {
                onSuccess: () =>
                    toast.success(`Synchronisation lancée (${episodeCode(e.season, e.episode)})`, {
                        description: "Calage sur l'audio de la vidéo : quelques minutes.",
                    }),
                onError: (err) => toast.error("Synchronisation impossible", { description: err.message }),
                onSettled: () => setSyncing(null),
            },
        );
    };

    return (
        <div className="space-y-5">
            {/* Résumé + actions globales */}
            <div className="glass flex flex-col gap-4 rounded-2xl p-4 md:flex-row md:items-center">
                <div className="flex-1 space-y-2">
                    <p className="flex items-center gap-2 font-semibold">
                        {frMissing > 0 ? (
                            <>
                                <CircleAlert className="h-5 w-5 text-warning" aria-hidden />
                                {frMissing} épisode{frMissing > 1 ? "s" : ""} sans sous-titre FR
                            </>
                        ) : (
                            <>
                                <CircleCheck className="h-5 w-5 text-success" aria-hidden />
                                Tous les épisodes ont un sous-titre FR
                            </>
                        )}
                    </p>
                    <div className="flex items-center gap-3">
                        <GradientProgress value={percent(withFr, episodes.length)} tone={frMissing > 0 ? "amber" : "emerald"} className="max-w-sm" />
                        <span className="text-xs tabular-nums text-muted-foreground">
                            {withFr}/{episodes.length}
                        </span>
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                        <Switch id="subs-only-missing" checked={onlyMissing} onCheckedChange={setOnlyMissing} />
                        <Label htmlFor="subs-only-missing" className="cursor-pointer text-xs text-muted-foreground">
                            Seulement sans ST FR
                        </Label>
                    </div>
                    {frMissing > 0 && (
                        <Button onClick={runSeriesAuto} disabled={seriesAuto.isPending}>
                            {seriesAuto.isPending ? <Loader2 className="animate-spin" /> : <CloudDownload />}
                            Tout télécharger en FR
                        </Button>
                    )}
                </div>
            </div>

            {bySeason.length === 0 ? (
                <EmptyState compact icon={CircleCheck} tone="success" title="Rien à afficher" description="Aucun épisode ne manque de sous-titre FR." />
            ) : (
                <motion.div variants={stagger(0, 0.06)} initial="hidden" animate="show" className="space-y-4">
                    {bySeason.map(([season, list], i) => {
                        const ok = list.filter(hasFr).length;
                        return (
                            <motion.div key={season} variants={i < 10 ? fadeUp : undefined}>
                                <Panel
                                    title={seasonLabel(season)}
                                    action={
                                        <span className={cn("text-xs tabular-nums", ok === list.length ? "text-success" : "text-warning")}>
                                            {ok}/{list.length} avec ST FR
                                        </span>
                                    }
                                    bodyClassName="p-2 sm:p-3"
                                >
                                    <ul className="space-y-1">
                                        {list.map((e) => {
                                            const fr = hasFr(e);
                                            const isOpen = openEp === e.episode_id;
                                            const resultsId = `subs-results-${e.episode_id}`;
                                            return (
                                                <li key={e.episode_id} className={cn("rounded-xl transition-colors", isOpen && "bg-white/[0.03]")}>
                                                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 p-2">
                                                        {fr ? (
                                                            <CircleCheck className="h-4 w-4 shrink-0 text-success" aria-label="Sous-titre FR présent" />
                                                        ) : (
                                                            <CircleAlert className="h-4 w-4 shrink-0 text-warning" aria-label="Sous-titre FR manquant" />
                                                        )}
                                                        <span className="w-8 shrink-0 font-mono text-[11px] text-muted-foreground">E{pad2(e.episode)}</span>
                                                        <span className="min-w-0 flex-1 truncate text-sm" title={e.title}>
                                                            {e.title || `Épisode ${e.episode}`}
                                                        </span>
                                                        <div className="flex shrink-0 items-center gap-1">
                                                            <Button
                                                                size="icon-sm"
                                                                variant="ghost"
                                                                aria-label={`Télécharger automatiquement un sous-titre FR pour ${episodeCode(e.season, e.episode)}`}
                                                                title="Télécharger auto un ST FR"
                                                                disabled={autoEp === e.episode_id}
                                                                onClick={() => runEpAuto(e)}
                                                            >
                                                                {autoEp === e.episode_id ? <Loader2 className="animate-spin" /> : <CloudDownload />}
                                                            </Button>
                                                            <Button
                                                                size="icon-sm"
                                                                variant={isOpen ? "glow" : "ghost"}
                                                                aria-label={`Recherche manuelle de sous-titres pour ${episodeCode(e.season, e.episode)}`}
                                                                aria-expanded={isOpen}
                                                                aria-controls={resultsId}
                                                                title="Recherche manuelle"
                                                                onClick={() => setOpenEp(isOpen ? null : e.episode_id)}
                                                            >
                                                                <Search />
                                                            </Button>
                                                        </div>
                                                        {/* Pistes : ligne complète sous le titre (visible sur mobile) */}
                                                        {(e.subtitles.length > 0 || e.missing.length > 0) && (
                                                            <div className="flex basis-full flex-wrap gap-1 pl-6 sm:pl-16">
                                                                {e.subtitles.map((t, i) => (
                                                                    <SubTrackChip
                                                                        key={`${subTrackKey(t)}-${i}`}
                                                                        track={t}
                                                                        onDelete={() => setToDelete({ ep: e, track: t })}
                                                                        deleting={del.isPending && toDelete?.track === t}
                                                                        onSync={() => runSync(e, t)}
                                                                        syncing={syncing === `${e.episode_id}:${subTrackKey(t)}`}
                                                                    />
                                                                ))}
                                                                {e.missing.map((t, i) => (
                                                                    <MissingSubChip key={`m-${subTrackKey(t)}-${i}`} track={t} />
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                    <AnimatePresence initial={false}>
                                                        {isOpen && (
                                                            <motion.div
                                                                id={resultsId}
                                                                initial={{ height: 0, opacity: 0 }}
                                                                animate={{ height: "auto", opacity: 1 }}
                                                                exit={{ height: 0, opacity: 0 }}
                                                                transition={{ duration: 0.3, ease: EASE_OUT }}
                                                                className="overflow-hidden"
                                                            >
                                                                <div className="p-2 pt-0">
                                                                    <ProviderResults
                                                                        items={providers.data?.items}
                                                                        isLoading={providers.isFetching && !providers.data}
                                                                        error={providers.error}
                                                                        onRetry={() => providers.refetch()}
                                                                        onDownload={runDownload}
                                                                        downloadingKey={dlKey}
                                                                    />
                                                                </div>
                                                            </motion.div>
                                                        )}
                                                    </AnimatePresence>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                </Panel>
                            </motion.div>
                        );
                    })}
                </motion.div>
            )}

            <ConfirmDialog
                open={!!toDelete}
                onOpenChange={(o) => !o && setToDelete(null)}
                destructive
                title="Supprimer ce sous-titre ?"
                description={
                    toDelete
                        ? `Le sous-titre ${subLangLabel(toDelete.track)} de ${episodeCode(toDelete.ep.season, toDelete.ep.episode)} sera supprimé du disque.`
                        : undefined
                }
                confirmLabel="Supprimer"
                onConfirm={async () => {
                    if (!toDelete) return;
                    try {
                        await del.mutateAsync({ seriesId: media.id, episodeId: toDelete.ep.episode_id, track: toDelete.track });
                        toast.success("Sous-titre supprimé");
                    } catch (err) {
                        toast.error("Suppression impossible", { description: err instanceof Error ? err.message : String(err) });
                        throw err;
                    }
                }}
            />
        </div>
    );
}
