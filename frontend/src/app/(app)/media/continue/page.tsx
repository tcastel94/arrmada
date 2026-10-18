"use client";

/**
 * Reprendre : ce qui est commencé sur les TV (appli Kodi 1.19).
 * ----------------------------------------------------------------
 * Source : le vu / reprise que les TV appairées partagent sur le serveur
 * (salon ↔ cinéma). Le plus récent d'abord ; chaque affiche dit où on s'est
 * arrêté, sur quelle TV, et propose de relancer la lecture sur une TV
 * (bouton en bas à droite de l'affiche). Mis à jour en direct : une TV qui
 * s'arrête envoie l'événement `watch_state`, la page se rafraîchit.
 */
import { motion } from "framer-motion";
import { History, MonitorPlay, Tv } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { PlayOnTvButton } from "@/components/media/play-on-tv";
import { clockLabel, episodeCode, useTvDevices, useWatchSummary, type ContinueRow } from "@/hooks/use-watch";
import { stagger } from "@/lib/motion";

const GRID = "grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";

/** « reste 1 h 12 » / « reste 8 min » (vide sans durée connue). */
function leftLabel(row: ContinueRow): string {
    if (!row.total || row.total <= row.position) return "";
    const minutes = Math.round((row.total - row.position) / 60);
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `reste ${h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`}`;
}

/** « il y a 5 min », « hier », « le 3 oct. » */
function agoLabel(iso: string, now = Date.now()): string {
    const at = Date.parse(iso);
    if (!Number.isFinite(at)) return "";
    const minutes = Math.round((now - at) / 60_000);
    if (minutes < 1) return "à l'instant";
    if (minutes < 60) return `il y a ${minutes} min`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `il y a ${hours} h`;
    if (hours < 48) return "hier";
    return `le ${new Date(at).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}`;
}

export default function ContinuePage() {
    const { data, isLoading, isError, error, refetch } = useWatchSummary();
    const tvs = useTvDevices();
    const rows = data?.continue ?? [];

    return (
        <>
            <Header title="Reprendre" />
            <PageContainer>
                <PageHeader
                    icon={History}
                    accent="violet"
                    eyebrow="Bibliothèque"
                    title="Reprendre"
                    description="Films et épisodes commencés sur tes TV, là où tu t'es arrêté. Relance la lecture sur la TV de ton choix."
                >
                    <StatPill icon={MonitorPlay} label={rows.length > 1 ? "titres en cours" : "titre en cours"} value={data ? rows.length : "—"} />
                    <StatPill icon={Tv} label={tvs.length > 1 ? "TV appairées" : "TV appairée"} value={tvs.length} />
                </PageHeader>

                {isError ? (
                    <ErrorState error={error} onRetry={() => refetch()} />
                ) : isLoading ? (
                    <div className={GRID}>
                        {Array.from({ length: 8 }, (_, i) => (
                            <div key={i} className="aspect-[2/3] animate-pulse rounded-2xl bg-white/5" />
                        ))}
                    </div>
                ) : rows.length === 0 ? (
                    <EmptyState
                        icon={History}
                        title="Rien en cours"
                        description={
                            tvs.length
                                ? "Arrête un film ou un épisode en route sur une TV : il apparaîtra ici quelques secondes plus tard."
                                : "Appaire une TV (appli ArrMada dans Kodi) : ce qu'elle commence s'affichera ici."
                        }
                        action={tvs.length ? undefined : { label: "Appairer une TV", href: "/settings/kodi" }}
                    />
                ) : (
                    <motion.div variants={stagger(0, 0.03)} initial="hidden" animate="show" className={GRID}>
                        {rows.map((row) => {
                            const isMovie = row.media_type === "movie";
                            const code = isMovie ? "" : episodeCode(row.season, row.episode);
                            return (
                                <PosterCard
                                    key={`${row.media_type}:${row.id}:${row.season ?? ""}:${row.episode ?? ""}`}
                                    title={row.title}
                                    // Court : le bouton TV occupe le bas à droite de l'affiche
                                    subtitle={isMovie ? (row.year ?? "Film") : code}
                                    posterUrl={row.poster_url}
                                    type={isMovie ? "movie" : "series"}
                                    href={row.media_kind && row.media_id ? `/media/${row.media_kind}/${row.media_id}` : undefined}
                                    progress={row.progress ?? undefined}
                                    badges={
                                        <PosterBadge tone="violet" title={`Arrêté à ${clockLabel(row.position)}`}>
                                            ⏵ {clockLabel(row.position)}
                                        </PosterBadge>
                                    }
                                    meta={[leftLabel(row), row.device, agoLabel(row.updated_at)].filter(Boolean).join(" · ")}
                                    action={
                                        <PlayOnTvButton
                                            target={{
                                                media_type: row.media_type,
                                                id: row.id,
                                                season: row.season,
                                                episode: row.episode,
                                                title: row.title,
                                            }}
                                            resumeAt={row.position}
                                            label=""
                                            size="icon-sm"
                                            variant="secondary"
                                            className="shadow-lg"
                                        />
                                    }
                                />
                            );
                        })}
                    </motion.div>
                )}
            </PageContainer>
        </>
    );
}
