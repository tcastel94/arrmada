"use client";

/**
 * Bloc « Saga » de la fiche d'un film : sa place dans la saga (« film 2
 * sur 3 »), le film d'avant et le film d'après, lien vers la saga.
 * Rien n'est affiché si le film n'appartient à aucune saga.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { ChevronRight, Film } from "lucide-react";
import { useMovieSaga, type SagaFilm } from "@/hooks/use-sagas";
import { cn } from "@/lib/utils";

const STATE: Record<string, string> = {
    available: "Sur le NAS",
    wanted: "En recherche",
    missing: "Pas sur le NAS",
    upcoming: "Annoncé",
    excluded: "Exclu dans Radarr",
};

export function SagaBlock({ movieId }: { movieId: number }) {
    const { data } = useMovieSaga(movieId);
    const saga = data?.saga;
    const position = data?.position;
    if (!saga || !position) return null;
    const films = saga.films;
    const around = [films[position - 2], films[position - 1], films[position]];
    const labels = ["Précédent", "Ce film", "Suivant"];

    return (
        <section className="space-y-3 rounded-2xl bg-card p-4" aria-label="Saga">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[15px] font-semibold">
                    {saga.title} · film {position} sur {saga.total}
                </p>
                <Link href={`/media/sagas/${saga.id}`} className="flex items-center gap-0.5 text-[13px] text-primary hover:opacity-80">
                    Voir la saga <ChevronRight className="h-4 w-4" />
                </Link>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
                {around.map((film, i) =>
                    film ? (
                        <Cell key={film.tmdb_id} film={film} label={`${labels[i]}${film.year ? ` · ${film.year}` : ""}`} here={i === 1} />
                    ) : (
                        <div key={i} className="hidden sm:block" />
                    ),
                )}
            </div>
        </section>
    );
}

function Cell({ film, label, here }: { film: SagaFilm; label: string; here: boolean }) {
    const body = (
        <div
            className={cn(
                "grid min-w-0 grid-cols-[48px_1fr] items-center gap-3 rounded-xl p-2",
                here ? "bg-primary/15 ring-2 ring-primary" : "bg-white/[0.03]",
                !here && film.movie_id && "transition-colors hover:bg-white/[0.07]",
            )}
        >
            <div className={cn("aspect-[2/3] overflow-hidden rounded-md bg-white/[0.06]", film.state !== "available" && film.state !== "wanted" && "grayscale brightness-50")}>
                {film.poster ? <img src={film.poster} alt="" loading="lazy" className="h-full w-full object-cover" /> : <Film className="m-auto mt-4 h-5 w-5 text-white/20" />}
            </div>
            <div className="min-w-0">
                <p className="text-[11.5px] text-muted-foreground">{label}</p>
                <p className="truncate text-[13px] font-semibold">{film.title}</p>
                <p className={cn("text-[11.5px]", film.state === "available" ? "text-muted-foreground" : "text-warning")}>{STATE[film.state]}</p>
            </div>
        </div>
    );
    return film.movie_id && !here ? (
        <Link href={`/media/movie/${film.movie_id}`} className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-primary/60">
            {body}
        </Link>
    ) : (
        body
    );
}
