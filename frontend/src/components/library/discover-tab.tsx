"use client";

/**
 * Onglet « Découvrir » de /search (remplace l'ancienne page
 * /recommendations) : rangées horizontales façon Netflix.
 * ----------------------------------------------------------------
 *  - « À la carte » : choisis un titre de ta médiathèque (« À partir de… »)
 *    et TMDB propose des titres dans la même veine (porté du serveur) ;
 *  - « Parce que tu as aimé {titre} » : UNE rangée par titre de ta
 *    bibliothèque, avec sa vignette et un lien vers sa fiche (avant : les
 *    groupes étaient lus comme des films à plat → tuiles vides) ;
 *  - Films / Séries tendance de la semaine (TMDB) ;
 *  - Toujours attendus : tes médias surveillés encore sans fichier.
 * Un clic sur une affiche ouvre la fiche TMDB détaillée (casting,
 * bande-annonce…) ; le bouton « + » de l'affiche ajoute directement, sans
 * ouvrir la fiche.
 * Ajouter une série tendance envoie son ID TMDB comme tel : le backend le
 * convertit en ID TVDB (avant : Sonarr recevait l'ID TMDB pris pour un ID
 * TVDB et ajoutait une autre série).
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
    ArrowUpRight,
    Check,
    ChevronsUpDown,
    Clapperboard,
    Compass,
    Flame,
    KeyRound,
    Loader2,
    PackageX,
    Search,
    Shuffle,
    Sparkles,
    Tv,
    X,
} from "lucide-react";
import {
    useLibraryPicker,
    useRecommendations,
    useRecommendationsBasedOn,
    type IdSource,
    type LibrarySelectItem,
} from "@/hooks/use-recommendations";
import { useDebounce } from "@/hooks/use-debounce";
import { RatingBadge } from "@/components/shared/rating-badge";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { MediaThumb } from "./media-thumb";
import { PosterRail, RailItem } from "./poster-rail";
import { AddButton } from "./add-button";
import { fromTmdb, useAdder, type AddableItem } from "./adder";

/** Lien vers la fiche d'un média de la bibliothèque (ID Radarr/Sonarr). */
function libraryHref(type: string | undefined, id: string | number | null | undefined): string | null {
    if (id === null || id === undefined || id === "") return null;
    return `/media/${type === "series" ? "series" : "movie"}/${id}`;
}

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

            {data?.tmdb_available && <BasedOnSection items={data.library_select_items ?? []} onPreview={onPreview} />}

            {groups.map((g) => {
                const href = libraryHref(g.base_type, g.base_id);
                const kind = g.base_type === "series" ? "Série" : "Film";
                return (
                    <PosterRail
                        key={`${g.base_type ?? "movie"}:${g.base_id ?? g.base_title}`}
                        title={
                            <>
                                Parce que tu as aimé{" "}
                                {href ? (
                                    <Link href={href} className="text-gradient transition-opacity hover:opacity-80" title={`Voir la fiche de ${g.base_title}`}>
                                        {g.base_title}
                                    </Link>
                                ) : (
                                    <span className="text-gradient">{g.base_title}</span>
                                )}
                            </>
                        }
                        subtitle={`${kind} de ta médiathèque · recommandations TMDB`}
                        leading={
                            href ? (
                                // Doublon souris du lien du titre : retiré du parcours clavier.
                                <Link href={href} tabIndex={-1} aria-hidden className="group shrink-0">
                                    <MediaThumb src={g.base_poster} alt="" type={g.base_type} className="h-12 w-8 rounded-md" />
                                </Link>
                            ) : (
                                <MediaThumb src={g.base_poster} alt="" type={g.base_type} className="h-12 w-8 rounded-md" />
                            )
                        }
                        action={
                            href ? (
                                <Button variant="ghost" size="sm" asChild className="hidden text-muted-foreground sm:inline-flex">
                                    <Link href={href}>
                                        Sa fiche <ArrowUpRight />
                                    </Link>
                                </Button>
                            ) : undefined
                        }
                    >
                        {g.items.map((it) => (
                            <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                        ))}
                    </PosterRail>
                );
            })}

            {trendingMovies.length > 0 && (
                <PosterRail title="Films tendance" subtitle="Les plus regardés cette semaine" icon={Flame} iconClassName="text-orange-400">
                    {trendingMovies.map((it) => (
                        <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                    ))}
                </PosterRail>
            )}

            {trendingSeries.length > 0 && (
                <PosterRail title="Séries tendance" subtitle="Les plus suivies cette semaine" icon={Tv} iconClassName="text-primary">
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
                    iconClassName="text-warning"
                    action={
                        <Button variant="ghost" size="sm" asChild className="text-muted-foreground">
                            <Link href="/media/missing">Tout voir</Link>
                        </Button>
                    }
                >
                    {wanted.map((w) => (
                        <RailItem key={`${w.type}:${w.id ?? w.title}:${w.year ?? ""}`}>
                            <PosterCard
                                title={w.title}
                                subtitle={`${w.year ?? "—"} · ${w.type === "series" ? "Série" : "Film"}`}
                                posterUrl={w.poster_url}
                                type={w.type}
                                // Fiche du média si le backend donne son ID *arr, sinon la page des manquants filtrée.
                                href={libraryHref(w.type, w.id) ?? `/media/missing?q=${encodeURIComponent(w.title)}`}
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

/** Affiche d'une suggestion : note TMDB, bouton + flottant, fiche détaillée au clic. */
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
                rating={<RatingBadge value={item.rating} source={item.rating_source} />}
                corner={
                    item.in_library ? (
                        <PosterBadge tone="success" title="Déjà dans ta bibliothèque">
                            <Check className="h-2.5 w-2.5" strokeWidth={3} /> À toi
                        </PosterBadge>
                    ) : (
                        // AddButton stoppe la propagation : le clic ajoute sans ouvrir la fiche.
                        <AddButton state={stateOf(item.key)} onAdd={() => add(item)} title={item.title} />
                    )
                }
                meta={item.overview ? <p className="line-clamp-3 text-[11px] leading-snug text-white/75">{item.overview}</p> : undefined}
            />
        </RailItem>
    );
}

/* ════════════════════════════════════════════════════════════════
   « À partir de… » : recommandations ciblées
   ════════════════════════════════════════════════════════════════ */

/** Clé stable d'un titre de la bibliothèque. */
const pickKey = (it: LibrarySelectItem) => `${it.type}:${it.id ?? `id${it.tmdb_id}`}`;

/** Mélange de Fisher-Yates (copie : le tableau d'origine n'est pas touché). */
function shuffle<T>(list: readonly T[]): T[] {
    const out = [...list];
    for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
}

/** Minuscules sans accents : « Amélie » se trouve en tapant « amelie ». */
const normalize = (s: string) =>
    s
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();

/**
 * Type d'ID à envoyer à /based_on. Pour une série de la bibliothèque, le
 * champ `tmdb_id` contient l'ID TVDB (Sonarr) : on le signale au backend,
 * qui le traduit en ID TMDB. Sans `id_source` (ancien backend), on applique
 * la même convention que l'agrégateur.
 */
const sourceOf = (it: LibrarySelectItem): IdSource =>
    it.id_source === "tvdb" || it.id_source === "tmdb" ? it.id_source : it.type === "series" ? "tvdb" : "tmdb";

function BasedOnSection({ items, onPreview }: { items: LibrarySelectItem[]; onPreview: (item: AddableItem) => void }) {
    // Seuls les titres avec un ID exploitable peuvent servir de point de départ.
    const base = useMemo(() => items.filter((it) => !!it.tmdb_id && !!it.title), [items]);
    const [selected, setSelected] = useState<LibrarySelectItem | null>(null);

    // Quelques idées cliquables tant que rien n'est choisi (tirées au hasard
    // une fois par affichage de l'onglet, pour varier les plaisirs).
    const ideas = useMemo(() => shuffle(base).slice(0, 6), [base]);

    const pickRandom = () => {
        const pool = base.filter((it) => !selected || pickKey(it) !== pickKey(selected));
        if (pool.length) setSelected(pool[Math.floor(Math.random() * pool.length)]);
    };

    return (
        <motion.section variants={fadeUp} className="glass border-gradient relative overflow-hidden rounded-3xl p-4 md:p-6">

            <div className="relative space-y-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/30 to-primary/10 text-primary ring-1 ring-primary/30">
                            <Compass className="h-5 w-5" />
                        </span>
                        <div className="min-w-0">
                            <h3 className="text-base font-semibold tracking-tight">Recommandations à la carte</h3>
                            <p className="text-xs text-muted-foreground">
                                Choisis un titre de ta médiathèque : TMDB te propose des films ou séries dans la même veine.
                            </p>
                        </div>
                    </div>
                    <div className="flex w-full items-center gap-2 lg:w-auto">
                        <LibraryPicker base={base} selected={selected} onSelect={setSelected} />
                        <Button
                            variant="outline"
                            size="icon"
                            className="h-11 w-11 shrink-0 rounded-xl"
                            onClick={pickRandom}
                            disabled={base.length === 0}
                            aria-label="Choisir un titre au hasard"
                            title="Au hasard"
                        >
                            <Shuffle />
                        </Button>
                    </div>
                </div>

                {selected ? (
                    <BasedOnResults key={pickKey(selected)} item={selected} onClear={() => setSelected(null)} onRandom={pickRandom} onPreview={onPreview} />
                ) : ideas.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="eyebrow mr-1">Idées</span>
                        {ideas.map((it) => (
                            <button key={pickKey(it)} type="button" className="chip max-w-[15rem] pl-1.5" onClick={() => setSelected(it)}>
                                <MediaThumb src={it.poster_url} alt="" type={it.type} className="h-5 w-[14px] rounded-[4px]" />
                                <span className="truncate">{it.title}</span>
                            </button>
                        ))}
                    </div>
                ) : null}
            </div>
        </motion.section>
    );
}

/** Sélecteur avec recherche (Popover + Command) parmi les titres de la bibliothèque. */
function LibraryPicker({
    base,
    selected,
    onSelect,
}: {
    base: LibrarySelectItem[];
    selected: LibrarySelectItem | null;
    onSelect: (item: LibrarySelectItem) => void;
}) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const debounced = useDebounce(query.trim(), 250);
    // Le backend ne joint que 50 titres : au-delà de 2 lettres, on cherche
    // aussi dans toute la médiathèque (/api/media, titres avec fichier).
    const picker = useLibraryPicker(debounced);
    const searching = debounced.length >= 2;

    const { movies, series } = useMemo(() => {
        const q = normalize(query.trim());
        const seen = new Set<string>();
        const out: LibrarySelectItem[] = [];
        const push = (it: LibrarySelectItem) => {
            const k = pickKey(it);
            if (!it.tmdb_id || seen.has(k)) return;
            if (q && !normalize(it.title).includes(q)) return;
            seen.add(k);
            out.push(it);
        };
        base.forEach(push);
        // Résultats serveur filtrés aussi côté client : pendant la frappe,
        // la réponse précédente reste affichée et ne doit pas « déborder ».
        if (searching) (picker.data ?? []).forEach(push);
        const capped = out.slice(0, 60);
        return { movies: capped.filter((it) => it.type !== "series"), series: capped.filter((it) => it.type === "series") };
    }, [base, query, searching, picker.data]);

    const loading = searching && picker.isFetching;
    const empty = movies.length === 0 && series.length === 0;

    const choose = (it: LibrarySelectItem) => {
        onSelect(it);
        setOpen(false);
        setQuery("");
    };

    const renderItem = (it: LibrarySelectItem) => {
        const active = !!selected && pickKey(selected) === pickKey(it);
        return (
            <CommandItem key={pickKey(it)} value={pickKey(it)} onSelect={() => choose(it)} className="group">
                <MediaThumb src={it.poster_url} alt="" type={it.type} className="h-9 w-6 rounded-md" />
                <span className="min-w-0 flex-1 truncate">{it.title}</span>
                {it.year ? <span className="text-[11px] tabular-nums text-muted-foreground">{it.year}</span> : null}
                <Check className={cn("text-primary", active ? "opacity-100" : "opacity-0")} />
            </CommandItem>
        );
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    aria-haspopup="listbox"
                    aria-label={selected ? `Recommandations à partir de ${selected.title} — changer de titre` : "Choisir un titre de ta médiathèque"}
                    className="h-11 min-w-0 flex-1 justify-between rounded-xl px-3 lg:w-80 lg:flex-none"
                >
                    <span className="flex min-w-0 items-center gap-2">
                        {selected ? (
                            <MediaThumb src={selected.poster_url} alt="" type={selected.type} className="h-7 w-5 rounded" />
                        ) : (
                            <Search className="text-muted-foreground" />
                        )}
                        <span className={cn("truncate", !selected && "text-muted-foreground")}>
                            {selected ? selected.title : "À partir de…"}
                        </span>
                    </span>
                    <ChevronsUpDown className="opacity-60" />
                </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-[min(24rem,calc(100vw-2rem))] p-0">
                <Command shouldFilter={false} label="Titres de ta médiathèque">
                    <CommandInput value={query} onValueChange={setQuery} placeholder="Cherche un film ou une série…" className="h-11" />
                    <CommandList className="max-h-[min(20rem,50vh)] p-1">
                        {loading && empty && (
                            <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Recherche dans ta médiathèque…
                            </div>
                        )}
                        {!loading && (
                            <CommandEmpty className="px-4 py-6 text-center text-xs text-muted-foreground">
                                {query.trim().length === 1
                                    ? "Tape au moins deux lettres pour chercher dans toute ta médiathèque."
                                    : "Aucun titre disponible ne correspond."}
                            </CommandEmpty>
                        )}
                        {movies.length > 0 && <CommandGroup heading="Films">{movies.map(renderItem)}</CommandGroup>}
                        {series.length > 0 && <CommandGroup heading="Séries">{series.map(renderItem)}</CommandGroup>}
                        {loading && !empty && (
                            <div className="flex items-center gap-2 px-3 py-2 text-[11px] text-muted-foreground">
                                <Loader2 className="h-3 w-3 animate-spin" /> Recherche dans toute ta médiathèque…
                            </div>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}

/** Rangée des recommandations TMDB pour le titre choisi (chargement / erreur / vide). */
function BasedOnResults({
    item,
    onClear,
    onRandom,
    onPreview,
}: {
    item: LibrarySelectItem;
    onClear: () => void;
    onRandom: () => void;
    onPreview: (item: AddableItem) => void;
}) {
    const { data, isLoading, isError, error, refetch } = useRecommendationsBasedOn(item.type, item.tmdb_id, sourceOf(item));
    const recs = useMemo(() => (data?.items ?? []).map(fromTmdb), [data]);
    const href = libraryHref(item.type, item.id);
    const kind = item.type === "series" ? "série" : "film";

    const clear = (
        <Button variant="ghost" size="icon-sm" onClick={onClear} aria-label="Effacer le titre choisi" title="Effacer">
            <X />
        </Button>
    );

    if (isLoading) {
        return (
            <div className="space-y-3" aria-busy="true" aria-label={`Recherche de recommandations à partir de ${item.title}`}>
                <div className="flex items-center gap-3 px-1">
                    <MediaThumb src={item.poster_url} alt="" type={item.type} className="h-12 w-8 rounded-md" />
                    <div className="space-y-1.5">
                        <Shimmer className="h-4 w-56 max-w-[60vw] rounded-md" />
                        <Shimmer className="h-3 w-32 rounded-md" />
                    </div>
                </div>
                <RailSkeletonRow count={7} />
            </div>
        );
    }

    if (isError) {
        return (
            <div className="rounded-2xl bg-black/20 ring-1 ring-white/[0.06]">
                <ErrorState error={error} onRetry={() => refetch()} title={`Impossible de charger les recommandations pour « ${item.title} »`} compact />
            </div>
        );
    }

    if (recs.length === 0) {
        return (
            <div className="rounded-2xl bg-black/20 ring-1 ring-white/[0.06]">
                <EmptyState
                    compact
                    icon={Clapperboard}
                    title="Aucune recommandation pour ce titre"
                    description={`TMDB ne propose rien à partir de « ${item.title} ». Essaie un autre ${kind}, de préférence plus connu.`}
                    action={{ label: "Un autre au hasard", onClick: onRandom }}
                />
            </div>
        );
    }

    // Variants propres : la rangée s'anime à chaque nouveau titre choisi
    // (la cascade du conteneur parent, elle, n'a lieu qu'une fois).
    return (
        <motion.div variants={stagger(0, 0.08)} initial="hidden" animate="show">
            <PosterRail
                title={
                    <>
                        À partir de{" "}
                        {href ? (
                            <Link href={href} className="text-gradient transition-opacity hover:opacity-80" title={`Voir la fiche de ${item.title}`}>
                                {item.title}
                            </Link>
                        ) : (
                            <span className="text-gradient">{item.title}</span>
                        )}
                    </>
                }
                subtitle={`${recs.length} recommandation${recs.length > 1 ? "s" : ""} TMDB · ${recs.filter((r) => !r.in_library).length} à découvrir`}
                leading={<MediaThumb src={item.poster_url} alt="" type={item.type} className="h-12 w-8 rounded-md" />}
                action={clear}
            >
                {recs.map((it) => (
                    <SuggestionTile key={it.key} item={it} onPreview={onPreview} />
                ))}
            </PosterRail>
        </motion.div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Divers
   ════════════════════════════════════════════════════════════════ */

/** Explique comment activer TMDB (clé absente du .env). */
function TmdbGuide() {
    return (
        <motion.div variants={fadeUp} className="glass border-gradient relative overflow-hidden rounded-2xl p-5 md:p-6">
            <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500/30 to-orange-500/10 text-warning ring-1 ring-warning/30">
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
                    <p className="text-xs text-muted-foreground">Redémarre ensuite le conteneur arrmada-backend.</p>
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

/** Une rangée d'affiches fantômes (mêmes largeurs que RailItem). */
function RailSkeletonRow({ count = 8 }: { count?: number }) {
    return (
        <div className="flex gap-3 overflow-hidden px-2 sm:gap-4">
            {Array.from({ length: count }).map((_, i) => (
                <Shimmer key={i} className="aspect-[2/3] w-[136px] shrink-0 rounded-2xl sm:w-[156px] lg:w-[172px]" />
            ))}
        </div>
    );
}

/** Squelette : bloc « à la carte » + trois rangées d'affiches. */
function RailsSkeleton() {
    return (
        <div className="space-y-8">
            <Shimmer className="h-28 w-full rounded-3xl" />
            {Array.from({ length: 3 }).map((_, r) => (
                <div key={r} className="space-y-3">
                    <Shimmer className="h-6 w-56 rounded-lg" />
                    <RailSkeletonRow />
                </div>
            ))}
        </div>
    );
}
