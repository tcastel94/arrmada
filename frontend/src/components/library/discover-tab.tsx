"use client";

/**
 * Onglet « Suggestions » de /search (remplace l'ancienne page
 * /recommendations) : rangées horizontales façon Netflix.
 * ----------------------------------------------------------------
 *  - « Parce que tu as {film} » : une rangée par film de ta bibliothèque
 *    (avant : les groupes étaient lus comme des films à plat → tuiles
 *    vides et ajout avec un titre « undefined ») ;
 *  - Films / Séries tendance de la semaine (TMDB) ;
 *  - Toujours attendus : tes médias surveillés encore sans fichier.
 * Ajouter une série tendance envoie son ID TMDB comme tel : le backend le
 * convertit en ID TVDB (avant : Sonarr recevait l'ID TMDB pris pour un ID
 * TVDB et ajoutait une autre série).
 */
import { useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Clapperboard, Flame, KeyRound, PackageX, Sparkles, Star, Tv } from "lucide-react";
import { useRecommendations } from "@/hooks/use-recommendations";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { fadeUp, stagger } from "@/lib/motion";
import { MediaThumb } from "./media-thumb";
import { PosterRail, RailItem } from "./poster-rail";
import { AddButton } from "./add-button";
import { fromTmdb, useAdder, type AddableItem } from "./adder";

export function DiscoverTab({ onPreview }: { onPreview: (item: AddableItem) => void }) {
    const { data, isLoading, isError, error, refetch } = useRecommendations();

    const groups = useMemo(
        () =>
            (data?.because_you_have ?? [])
                .filter((g) => g && Array.isArray(g.recommendations) && g.recommendations.length > 0)
                .map((g) => ({ ...g, items: g.recommendations.map(fromTmdb) })),
        [data],
    );
    const trendingMovies = useMemo(() => (data?.trending_movies ?? []).map(fromTmdb), [data]);
    const trendingSeries = useMemo(() => (data?.trending_series ?? []).map(fromTmdb), [data]);
    const wanted = data?.wanted ?? [];

    if (isLoading) return <RailsSkeleton />;
    if (isError) {
        return (
            <div className="glass rounded-2xl">
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger les suggestions" />
            </div>
        );
    }

    const nothing = groups.length === 0 && trendingMovies.length === 0 && trendingSeries.length === 0;

    return (
        <motion.div variants={stagger(0, 0.1)} initial="hidden" animate="show" className="space-y-6">
            {!data?.tmdb_available && <TmdbGuide />}

            {groups.map((g, i) => (
                <PosterRail
                    key={`${g.base_title}-${i}`}
                    title={
                        <>
                            Parce que tu as <span className="text-gradient">{g.base_title}</span>
                        </>
                    }
                    subtitle="Recommandations TMDB à partir de ta bibliothèque"
                    leading={<MediaThumb src={g.base_poster} alt={g.base_title} type="movie" className="h-12 w-8 rounded-md" />}
                >
                    {g.items.map((it) => (
                        <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                    ))}
                </PosterRail>
            ))}

            {trendingMovies.length > 0 && (
                <PosterRail title="Films tendance" subtitle="Les plus regardés cette semaine" icon={Flame} iconClassName="text-orange-400">
                    {trendingMovies.map((it) => (
                        <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                    ))}
                </PosterRail>
            )}

            {trendingSeries.length > 0 && (
                <PosterRail title="Séries tendance" subtitle="Les plus suivies cette semaine" icon={Tv} iconClassName="text-sky-400">
                    {trendingSeries.map((it) => (
                        <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                    ))}
                </PosterRail>
            )}

            {wanted.length > 0 && (
                <PosterRail
                    title="Toujours attendus"
                    subtitle="Surveillés, mais encore sans fichier"
                    icon={PackageX}
                    iconClassName="text-amber-400"
                    action={
                        <Button variant="ghost" size="sm" asChild className="text-muted-foreground">
                            <Link href="/media/missing">Tout voir</Link>
                        </Button>
                    }
                >
                    {wanted.map((w) => (
                        <RailItem key={`${w.type}:${w.title}:${w.year ?? ""}`}>
                            <PosterCard
                                title={w.title}
                                subtitle={`${w.year ?? "—"} · ${w.type === "series" ? "Série" : "Film"}`}
                                posterUrl={w.poster_url}
                                type={w.type}
                                href={`/media/missing?q=${encodeURIComponent(w.title)}`}
                                dimmed
                                corner={<PosterBadge tone="warning">Attendu</PosterBadge>}
                            />
                        </RailItem>
                    ))}
                </PosterRail>
            )}

            {nothing && data?.tmdb_available && (
                <motion.div variants={fadeUp} className="glass rounded-2xl">
                    <EmptyState
                        icon={Sparkles}
                        title="Pas de suggestion pour le moment"
                        description="TMDB n'a rien renvoyé. Réessaie un peu plus tard : les tendances sont mises à jour chaque semaine."
                        action={{ label: "Réessayer", onClick: () => refetch() }}
                    />
                </motion.div>
            )}
        </motion.div>
    );
}

/** Affiche d'une suggestion : note TMDB, bouton + flottant, aperçu au clic. */
function SuggestionTile({ item, onPreview }: { item: AddableItem; onPreview: (item: AddableItem) => void }) {
    const { add, stateOf } = useAdder();
    return (
        <RailItem>
            <PosterCard
                title={item.title}
                subtitle={`${item.year ?? "—"} · ${item.type === "series" ? "Série" : "Film"}`}
                posterUrl={item.poster_url}
                type={item.type}
                onClick={() => onPreview(item)}
                badges={
                    item.rating ? (
                        <PosterBadge title="Note TMDB">
                            <Star className="h-2.5 w-2.5 fill-amber-400 text-amber-400" />
                            {item.rating.toFixed(1)}
                        </PosterBadge>
                    ) : undefined
                }
                corner={
                    item.in_library ? (
                        <PosterBadge tone="success" title="Déjà dans ta bibliothèque">
                            <Check className="h-2.5 w-2.5" strokeWidth={3} /> À toi
                        </PosterBadge>
                    ) : (
                        <AddButton state={stateOf(item.key)} onAdd={() => add(item)} title={item.title} />
                    )
                }
                meta={item.overview ? <p className="line-clamp-3 text-[11px] leading-snug text-white/75">{item.overview}</p> : undefined}
            />
        </RailItem>
    );
}

/** Explique comment activer TMDB (clé absente du .env). */
function TmdbGuide() {
    return (
        <motion.div variants={fadeUp} className="glass border-gradient relative overflow-hidden rounded-2xl p-5 md:p-6">
            <div aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-amber-500/20 blur-3xl" />
            <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500/30 to-orange-500/10 text-amber-300 ring-1 ring-amber-400/30">
                    <KeyRound className="h-6 w-6" />
                </span>
                <div className="space-y-2 text-sm">
                    <p className="text-base font-semibold">Active les suggestions TMDB</p>
                    <p className="text-muted-foreground">
                        Les tendances et les recommandations personnalisées viennent de The Movie Database. Crée une clé API gratuite sur
                        themoviedb.org, puis ajoute-la au fichier <code className="kbd">.env</code> du backend :
                    </p>
                    <pre className="overflow-x-auto rounded-xl bg-black/40 px-3 py-2 font-mono text-xs text-brand ring-1 ring-white/[0.06]">
                        TMDB_API_KEY=ta_cle_api
                    </pre>
                    <p className="text-xs text-muted-foreground">Redémarre ensuite le conteneur arrmada.</p>
                    <Button variant="outline" size="sm" asChild>
                        <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noreferrer noopener">
                            <Clapperboard /> Obtenir une clé TMDB
                        </a>
                    </Button>
                </div>
            </div>
        </motion.div>
    );
}

/** Squelette : trois rangées d'affiches. */
function RailsSkeleton() {
    return (
        <div className="space-y-8">
            {Array.from({ length: 3 }).map((_, r) => (
                <div key={r} className="space-y-3">
                    <Shimmer className="h-6 w-56 rounded-lg" />
                    <div className="flex gap-4 overflow-hidden">
                        {Array.from({ length: 8 }).map((__, i) => (
                            <Shimmer key={i} className="aspect-[2/3] w-[136px] shrink-0 rounded-2xl sm:w-[156px] lg:w-[172px]" />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

