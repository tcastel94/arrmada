"use client";

/**
 * Filmographie d'un acteur (clic sur un visage du casting).
 * ----------------------------------------------------------------
 * Deux sections : les films déjà dans ta médiathèque (lien vers leur fiche)
 * et les films « à découvrir », ajoutables à Radarr d'un clic (la recherche
 * est lancée automatiquement). Les affiches réutilisent PosterCard.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Cake, Check, Film, Library, Loader2, MapPin, Plus, Sparkles, Star } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { usePersonFilmography, type PersonMovie } from "@/hooks/use-media";
import { useCreateRequest } from "@/hooks/use-requests";
import { stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { departmentLabel, formatDay, initials } from "./labels";

const GRID = "grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5";

export function PersonDialog({
    person,
    onClose,
}: {
    person: { id: number; name: string; photo?: string | null } | null;
    onClose: () => void;
}) {
    const { data, isLoading, isError, error, refetch } = usePersonFilmography(person?.id ?? null, !!person);
    const createReq = useCreateRequest();
    const [added, setAdded] = useState<Set<number>>(new Set());
    const [adding, setAdding] = useState<Set<number>>(new Set());
    const [bioOpen, setBioOpen] = useState(false);

    const info = data?.person;
    const photo = info?.photo ?? person?.photo ?? null;

    const addMovie = (m: PersonMovie) => {
        setAdding((s) => new Set(s).add(m.tmdb_id));
        createReq.mutate(
            {
                title: m.title,
                type: "movie",
                tmdb_id: m.tmdb_id,
                year: m.year ?? undefined,
                poster_url: m.poster ?? undefined,
            },
            {
                onSuccess: () => {
                    setAdded((prev) => new Set(prev).add(m.tmdb_id));
                    toast.success(`« ${m.title} » ajouté à Radarr`, { description: "La recherche est lancée automatiquement." });
                },
                onError: (e) => toast.error("Ajout impossible", { description: e.message }),
                onSettled: () =>
                    setAdding((s) => {
                        const n = new Set(s);
                        n.delete(m.tmdb_id);
                        return n;
                    }),
            },
        );
    };

    return (
        <Dialog
            open={!!person}
            onOpenChange={(o) => {
                if (!o) {
                    onClose();
                    setBioOpen(false);
                }
            }}
        >
            <DialogContent className="max-h-[88dvh] sm:max-w-4xl">
                <DialogHeader>
                    <div className="flex items-center gap-4 text-left">
                        <span className="relative shrink-0">
                            <span aria-hidden className="absolute -inset-1 rounded-full bg-gradient-to-br from-primary to-brand opacity-60 blur-md" />
                            <span className="relative flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-muted text-lg font-semibold ring-2 ring-white/15">
                                {photo ? (
                                    <img src={photo} alt="" className="h-full w-full object-cover" />
                                ) : (
                                    initials(person?.name ?? "?")
                                )}
                            </span>
                        </span>
                        <div className="min-w-0 space-y-1">
                            <DialogTitle className="text-xl">{person?.name ?? "Acteur"}</DialogTitle>
                            <DialogDescription asChild>
                                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                    {info?.known_for && <span>{departmentLabel(info.known_for)}</span>}
                                    {info?.birthday && (
                                        <span className="flex items-center gap-1">
                                            <Cake className="h-3 w-3" aria-hidden /> {formatDay(info.birthday, { withYear: true })}
                                        </span>
                                    )}
                                    {info?.place_of_birth && (
                                        <span className="flex items-center gap-1">
                                            <MapPin className="h-3 w-3" aria-hidden /> {info.place_of_birth}
                                        </span>
                                    )}
                                    {data?.counts && (
                                        <span>
                                            {data.counts.in_library} dans ta médiathèque · {data.counts.discover} à découvrir
                                        </span>
                                    )}
                                </div>
                            </DialogDescription>
                        </div>
                    </div>
                </DialogHeader>

                {info?.biography && (
                    <div>
                        <p className={cn("text-sm leading-relaxed text-muted-foreground", !bioOpen && "line-clamp-3")}>{info.biography}</p>
                        {info.biography.length > 240 && (
                            <button
                                type="button"
                                onClick={() => setBioOpen((v) => !v)}
                                aria-expanded={bioOpen}
                                className="mt-1 text-xs font-medium text-primary hover:underline"
                            >
                                {bioOpen ? "Réduire" : "Lire la biographie"}
                            </button>
                        )}
                    </div>
                )}

                {isLoading ? (
                    <div className="space-y-3">
                        <Shimmer className="h-4 w-40 rounded-md" />
                        <div className={GRID}>
                            {Array.from({ length: 5 }).map((_, i) => (
                                <Shimmer key={i} className="aspect-[2/3] w-full rounded-2xl" />
                            ))}
                        </div>
                    </div>
                ) : isError ? (
                    <ErrorState compact error={error} onRetry={() => refetch()} title="Filmographie indisponible" />
                ) : data?.error ? (
                    <ErrorState compact error={data.error} onRetry={() => refetch()} title="Filmographie indisponible" />
                ) : data && data.in_library.length === 0 && data.discover.length === 0 ? (
                    <EmptyState compact icon={Film} title="Aucun film trouvé" description="TMDb ne liste aucun film pour cette personne." />
                ) : data ? (
                    <div className="space-y-6">
                        {data.in_library.length > 0 && (
                            <section className="space-y-3">
                                <h3 className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
                                    <Library className="h-4 w-4" aria-hidden /> Dans ta médiathèque
                                </h3>
                                <motion.div variants={stagger(0, 0.03)} initial="hidden" animate="show" className={GRID}>
                                    {data.in_library.map((m) => (
                                        <PosterCard
                                            key={m.tmdb_id}
                                            title={m.title}
                                            subtitle={m.year ?? undefined}
                                            posterUrl={m.poster}
                                            type="movie"
                                            href={m.radarr_id ? `/media/movie/${m.radarr_id}` : undefined}
                                            onClick={onClose}
                                            meta={m.character ? <span className="text-[11px] text-white/70">Rôle : {m.character}</span> : undefined}
                                            badges={
                                                m.has_file ? (
                                                    <PosterBadge tone="success">Présent</PosterBadge>
                                                ) : (
                                                    <PosterBadge tone="warning">Manquant</PosterBadge>
                                                )
                                            }
                                            corner={
                                                m.vote_average ? (
                                                    <PosterBadge>
                                                        <Star className="h-2.5 w-2.5 fill-amber-400 text-amber-400" aria-hidden />
                                                        {m.vote_average.toFixed(1)}
                                                    </PosterBadge>
                                                ) : undefined
                                            }
                                        />
                                    ))}
                                </motion.div>
                            </section>
                        )}

                        {data.discover.length > 0 && (
                            <section className="space-y-3">
                                <h3 className="flex items-center gap-2 text-sm font-semibold">
                                    <Sparkles className="h-4 w-4 text-primary" aria-hidden /> À découvrir
                                </h3>
                                <motion.div variants={stagger(0, 0.03)} initial="hidden" animate="show" className={GRID}>
                                    {data.discover.map((m) => {
                                        const isAdded = added.has(m.tmdb_id);
                                        const isAdding = adding.has(m.tmdb_id);
                                        return (
                                            <PosterCard
                                                key={m.tmdb_id}
                                                title={m.title}
                                                subtitle={m.year ?? undefined}
                                                posterUrl={m.poster}
                                                type="movie"
                                                dimmed={!isAdded}
                                                meta={m.character ? <span className="text-[11px] text-white/70">Rôle : {m.character}</span> : undefined}
                                                corner={
                                                    m.vote_average ? (
                                                        <PosterBadge>
                                                            <Star className="h-2.5 w-2.5 fill-amber-400 text-amber-400" aria-hidden />
                                                            {m.vote_average.toFixed(1)}
                                                        </PosterBadge>
                                                    ) : undefined
                                                }
                                                badges={isAdded ? <PosterBadge tone="primary">Ajouté</PosterBadge> : undefined}
                                                action={
                                                    <Button
                                                        size="icon-sm"
                                                        variant={isAdded ? "secondary" : "default"}
                                                        className="rounded-full"
                                                        disabled={isAdded || isAdding}
                                                        aria-label={isAdded ? `« ${m.title} » ajouté` : `Ajouter « ${m.title} » à Radarr`}
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            addMovie(m);
                                                        }}
                                                    >
                                                        {isAdding ? <Loader2 className="animate-spin" /> : isAdded ? <Check /> : <Plus />}
                                                    </Button>
                                                }
                                            />
                                        );
                                    })}
                                </motion.div>
                            </section>
                        )}
                    </div>
                ) : null}
            </DialogContent>
        </Dialog>
    );
}
