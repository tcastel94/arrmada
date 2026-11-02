"use client";

/**
 * Ordre des films d'une saga, choisi à la main (ordre de l'histoire).
 * ----------------------------------------------------------------
 * TMDB ne donne que l'ordre de sortie. Ici, on monte ou descend chaque
 * film avec les flèches, puis « Enregistrer » ; « Ordre de sortie » efface
 * l'ordre choisi. L'ordre vaut pour tous les profils et sert partout : web
 * app, TV, « Reprendre la saga », film suivant.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { ArrowDown, ArrowUp, Film, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useSagaOrder, type SagaDetail, type SagaFilm } from "@/hooks/use-sagas";

export function SagaOrderEditor({ saga, onDone }: { saga: SagaDetail; onDone: () => void }) {
    const [films, setFilms] = useState<SagaFilm[]>(saga.films);
    const save = useSagaOrder();

    const move = (index: number, delta: number) => {
        const target = index + delta;
        if (target < 0 || target >= films.length) return;
        const next = [...films];
        [next[index], next[target]] = [next[target], next[index]];
        setFilms(next);
    };
    const run = (tmdbIds: number[] | null) =>
        save.mutate(
            { id: saga.id, tmdbIds },
            {
                onSuccess: (r) => {
                    toast.success(r.message);
                    onDone();
                },
                onError: (e) => toast.error("Ordre non enregistré", { description: e.message }),
            },
        );

    return (
        <section className="space-y-3 rounded-2xl bg-card p-4" aria-label="Ordre des films">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <p className="text-[15px] font-semibold">Ordre des films</p>
                    <p className="text-[13px] text-muted-foreground">Monte ou descends les films, par exemple dans l&apos;ordre de l&apos;histoire.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" onClick={onDone} disabled={save.isPending}>
                        Annuler
                    </Button>
                    {saga.custom_order && (
                        <Button size="sm" variant="secondary" onClick={() => run(null)} disabled={save.isPending}>
                            Ordre de sortie
                        </Button>
                    )}
                    <Button size="sm" onClick={() => run(films.map((f) => f.tmdb_id))} disabled={save.isPending}>
                        {save.isPending && <Loader2 className="animate-spin" />}
                        Enregistrer
                    </Button>
                </div>
            </div>
            <ol className="divide-y divide-white/[0.06] overflow-hidden rounded-xl bg-white/[0.03]">
                {films.map((film, i) => (
                    <li key={film.tmdb_id} className="flex items-center gap-3 px-3 py-2">
                        <span className="w-5 text-right text-[13px] tabular-nums text-muted-foreground">{i + 1}</span>
                        <div className="aspect-[2/3] w-8 shrink-0 overflow-hidden rounded bg-white/[0.06]">
                            {film.poster ? <img src={film.poster} alt="" className="h-full w-full object-cover" /> : <Film className="m-auto mt-2 h-4 w-4 text-white/20" />}
                        </div>
                        <p className="min-w-0 flex-1 truncate text-[14px]">
                            {film.title} <span className="text-muted-foreground">{film.year ?? ""}</span>
                        </p>
                        <Button size="icon-sm" variant="ghost" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Monter ${film.title}`}>
                            <ArrowUp />
                        </Button>
                        <Button size="icon-sm" variant="ghost" onClick={() => move(i, 1)} disabled={i === films.length - 1} aria-label={`Descendre ${film.title}`}>
                            <ArrowDown />
                        </Button>
                    </li>
                ))}
            </ol>
        </section>
    );
}
