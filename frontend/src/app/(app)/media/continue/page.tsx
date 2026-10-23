"use client";

/**
 * Reprendre : ce qui est commencé sur les TV (appli Kodi 1.19).
 * ----------------------------------------------------------------
 * Source : le vu / reprise que les TV appairées partagent sur le serveur
 * (salon ↔ cinéma). Le plus récent d'abord ; chaque vignette (image du
 * film, barre de progression) dit où on s'est arrêté, sur quelle TV, et
 * propose de relancer la lecture sur une TV (bouton ▶ en haut à droite).
 * Mis à jour en direct : une TV qui s'arrête envoie l'événement
 * `watch_state`, la page se rafraîchit.
 */
import { History, MonitorPlay, Tv } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ContinueCard, continueKey } from "@/components/media/continue-card";
import { useTvDevices, useWatchSummary } from "@/hooks/use-watch";

// Vignettes paysage : 1 colonne sur iPhone, jusqu'à 4 sur grand écran.
const GRID = "grid grid-cols-1 gap-x-4 gap-y-6 min-[480px]:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4";

export default function ContinuePage() {
    const { data, isLoading, isError, error, refetch } = useWatchSummary();
    const tvs = useTvDevices();
    const rows = data?.continue ?? [];

    return (
        <>
            <Header title="Reprendre" />
            <PageContainer>
                <PageHeader
                    title="Reprendre"
                    description="Films et épisodes commencés sur tes TV, là où tu t'es arrêté. Relance la lecture sur la TV de ton choix."
                >
                    <StatPill icon={MonitorPlay} label={rows.length > 1 ? "titres en cours" : "titre en cours"} value={data ? rows.length : "—"} />
                    <StatPill icon={Tv} label={tvs.length > 1 ? "TV appairées" : "TV appairée"} value={tvs.length} />
                </PageHeader>

                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading ? (
                    <div className={GRID}>
                        {Array.from({ length: 6 }, (_, i) => (
                            <div key={i}>
                                <Shimmer className="aspect-video w-full rounded-[12px]" />
                                <Shimmer className="mt-2 h-3 w-2/3 rounded" />
                            </div>
                        ))}
                    </div>
                ) : rows.length === 0 ? (
                    <div className="rounded-2xl bg-card">
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
                    </div>
                ) : (
                    <div className={GRID}>
                        {rows.map((row) => (
                            <ContinueCard key={continueKey(row)} row={row} />
                        ))}
                    </div>
                )}
            </PageContainer>
        </>
    );
}
