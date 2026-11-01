"use client";

/**
 * Fiche d'une saga : /media/sagas/2.
 * ----------------------------------------------------------------
 * Fond flou tiré de la saga, ses films dans l'ordre de sortie :
 *  - sur le NAS : lien vers la fiche du film ;
 *  - recherché par Radarr : « En recherche » ;
 *  - manquant (sorti, pas dans Radarr) : grisé, bouton « Ajouter » ;
 *  - annoncé : grisé, « Annoncé » (pas encore de release à chercher).
 * « Compléter la saga » ajoute d'un coup tous les films sortis manquants.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Library, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton } from "@/components/shared/loading-skeleton";
import { PosterCard } from "@/components/shared/poster-card";
import { SAGA_TONE, SagaStack } from "@/components/sagas/saga-stack";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { sagaBadge, useCompleteSaga, useSaga, type SagaDetail, type SagaFilm } from "@/hooks/use-sagas";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8";

export default function SagaPage() {
    const params = useParams<{ id: string }>();
    const id = Number(params.id);
    const { data: saga, isLoading, isError, error, refetch } = useSaga(id);

    return (
        <>
            <Header title={saga?.title ?? "Saga"} />
            <PageContainer>
                <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground hover:text-foreground">
                    <Link href="/media/sagas">
                        <ArrowLeft />
                        Sagas
                    </Link>
                </Button>
                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading || !saga ? (
                    <PosterGridSkeleton count={8} className={GRID} />
                ) : (
                    <>
                        <SagaHero saga={saga} />
                        {saga.films.length === 0 ? (
                            <div className="rounded-2xl bg-card">
                                <EmptyState icon={Library} title="Aucun film" description="Radarr ne connaît pas encore les films de cette saga." />
                            </div>
                        ) : (
                            <div className={GRID}>
                                {saga.films.map((film, i) => (
                                    <FilmCard key={film.tmdb_id} saga={saga} film={film} index={i} />
                                ))}
                            </div>
                        )}
                    </>
                )}
            </PageContainer>
        </>
    );
}

function SagaHero({ saga }: { saga: SagaDetail }) {
    const complete = useCompleteSaga();
    const badge = sagaBadge(saga);
    const years = saga.years.length ? Array.from(new Set(saga.years)).join(" – ") : null;
    const completeAll = () =>
        complete.mutate(
            { id: saga.id },
            {
                onSuccess: (r) =>
                    r.status === "empty"
                        ? toast.info("Rien à ajouter", { description: r.message })
                        : toast.success("Saga complétée", { description: `${r.message} : ${r.added.join(", ")}` }),
                onError: (e) => toast.error("Ajout impossible", { description: e.message }),
            },
        );
    return (
        <section className="relative overflow-hidden rounded-2xl bg-card">
            {(saga.fanart ?? saga.poster) && (
                <img
                    src={(saga.fanart ?? saga.poster)!}
                    alt=""
                    aria-hidden
                    className="absolute inset-0 h-full w-full scale-110 object-cover opacity-25 blur-2xl"
                />
            )}
            <div className="relative flex flex-col gap-5 p-4 sm:flex-row sm:items-end md:p-6">
                <SagaStack posters={saga.posters} title={saga.title} className="w-36 shrink-0 md:w-44" />
                <div className="min-w-0 space-y-2">
                    <h1 className="break-words text-ios-large md:text-[2rem] md:leading-[2.375rem]">{saga.title}</h1>
                    <p className="text-[14px] text-muted-foreground">
                        {[`${saga.total} films`, years, `${saga.available} sur le NAS`].filter(Boolean).join(" · ")}
                    </p>
                    <span className={cn("inline-block rounded-md px-1.5 py-1 text-[11px] font-semibold leading-none", SAGA_TONE[badge.tone])}>
                        {badge.label}
                    </span>
                    {saga.overview && <p className="line-clamp-3 max-w-2xl text-[14px] leading-snug text-foreground/80">{saga.overview}</p>}
                    {saga.missing > 0 && (
                        <div className="pt-1">
                            <Button onClick={completeAll} disabled={complete.isPending}>
                                {complete.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
                                Compléter la saga ({saga.missing} film{saga.missing > 1 ? "s" : ""})
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}

const STATE_LABEL: Record<string, string> = {
    wanted: "En recherche",
    missing: "Pas sur le NAS",
    upcoming: "Annoncé",
    excluded: "Exclu dans Radarr",
};

function FilmCard({ saga, film, index }: { saga: SagaDetail; film: SagaFilm; index: number }) {
    const add = useCompleteSaga();
    const addOne = () =>
        add.mutate(
            { id: saga.id, tmdbIds: [film.tmdb_id] },
            {
                onSuccess: (r) => toast.success("Film ajouté", { description: r.message }),
                onError: (e) => toast.error("Ajout impossible", { description: e.message }),
            },
        );
    const subtitle = `${index + 1} · ${film.year ?? "date inconnue"}`;
    return (
        <PosterCard
            noEntrance
            type="movie"
            title={film.title}
            subtitle={film.state === "available" ? subtitle : `${subtitle} · ${STATE_LABEL[film.state]}`}
            posterUrl={film.poster}
            href={film.movie_id ? `/media/movie/${film.movie_id}` : undefined}
            dimmed={film.state === "missing" || film.state === "upcoming" || film.state === "excluded"}
            badges={
                film.state === "wanted" ? (
                    <Badge variant="secondary">En recherche</Badge>
                ) : film.state === "upcoming" ? (
                    <Badge variant="warning">Annoncé</Badge>
                ) : undefined
            }
            action={
                film.state === "missing" ? (
                    <Button
                        size="icon-sm"
                        onClick={addOne}
                        disabled={add.isPending || add.isSuccess}
                        aria-label={`Ajouter ${film.title}`}
                        title="Ajouter à Radarr"
                    >
                        {add.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
                    </Button>
                ) : undefined
            }
        />
    );
}
