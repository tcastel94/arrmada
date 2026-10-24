"use client";

/**
 * Fiche d'une série maison : /media/local/3 (Naruto Kai, One Pace…).
 * ----------------------------------------------------------------
 * Même esprit que la fiche d'une série Sonarr, en plus simple : pas de
 * Sonarr derrière, donc ni recherche ni téléchargement. On y voit :
 *   - l'affiche, le fond, le résumé (TMDB de la série officielle, ou les
 *     poster.jpg / tvshow.nfo du dossier), la pastille « Kai » ;
 *   - « Sur la TV » : l'épisode commencé, sinon le suivant ;
 *   - les arcs (sous-dossiers) en onglets, et pour chaque épisode son vu /
 *     sa reprise (partagés avec les TV) et son propre « Sur la TV ».
 *
 * La TV lit la vidéo par son jeton (chemin opaque vérifié par le serveur) :
 * la web app ne connaît jamais le chemin réel du fichier.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, FolderOpen } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { HeroBackdrop } from "@/components/media-detail/hero";
import { DetailSkeleton } from "@/components/media-detail/detail-skeleton";
import { PlayOnTvButton } from "@/components/media/play-on-tv";
import {
    localImage,
    nextLocalEpisode,
    useLocalSeriesDetail,
    type LocalEpisode,
    type LocalSeriesDetail,
} from "@/hooks/use-local-series";
import { clockLabel, episodeCode, type PlayTarget } from "@/hooks/use-watch";
import { plural } from "@/lib/format";

/** Ce que la TV doit lancer pour cet épisode (avec la reprise connue). */
function target(series: LocalSeriesDetail, episode: LocalEpisode): PlayTarget & { resumeAt: number } {
    const resumeAt = episode.state && !episode.state.watched ? episode.state.position : 0;
    return {
        media_type: "file",
        id_type: "sha1",
        id: episode.watch_id,
        season: episode.season_number,
        episode: episode.episode_number,
        title: series.title,
        file: episode.token,
        local_series: series.id,
        start: resumeAt,
        resumeAt,
    };
}

function BackLink() {
    return (
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground hover:text-foreground">
            <Link href="/media?type=series">
                <ArrowLeft /> Séries
            </Link>
        </Button>
    );
}

export default function LocalSeriesPage() {
    const params = useParams<{ id: string }>();
    const id = Number.parseInt(params.id ?? "", 10);
    const { data: series, isLoading, isError, error, refetch, isFetching } = useLocalSeriesDetail(Number.isFinite(id) ? id : null);

    const next = useMemo(() => (series ? nextLocalEpisode(series) : null), [series]);
    const [picked, setPicked] = useState<number | null>(null);
    // Onglet ouvert : celui choisi, sinon l'arc de l'épisode à reprendre
    const season = picked ?? next?.season_number ?? series?.seasons[0]?.season_number ?? 0;
    const shown = series?.seasons.find((s) => s.season_number === season) ?? series?.seasons[0];

    return (
        <div className="relative isolate min-h-[calc(100dvh-6rem)]">
            <HeroBackdrop src={localImage(series?.fanart_url ?? series?.poster_url)} />
            <Header title={series?.title ?? (isLoading ? "Chargement…" : "Série maison")} />

            <PageContainer>
                {!Number.isFinite(id) ? (
                    <EmptyState
                        icon={FolderOpen}
                        title="Série inconnue"
                        description="Cette adresse ne désigne aucune série maison."
                        action={{ label: "Retour aux séries", href: "/media?type=series" }}
                    />
                ) : isLoading ? (
                    <DetailSkeleton />
                ) : isError || !series ? (
                    <div className="pt-10">
                        <ErrorState
                            error={error ?? "Cette série est introuvable."}
                            title="Impossible de charger cette série"
                            onRetry={isFetching ? undefined : () => refetch()}
                        />
                        <div className="flex justify-center">
                            <BackLink />
                        </div>
                    </div>
                ) : (
                    <>
                        {/* En-tête : affiche, titre, pastille, résumé, « Sur la TV » */}
                        <section className="mt-2 flex flex-col gap-6 sm:flex-row">
                            {localImage(series.poster_url) && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={localImage(series.poster_url) ?? ""}
                                    alt=""
                                    className="aspect-[2/3] w-36 shrink-0 self-start rounded-xl object-cover shadow-2xl shadow-black/60 sm:w-48"
                                />
                            )}
                            <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h1 className="text-2xl font-semibold sm:text-3xl">{series.title}</h1>
                                    {series.badge && (
                                        <span className="rounded-[5px] bg-primary px-1.5 py-0.5 text-[11px] font-semibold uppercase text-white">
                                            {series.badge}
                                        </span>
                                    )}
                                </div>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    {[series.year, plural(series.seasons.length, "arc", "arcs"), plural(series.episodes, "épisode", "épisodes")]
                                        .filter(Boolean)
                                        .join(" · ")}
                                </p>
                                {series.overview && <p className="mt-4 max-w-3xl text-sm leading-relaxed text-foreground/85">{series.overview}</p>}
                                {next && (
                                    <div className="mt-5 flex flex-wrap items-center gap-3">
                                        <PlayOnTvButton
                                            target={target(series, next)}
                                            resumeAt={target(series, next).resumeAt}
                                            label={`${episodeCode(next.season_number, next.episode_number)} sur la TV`}
                                            variant="default"
                                        />
                                        <span className="text-sm text-muted-foreground">
                                            {next.state && !next.state.watched && next.state.position > 0
                                                ? `Reprise à ${clockLabel(next.state.position)}`
                                                : next.title}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </section>

                        {/* Arcs (sous-dossiers) en onglets */}
                        {series.seasons.length > 1 && (
                            <div className="scrollbar-none -mx-4 mt-8 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
                                {series.seasons.map((s) => (
                                    <button
                                        key={s.season_number}
                                        type="button"
                                        onClick={() => setPicked(s.season_number)}
                                        data-active={s.season_number === shown?.season_number}
                                        className="chip shrink-0"
                                    >
                                        {s.name || `Saison ${s.season_number}`}
                                    </button>
                                ))}
                            </div>
                        )}

                        <ul className="mt-4 overflow-hidden rounded-xl bg-card [&>*+*]:shadow-[inset_0_0.5px_0_hsl(0_0%_100%/0.1)]">
                            {(shown?.episodes ?? []).map((ep) => (
                                <EpisodeRow key={ep.token} series={series} episode={ep} />
                            ))}
                        </ul>
                    </>
                )}
            </PageContainer>
        </div>
    );
}

function EpisodeRow({ series, episode }: { series: LocalSeriesDetail; episode: LocalEpisode }) {
    const state = episode.state;
    const progress = state && !state.watched && state.total > 0 ? Math.min(100, (state.position / state.total) * 100) : 0;
    const thumb = localImage(episode.image);
    const play = target(series, episode);
    return (
        <li className="flex items-center gap-3 p-2.5 sm:gap-4">
            <div className="relative aspect-video w-28 shrink-0 overflow-hidden rounded-md bg-muted sm:w-40">
                {thumb && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumb} alt="" loading="lazy" className="h-full w-full object-cover" />
                )}
                {progress > 0 && (
                    <div className="absolute inset-x-0 bottom-0 h-1 bg-black/60">
                        <div className="h-full bg-white" style={{ width: `${progress}%` }} />
                    </div>
                )}
            </div>
            <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm">
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">
                        {episodeCode(episode.season_number, episode.episode_number)}
                    </span>
                    <span className="truncate font-medium">{episode.title}</span>
                    {state?.watched && (
                        <span className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
                            <Check className="h-3.5 w-3.5" /> vu
                        </span>
                    )}
                </p>
                {episode.overview && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{episode.overview}</p>}
                {progress > 0 && state && (
                    <p className="mt-0.5 text-xs text-primary">
                        Arrêté à {clockLabel(state.position)}
                        {state.total > 0 ? ` sur ${clockLabel(state.total)}` : ""}
                    </p>
                )}
            </div>
            <PlayOnTvButton target={play} resumeAt={play.resumeAt} label="" size="icon" variant="ghost" />
        </li>
    );
}
