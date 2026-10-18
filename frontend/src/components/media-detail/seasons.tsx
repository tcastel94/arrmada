"use client";

/**
 * Onglet « Saisons » d'une série.
 * ----------------------------------------------------------------
 * - Accordéon accessible (bouton avec aria-expanded / aria-controls, chevron
 *   animé) ; plusieurs saisons peuvent être ouvertes en même temps.
 * - Barre de progression par saison : épisodes présents / épisodes DIFFUSÉS.
 * - Épisodes non diffusés (date future ou inconnue) = « À venir » : ni rouges,
 *   ni recherchables (avant : affichés en erreur avec un bouton de recherche).
 * - Spéciaux (saison 0) affichés en dernier, repliés (avant : masqués).
 * - Recherche par épisode / des manquants d'une saison, avec indicateur
 *   « Recherche… » en direct (file de commandes Sonarr).
 * - Code couleur : vert = présent, ambre = manquant, bleu ciel = à venir.
 * - Épisode présent : bouton « Caster » (Chromecast via Jellyfin), si
 *   Jellyfin est configuré. Une seule boîte de choix pour toute la série.
 */
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { CalendarClock, Cast, ChevronRight, ChevronsDown, ChevronsUp, CircleAlert, CircleCheck, EyeOff, Layers, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { StatusDot } from "@/components/fx/status-dot";
import { EmptyState } from "@/components/shared/empty-state";
import { CastDialog } from "@/components/cast-button";
import { useJellyfinConfig } from "@/hooks/use-cast";
import { useUpdateSeasonMonitoring, type EpisodeDetail, type MediaDetail, type SeasonDetail } from "@/hooks/use-media";
import { useSearchEpisodes, useSeriesSearchActivity } from "@/hooks/use-media-actions";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { episodeCode, episodeState, formatDay, pad2, seasonLabel, seasonStats, seriesStats, sortSeasons, type EpisodeState } from "./labels";

export function SeasonsSection({ media }: { media: MediaDetail }) {
    const seriesId = media.id;
    const seasons = useMemo(() => sortSeasons(media.seasons ?? []), [media.seasons]);
    const totals = seriesStats(media.seasons);

    // Par défaut : la dernière « vraie » saison est ouverte (c'est là que ça bouge).
    const [open, setOpen] = useState<Set<number>>(() => {
        const last = [...seasons].reverse().find((s) => s.season_number > 0);
        return new Set(last ? [last.season_number] : []);
    });
    const toggle = (n: number) =>
        setOpen((prev) => {
            const next = new Set(prev);
            if (next.has(n)) next.delete(n);
            else next.add(n);
            return next;
        });
    const allOpen = seasons.length > 0 && seasons.every((s) => open.has(s.season_number));

    // Juste après un lancement de recherche, on interroge Sonarr quelques
    // secondes (le temps qu'il inscrive la commande), puis seulement tant
    // qu'une recherche est active.
    // Compteur plutôt que booléen : chaque nouveau lancement relance les 20 s.
    const [boostTick, setBoostTick] = useState(0);
    useEffect(() => {
        if (boostTick === 0) return;
        const t = setTimeout(() => setBoostTick(0), 20_000);
        return () => clearTimeout(t);
    }, [boostTick]);
    const { data: activity } = useSeriesSearchActivity(seriesId, true, { boost: boostTick > 0 });
    const searchingEpIds = useMemo(() => new Set(activity?.episode_ids ?? []), [activity]);
    const activeSeasons = useMemo(() => new Set(activity?.seasons ?? []), [activity]);

    // Cast d'un épisode : seulement si Jellyfin est configuré (il fait le transcodage)
    const { data: jellyfin } = useJellyfinConfig();
    const canCast = !!jellyfin?.configured && !!media.tvdb_id;
    const [castEp, setCastEp] = useState<EpisodeDetail | null>(null);

    const searchEpisodes = useSearchEpisodes();
    const seasonMonitor = useUpdateSeasonMonitoring();
    // Lancements en cours côté UI (plusieurs possibles en parallèle).
    const [launchingSeasons, setLaunchingSeasons] = useState<Set<number>>(new Set());
    const [launchingEps, setLaunchingEps] = useState<Set<number>>(new Set());

    const launch = (episodeIds: number[], scope: { season?: number; episode?: EpisodeDetail }) => {
        if (episodeIds.length === 0) return;
        const add = <T,>(set: Set<T>, v: T) => new Set(set).add(v);
        const del = <T,>(set: Set<T>, v: T) => {
            const n = new Set(set);
            n.delete(v);
            return n;
        };
        if (scope.season !== undefined) setLaunchingSeasons((s) => add(s, scope.season!));
        if (scope.episode) setLaunchingEps((s) => add(s, scope.episode!.id));
        searchEpisodes.mutate(
            { id: seriesId, episodeIds },
            {
                onSuccess: (d) => {
                    setBoostTick((t) => t + 1);
                    toast.success(
                        scope.episode
                            ? `Recherche lancée pour ${episodeCode(scope.episode.season_number, scope.episode.episode_number)}`
                            : `Recherche lancée pour ${d.count} épisode${d.count > 1 ? "s" : ""} manquant${d.count > 1 ? "s" : ""}`,
                        { description: "Sonarr récupère automatiquement la meilleure release trouvée." },
                    );
                },
                onError: (e) => toast.error("Recherche impossible", { description: e.message }),
                onSettled: () => {
                    if (scope.season !== undefined) setLaunchingSeasons((s) => del(s, scope.season!));
                    if (scope.episode) setLaunchingEps((s) => del(s, scope.episode!.id));
                },
            },
        );
    };

    const toggleMonitor = (season: number, monitored: boolean) =>
        seasonMonitor.mutate(
            { id: seriesId, season, monitored },
            {
                onSuccess: () => toast.success(`${seasonLabel(season)} ${monitored ? "surveillée" : "n'est plus surveillée"}`),
                onError: (e) => toast.error("Modification refusée par Sonarr", { description: e.message }),
            },
        );

    if (seasons.length === 0) {
        return <EmptyState icon={Layers} title="Aucune saison" description="Sonarr ne connaît encore aucun épisode pour cette série." />;
    }

    return (
        <div className="space-y-4">
            {/* Barre d'outils : résumé + tout déplier */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground tabular-nums">{totals.have}</span>/{totals.aired} épisodes diffusés présents
                    {totals.missing > 0 && <span className="text-amber-400"> · {totals.missing} manquant{totals.missing > 1 ? "s" : ""}</span>}
                    {totals.upcoming > 0 && <span className="text-sky-300"> · {totals.upcoming} à venir</span>}
                </p>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOpen(allOpen ? new Set() : new Set(seasons.map((s) => s.season_number)))}
                >
                    {allOpen ? <ChevronsUp /> : <ChevronsDown />}
                    {allOpen ? "Tout replier" : "Tout déplier"}
                </Button>
            </div>

            <motion.div variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-3">
                {seasons.map((season, i) => (
                    <motion.div key={season.season_number} variants={i < 15 ? fadeUp : undefined}>
                        <SeasonCard
                            season={season}
                            isOpen={open.has(season.season_number)}
                            onToggle={() => toggle(season.season_number)}
                            searching={
                                activeSeasons.has(season.season_number) ||
                                !!activity?.series_search ||
                                season.episodes.some((e) => searchingEpIds.has(e.id))
                            }
                            launching={launchingSeasons.has(season.season_number)}
                            searchingEpIds={searchingEpIds}
                            launchingEps={launchingEps}
                            onSearchMissing={(ids) => launch(ids, { season: season.season_number })}
                            onSearchEpisode={(ep) => launch([ep.id], { episode: ep })}
                            onToggleMonitor={(v) => toggleMonitor(season.season_number, v)}
                            monitorPending={seasonMonitor.isPending && seasonMonitor.variables?.season === season.season_number}
                            onCastEpisode={canCast ? setCastEp : undefined}
                        />
                    </motion.div>
                ))}
            </motion.div>

            {canCast && (
                <CastDialog
                    open={castEp !== null}
                    onOpenChange={(open) => !open && setCastEp(null)}
                    episode={
                        castEp
                            ? { tvdbId: media.tvdb_id as number, season: castEp.season_number, episode: castEp.episode_number }
                            : undefined
                    }
                    mediaId={String(media.id)}
                    title={
                        castEp
                            ? `${media.title} · ${episodeCode(castEp.season_number, castEp.episode_number)}${castEp.title ? ` · ${castEp.title}` : ""}`
                            : media.title
                    }
                />
            )}
        </div>
    );
}

interface SeasonCardProps {
    season: SeasonDetail;
    isOpen: boolean;
    onToggle: () => void;
    searching: boolean;
    launching: boolean;
    searchingEpIds: Set<number>;
    launchingEps: Set<number>;
    onSearchMissing: (episodeIds: number[]) => void;
    onSearchEpisode: (ep: EpisodeDetail) => void;
    onToggleMonitor: (monitored: boolean) => void;
    monitorPending: boolean;
    /** Absent : pas de Cast (Jellyfin non configuré ou série sans TVDB). */
    onCastEpisode?: (ep: EpisodeDetail) => void;
}

function SeasonCard({
    season,
    isOpen,
    onToggle,
    searching,
    launching,
    searchingEpIds,
    launchingEps,
    onSearchMissing,
    onSearchEpisode,
    onToggleMonitor,
    monitorPending,
    onCastEpisode,
}: SeasonCardProps) {
    const n = season.season_number;
    const stats = seasonStats(season);
    const complete = stats.aired > 0 && stats.missing === 0;
    const panelId = `season-${n}-episodes`;
    const switchId = `season-${n}-monitor`;
    const missingIds = season.episodes.filter((e) => episodeState(e) === "missing").map((e) => e.id);

    return (
        <SpotlightCard interactive={false} className="overflow-hidden">
            <div className="relative z-[2] flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:p-4">
                {/* En-tête cliquable (tout sauf les actions à droite) */}
                <button
                    type="button"
                    onClick={onToggle}
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    className="group flex min-w-0 flex-1 items-center gap-3 rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70"
                >
                    <motion.span
                        animate={{ rotate: isOpen ? 90 : 0 }}
                        transition={{ duration: 0.25, ease: EASE_OUT }}
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-muted-foreground ring-1 ring-white/[0.06] transition-colors group-hover:text-primary"
                    >
                        <ChevronRight className="h-4 w-4" aria-hidden />
                    </motion.span>
                    <span className="min-w-0 flex-1 space-y-2">
                        <span className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold tracking-tight">{seasonLabel(n)}</span>
                            {searching ? (
                                <Badge variant="default" className="gap-1.5 rounded-full">
                                    <StatusDot tone="primary" size="sm" /> Recherche en cours
                                </Badge>
                            ) : complete ? (
                                <Badge variant="success" className="rounded-full">Complète</Badge>
                            ) : stats.missing > 0 ? (
                                <Badge variant="warning" className="rounded-full">
                                    {stats.missing} manquant{stats.missing > 1 ? "s" : ""}
                                </Badge>
                            ) : stats.aired === 0 ? (
                                <Badge variant="secondary" className="rounded-full text-sky-300">À venir</Badge>
                            ) : null}
                            {!season.monitored && (
                                <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                    <EyeOff className="h-3 w-3" aria-hidden /> non surveillée
                                </span>
                            )}
                        </span>
                        <span className="flex items-center gap-3">
                            <GradientProgress
                                value={stats.pct}
                                tone={complete ? "emerald" : stats.missing > 0 ? "amber" : "slate"}
                                active={searching}
                                className="max-w-xs"
                            />
                            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                                {stats.have}/{stats.aired}
                                {stats.upcoming > 0 && <span className="text-sky-300/80"> +{stats.upcoming} à venir</span>}
                            </span>
                        </span>
                    </span>
                </button>

                {/* Actions de la saison */}
                <div className="flex items-center justify-end gap-3 pl-11 sm:pl-0">
                    {stats.missing > 0 &&
                        (searching ? (
                            <span className="flex items-center gap-1.5 text-xs text-primary">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Sonarr cherche…
                            </span>
                        ) : (
                            <Button size="sm" variant="outline" disabled={launching} onClick={() => onSearchMissing(missingIds)}>
                                {launching ? <Loader2 className="animate-spin" /> : <Search />}
                                Manquants ({stats.missing})
                            </Button>
                        ))}
                    <div className="flex items-center gap-2">
                        <Switch
                            id={switchId}
                            checked={!!season.monitored}
                            disabled={monitorPending}
                            onCheckedChange={onToggleMonitor}
                        />
                        <Label htmlFor={switchId} className="cursor-pointer text-xs text-muted-foreground">
                            Surveillée
                        </Label>
                    </div>
                </div>
            </div>

            <AnimatePresence initial={false}>
                {isOpen && (
                    <motion.div
                        id={panelId}
                        key="episodes"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.35, ease: EASE_OUT }}
                        className="relative z-[2] overflow-hidden"
                    >
                        <ul className="divide-y divide-white/[0.04] border-t border-white/[0.05] px-2 pb-2 sm:px-4">
                            {season.episodes.map((ep) => (
                                <EpisodeRow
                                    key={ep.id}
                                    ep={ep}
                                    searching={searchingEpIds.has(ep.id)}
                                    launching={launchingEps.has(ep.id)}
                                    onSearch={() => onSearchEpisode(ep)}
                                    onCast={onCastEpisode && ep.file ? () => onCastEpisode(ep) : undefined}
                                />
                            ))}
                        </ul>
                    </motion.div>
                )}
            </AnimatePresence>
        </SpotlightCard>
    );
}

const STATE_META: Record<EpisodeState, { icon: typeof CircleCheck; className: string; label: string }> = {
    present: { icon: CircleCheck, className: "text-emerald-400", label: "Présent" },
    missing: { icon: CircleAlert, className: "text-amber-400", label: "Manquant" },
    upcoming: { icon: CalendarClock, className: "text-sky-300", label: "À venir" },
};

function EpisodeRow({
    ep,
    searching,
    launching,
    onSearch,
    onCast,
}: {
    ep: EpisodeDetail;
    searching: boolean;
    launching: boolean;
    onSearch: () => void;
    onCast?: () => void;
}) {
    const state = episodeState(ep);
    const meta = STATE_META[state];
    const Icon = meta.icon;
    const code = episodeCode(ep.season_number, ep.episode_number);
    const date = formatDay(ep.air_date);

    return (
        <li className={cn("flex items-center gap-3 py-2.5 text-sm", state === "upcoming" && "opacity-75")}>
            <span className="w-8 shrink-0 font-mono text-[11px] text-muted-foreground">E{pad2(ep.episode_number)}</span>
            <Icon className={cn("h-4 w-4 shrink-0", meta.className)} aria-hidden />
            <span className="sr-only">{meta.label} :</span>
            <div className="min-w-0 flex-1">
                <p className="truncate">{ep.title || `Épisode ${ep.episode_number}`}</p>
                <p className="text-[11px] text-muted-foreground">
                    {state === "upcoming"
                        ? date
                            ? `Diffusion le ${date}`
                            : "Date de diffusion inconnue"
                        : date || "Date inconnue"}
                    {!ep.monitored && " · non surveillé"}
                </p>
            </div>
            {ep.file && (
                <Badge variant="outline" className="hidden shrink-0 text-[10px] sm:inline-flex">
                    {ep.file.quality}
                </Badge>
            )}
            {onCast && (
                <Button
                    size="icon-sm"
                    variant="ghost"
                    className="shrink-0 text-muted-foreground hover:text-sky-300"
                    aria-label={`Caster l'épisode ${code}`}
                    title="Caster sur un appareil"
                    onClick={onCast}
                >
                    <Cast />
                </Button>
            )}
            {state === "upcoming" && (
                <Badge variant="secondary" className="shrink-0 text-[10px] text-sky-300">
                    À venir
                </Badge>
            )}
            {state === "missing" &&
                (searching ? (
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center" aria-label={`Recherche en cours pour ${code}`} role="status">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    </span>
                ) : (
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className="shrink-0 text-amber-300 hover:text-amber-200"
                        disabled={launching}
                        aria-label={`Rechercher l'épisode ${code}`}
                        onClick={onSearch}
                    >
                        {launching ? <Loader2 className="animate-spin" /> : <Search />}
                    </Button>
                ))}
        </li>
    );
}
