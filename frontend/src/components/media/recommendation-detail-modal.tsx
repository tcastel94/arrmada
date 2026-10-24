"use client";

/**
 * Fiche détaillée d'un titre TMDB (suggestion de l'onglet « Découvrir » ou
 * résultat « À ajouter » de la recherche).
 * ----------------------------------------------------------------
 * Affiche, fond, synopsis, genres traduits, note, réalisation, casting et
 * bande-annonce YouTube, plus le bouton « Ajouter » du flux d'ajout commun
 * (AdderProvider) : ajouter depuis la modale marque aussi la tuile d'origine
 * comme ajoutée, et inversement.
 *
 * Chargement progressif : la tuile cliquée fournit déjà titre, affiche et
 * résumé (`preview`) ; on les montre tout de suite, puis la fiche TMDB
 * (/api/recommendations/details) complète le reste. Sans ID TMDB (série
 * Sonarr inconnue de TMDB) ou sans clé TMDB, la modale reste utile : elle
 * garde l'aperçu et le bouton d'ajout.
 *
 * Vie privée : le lecteur YouTube (domaine youtube-nocookie) n'est chargé
 * qu'au clic sur « Bande-annonce », jamais à l'ouverture de la fiche.
 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertTriangle,
    ArrowUpRight,
    CalendarDays,
    Check,
    Clock,
    ExternalLink,
    Film,
    Loader2,
    Play,
    Plus,
    RotateCcw,
    Tv,
    Users,
    X,
} from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/empty-state";
import { formatRating } from "@/components/shared/rating-badge";
import { RingGauge } from "@/components/fx/ring-gauge";
import { TiltCard } from "@/components/fx/tilt-card";
import { useRecommendationDetail, type TMDBCastMember, type TMDBDetail } from "@/hooks/use-recommendations";
import {
    AdderProvider,
    externalLink,
    fromTmdbDetail,
    useAdder,
    useOptionalAdder,
    type AddableItem,
} from "@/components/library/adder";
import { translateGenre } from "@/lib/genres";
import { WatchlistButton } from "@/components/watchlist/watchlist-button";
import { formatDuration, formatShortDate, plural } from "@/lib/format";
import { EASE_OUT, SPRING_SOFT, scaleIn, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface RecommendationDetailModalProps {
    /** Vrai ID TMDB du titre (null → pas de fiche TMDB, seul `preview` est affiché). */
    tmdbId: number | null;
    mediaType?: "movie" | "series" | string;
    isOpen: boolean;
    onClose: () => void;
    /** Données déjà connues (tuile cliquée) : affichées immédiatement, puis enrichies. */
    preview?: AddableItem | null;
    /** Action « Voir le suivi » proposée après un ajout (onglet Suivi de /search). */
    onShowTracking?: () => void;
}

/**
 * Point d'entrée. Sur /search, la modale partage l'AdderProvider de la page ;
 * ailleurs (fiche média, tableau de bord…), elle crée le sien pour que le
 * bouton « Ajouter » fonctionne quand même.
 */
export function RecommendationDetailModal(props: RecommendationDetailModalProps) {
    const adder = useOptionalAdder();
    const dialog = <DetailDialog {...props} />;
    return adder ? dialog : <AdderProvider onShowTracking={props.onShowTracking}>{dialog}</AdderProvider>;
}

interface Shown {
    tmdbId: number | null;
    type: "movie" | "series";
    preview: AddableItem | null;
}

function DetailDialog({ tmdbId, mediaType = "movie", isOpen, onClose, preview = null, onShowTracking }: RecommendationDetailModalProps) {
    const type: Shown["type"] = (preview?.type ?? mediaType) === "series" ? "series" : "movie";
    const current: Shown | null = isOpen && (tmdbId || preview) ? { tmdbId, type, preview } : null;

    // Le parent remet souvent son état à null dès la fermeture : on garde le
    // dernier titre affiché pour que le contenu ne disparaisse pas pendant
    // l'animation de sortie (état dérivé, mis à jour pendant le rendu).
    const [last, setLast] = useState<Shown | null>(current);
    if (current && (current.tmdbId !== last?.tmdbId || current.type !== last?.type || current.preview !== last?.preview)) {
        setLast(current);
    }
    const shown = current ?? last;

    return (
        <Dialog open={!!current} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-3xl gap-0 overflow-x-hidden p-0">
                {shown && (
                    <DetailBody
                        // Nouvelle clé = nouvel état (bande-annonce fermée, défilement en haut).
                        key={`${shown.type}:${shown.tmdbId ?? shown.preview?.key ?? ""}`}
                        {...shown}
                        active={!!current}
                        onClose={onClose}
                        onShowTracking={onShowTracking}
                    />
                )}
            </DialogContent>
        </Dialog>
    );
}

function DetailBody({
    tmdbId,
    type,
    preview,
    active,
    onClose,
    onShowTracking,
}: Shown & { active: boolean; onClose: () => void; onShowTracking?: () => void }) {
    const { data: detail, isLoading, isError, error, refetch, isFetching } = useRecommendationDetail(type, tmdbId, active);
    const [playing, setPlaying] = useState(false);
    const trailerRef = useRef<HTMLDivElement>(null);

    // Le lecteur s'ouvre sous les boutons : on le fait défiler dans la vue.
    useEffect(() => {
        if (!playing) return;
        const t = window.setTimeout(() => trailerRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 120);
        return () => window.clearTimeout(t);
    }, [playing]);

    const loading = !!tmdbId && isLoading;

    // Sans aperçu, rien à montrer tant que la fiche n'est pas là.
    if (!preview && loading) return <FullSkeleton />;
    if (!preview && !detail) {
        return (
            <div className="p-6">
                <DialogTitle className="sr-only">Fiche indisponible</DialogTitle>
                <DialogDescription className="sr-only">La fiche TMDB de ce titre n&apos;a pas pu être chargée.</DialogDescription>
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger cette fiche" compact />
            </div>
        );
    }

    // Fusion : la fiche TMDB complète prime, l'aperçu comble en attendant.
    const title = detail?.title ?? preview?.title ?? "";
    // Affiche : celle de la tuile d'abord (déjà en cache navigateur → pas de
    // clignotement quand la fiche TMDB arrive avec une autre taille d'image).
    const poster = preview?.poster_url ?? detail?.poster_url ?? null;
    const backdrop = detail?.backdrop_url ?? null;
    const overview = detail?.overview || preview?.overview || "";
    const year = detail?.year ?? (preview?.year ? String(preview.year) : null);
    const rating = detail?.rating ?? preview?.rating ?? null;
    // Ancien serveur (sans source) : c'était la note TMDB
    const ratingSource = detail?.rating_source ?? preview?.rating_source ?? (rating ? "tmdb" : null);
    const genres = detail?.genres ?? [];
    const cast = detail?.cast ?? [];
    const trailerKey = detail?.trailer_key ?? null;
    const TypeIcon = type === "series" ? Tv : Film;

    // Élément ajoutable : l'aperçu prime. Il porte les bons IDs (un résultat
    // Sonarr a aussi l'ID TVDB, plus sûr pour l'ajout), la même clé que la
    // tuile (état « ajouté » partagé) et un « déjà possédé » fiable : celui
    // du lookup Radarr/Sonarr est calculé par ID, alors que /details compare
    // aussi les titres (un remake homonyme passerait pour « déjà là » et le
    // bouton Ajouter disparaîtrait).
    const addable: AddableItem | null = preview ?? (detail ? fromTmdbDetail(detail) : null);
    const link = addable ? externalLink(addable) : null;

    return (
        <div className="relative">
            {/* ── Fond « cinéma » ── */}
            <div aria-hidden className="relative h-40 w-full overflow-hidden sm:h-64">
                {/* Couche 1 : l'affiche floutée, visible tout de suite (ou seule s'il n'y a pas de fond TMDB). */}
                {poster ? (
                    <img src={poster} alt="" className="absolute inset-0 h-full w-full scale-125 object-cover opacity-40 blur-2xl" />
                ) : loading ? (
                    <Shimmer className="absolute inset-0 rounded-none" />
                ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/25 via-brand/10 to-transparent" />
                )}
                {/* Couche 2 : le fond TMDB arrive en fondu par-dessus (effet « mise au point »). */}
                {backdrop && (
                    <motion.img
                        src={backdrop}
                        alt=""
                        initial={{ opacity: 0, scale: 1.08 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 1.1, ease: EASE_OUT }}
                        className="absolute inset-0 h-full w-full object-cover"
                    />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-popover via-popover/60 to-transparent" />
                {/* Assombrit le haut : le bouton « Fermer » reste lisible sur un fond clair. */}
                <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/60 to-transparent" />
            </div>

            <div className="relative -mt-20 px-5 pb-6 sm:-mt-28 sm:px-7 sm:pb-7">
                {/* ── Affiche + titre ── */}
                <div className="flex gap-4 sm:gap-6">
                    <motion.div
                        initial={{ opacity: 0, y: 18, scale: 0.94 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={SPRING_SOFT}
                        className="w-24 shrink-0 sm:w-36"
                    >
                        <TiltCard className="rounded-2xl" max={8}>
                            <div className="relative aspect-[2/3] overflow-hidden rounded-2xl bg-muted/40 shadow-[0_24px_60px_-18px_rgba(0,0,0,0.95)] ring-1 ring-white/10">
                                {poster ? (
                                    <img src={poster} alt={`Affiche de ${title}`} className="h-full w-full object-cover" />
                                ) : loading ? (
                                    <Shimmer className="h-full w-full rounded-none" />
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/60 to-primary/10">
                                        <TypeIcon className="h-8 w-8 text-muted-foreground/40" strokeWidth={1.5} />
                                    </div>
                                )}
                            </div>
                        </TiltCard>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, ease: EASE_OUT, delay: 0.05 }}
                        className="min-w-0 flex-1 space-y-2 pt-[4.5rem] sm:pt-24"
                    >
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                            <MetaChip icon={TypeIcon}>{type === "series" ? "Série" : "Film"}</MetaChip>
                            {year && <MetaChip>{year}</MetaChip>}
                            {detail?.runtime ? (
                                <MetaChip icon={Clock} title={type === "series" ? "Durée d'un épisode" : "Durée"}>
                                    {formatDuration(detail.runtime * 60)}
                                </MetaChip>
                            ) : null}
                            {detail?.release_date && (
                                <MetaChip icon={CalendarDays} title={type === "series" ? "Première diffusion" : "Sortie"} className="hidden sm:inline-flex">
                                    {formatShortDate(detail.release_date)}
                                </MetaChip>
                            )}
                        </div>
                        <DialogTitle className="text-balance text-xl font-bold leading-tight tracking-tight sm:text-3xl">{title}</DialogTitle>
                        {detail?.original_title && detail.original_title !== title && (
                            <p className="truncate text-xs italic text-muted-foreground" title={detail.original_title}>
                                {detail.original_title}
                            </p>
                        )}
                        {detail?.director ? (
                            <p className="text-xs text-muted-foreground">
                                <span className="font-medium text-foreground/80">{type === "series" ? "Création" : "Réalisation"} · </span>
                                {detail.director}
                            </p>
                        ) : (
                            loading && <Shimmer className="h-3 w-40 rounded-md" />
                        )}
                        <DialogDescription className="sr-only">
                            Fiche détaillée de {title} : synopsis, casting, bande-annonce et ajout à ta médiathèque.
                        </DialogDescription>
                    </motion.div>
                </div>

                {/* ── Actions + note ── */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45, ease: EASE_OUT, delay: 0.12 }}
                    className="mt-5 flex flex-wrap items-center gap-2"
                >
                    {addable && <AddAction item={addable} detail={detail} onShowTracking={onShowTracking} onNavigate={onClose} />}
                    {addable && (
                        // « + Ma liste » : s'il n'est pas sur le NAS, le titre est aussi demandé
                        <WatchlistButton
                            size="default"
                            request
                            target={{
                                media_type: addable.type,
                                tmdb_id: addable.tmdb_id ?? tmdbId,
                                tvdb_id: addable.tvdb_id,
                                title: addable.title,
                                year: addable.year,
                                poster_url: addable.poster_url,
                            }}
                            className="flex-none"
                        />
                    )}
                    {trailerKey && (
                        <Button
                            variant="glow"
                            onClick={() => setPlaying((p) => !p)}
                            aria-expanded={playing}
                            aria-controls={playing ? "tmdb-trailer" : undefined}
                        >
                            {playing ? <X /> : <Play className="fill-current" />}
                            {playing ? "Fermer la vidéo" : "Bande-annonce"}
                        </Button>
                    )}
                    {link && (
                        <Button variant="ghost" asChild className="text-muted-foreground">
                            <a href={link.href} target="_blank" rel="noreferrer noopener">
                                Fiche {link.label}
                                <ExternalLink />
                            </a>
                        </Button>
                    )}
                    {rating ? (
                        <RatingBlock
                            rating={rating}
                            source={ratingSource}
                            votes={detail?.rating_votes ?? detail?.vote_count}
                            metacritic={detail?.metacritic}
                            rottenTomatoes={detail?.rotten_tomatoes}
                        />
                    ) : null}
                </motion.div>

                {/* ── Bande-annonce (chargée uniquement à la demande) ── */}
                <AnimatePresence initial={false}>
                    {playing && trailerKey && (
                        <motion.div
                            key="trailer"
                            id="tmdb-trailer"
                            ref={trailerRef}
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.4, ease: EASE_OUT }}
                            className="overflow-hidden"
                        >
                            <div className="mt-5 overflow-hidden rounded-2xl bg-black shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)] ring-1 ring-white/10">
                                <div className="aspect-video w-full">
                                    <iframe
                                        src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(trailerKey)}?autoplay=1&rel=0`}
                                        title={`Bande-annonce de ${title}`}
                                        className="h-full w-full border-0"
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                                        referrerPolicy="strict-origin-when-cross-origin"
                                        allowFullScreen
                                    />
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* ── Fiche TMDB en échec : on garde l'aperçu, avec un mot d'explication ── */}
                {isError && <DetailError error={error} retrying={isFetching} onRetry={() => refetch()} />}

                {/* ── Genres ── */}
                {genres.length > 0 ? (
                    <div className="mt-5 flex flex-wrap gap-1.5">
                        {genres.map((g) => (
                            <span key={g} className="chip cursor-default">
                                {translateGenre(g)}
                            </span>
                        ))}
                    </div>
                ) : (
                    loading && (
                        <div className="mt-5 flex gap-1.5">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Shimmer key={i} className="h-6 w-20 rounded-full" />
                            ))}
                        </div>
                    )
                )}

                {/* ── Synopsis ── */}
                <section className="mt-6 space-y-2">
                    <h3 className="eyebrow">Synopsis</h3>
                    {overview ? (
                        <p className="text-sm leading-relaxed text-foreground/85">{overview}</p>
                    ) : loading ? (
                        <div className="space-y-2">
                            <Shimmer className="h-3.5 w-full rounded-md" />
                            <Shimmer className="h-3.5 w-11/12 rounded-md" />
                            <Shimmer className="h-3.5 w-2/3 rounded-md" />
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">Pas de résumé disponible pour ce titre.</p>
                    )}
                </section>

                {/* ── Casting ── */}
                {cast.length > 0 ? (
                    <section className="mt-6 space-y-3">
                        <h3 className="eyebrow flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5" /> Têtes d&apos;affiche
                        </h3>
                        <motion.ul variants={stagger(0.1, 0.04)} initial="hidden" animate="show" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                            {cast.map((member, i) => (
                                <motion.li key={`${member.name}-${member.character ?? i}`} variants={scaleIn}>
                                    <CastTile member={member} />
                                </motion.li>
                            ))}
                        </motion.ul>
                    </section>
                ) : (
                    loading && (
                        <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Shimmer key={i} className="h-14 rounded-xl" />
                            ))}
                        </div>
                    )
                )}
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Sous-composants
   ════════════════════════════════════════════════════════════════ */

/** Bouton principal : Ajouter → Ajouté, ou lien vers la fiche si déjà présent. */
function AddAction({
    item,
    detail,
    onShowTracking,
    onNavigate,
}: {
    item: AddableItem;
    detail?: TMDBDetail;
    onShowTracking?: () => void;
    onNavigate: () => void;
}) {
    const { add, stateOf } = useAdder();
    const state = stateOf(item.key);
    const service = item.type === "series" ? "Sonarr" : "Radarr";

    if (item.in_library) {
        // Lien direct vers la fiche quand le backend connaît l'ID Radarr/Sonarr,
        // sinon recherche du titre dans la médiathèque.
        const lib = detail?.library_item;
        const libType = lib?.type === "series" || lib?.type === "movie" ? lib.type : item.type;
        const href = lib?.id ? `/media/${libType}/${lib.id}` : `/media?q=${encodeURIComponent(item.title)}`;
        return (
            <>
                <span className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-success/10 px-3 text-sm text-success ring-1 ring-success/25">
                    <Check className="h-4 w-4" /> Dans ta médiathèque
                </span>
                <Button variant="outline" asChild>
                    <Link href={href} onClick={onNavigate}>
                        Voir la fiche <ArrowUpRight />
                    </Link>
                </Button>
            </>
        );
    }

    if (state === "added") {
        return (
            <>
                <motion.span
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-success/10 px-3 text-sm text-success ring-1 ring-success/25"
                >
                    <Check className="h-4 w-4" /> Ajouté — recherche lancée
                </motion.span>
                {onShowTracking && (
                    <Button variant="outline" onClick={onShowTracking}>
                        Voir le suivi
                    </Button>
                )}
            </>
        );
    }

    return (
        <Button onClick={() => add(item)} disabled={state === "adding"} className="min-w-[11rem]">
            {state === "adding" ? <Loader2 className="animate-spin" /> : <Plus />}
            {state === "adding" ? "Ajout en cours…" : `Ajouter à ${service}`}
        </Button>
    );
}

/**
 * Note la plus fiable (IMDb, sinon TMDB) en jauge circulaire + nombre de
 * votes ; pour un film, Metacritic (critiques de presse) et Rotten Tomatoes
 * (% de critiques positives) en dessous quand ils existent.
 */
function RatingBlock({
    rating,
    source,
    votes,
    metacritic,
    rottenTomatoes,
}: {
    rating: number;
    source: "imdb" | "tmdb" | null | undefined;
    votes?: number | null;
    metacritic?: number | null;
    rottenTomatoes?: number | null;
}) {
    const label = source === "imdb" ? "IMDb" : "TMDB";
    const critics = [metacritic ? `Metacritic ${metacritic}` : null, rottenTomatoes ? `Rotten Tomatoes ${rottenTomatoes} %` : null].filter(Boolean);
    return (
        <div className="ml-auto flex items-center gap-2.5" title={`Note moyenne des spectateurs sur ${label}`}>
            <RingGauge value={rating * 10} size={44} stroke={4} tone="amber">
                <span className="text-xs font-bold tabular-nums">{formatRating(rating)}</span>
            </RingGauge>
            <div className="leading-tight">
                <p className="text-xs font-medium">Note {label}</p>
                {votes ? <p className="text-[11px] text-muted-foreground">{plural(votes, "vote")}</p> : null}
                {critics.length > 0 && <p className="text-[11px] text-muted-foreground">{critics.join(" · ")}</p>}
            </div>
        </div>
    );
}

/** Petite pastille d'information (type, année, durée…). */
function MetaChip({
    icon: Icon,
    children,
    title,
    className,
}: {
    icon?: typeof Film;
    children: ReactNode;
    title?: string;
    className?: string;
}) {
    return (
        <span
            title={title}
            className={cn(
                "inline-flex items-center gap-1 rounded-full bg-white/[0.06] px-2 py-0.5 tabular-nums text-foreground/85 ring-1 ring-white/10 backdrop-blur",
                className,
            )}
        >
            {Icon && <Icon className="h-3 w-3" />}
            {children}
        </span>
    );
}

/** Vignette d'un acteur : photo ronde (ou initiales) + nom + rôle. */
function CastTile({ member }: { member: TMDBCastMember }) {
    const [failed, setFailed] = useState(false);
    const initials = member.name
        .split(/\s+/)
        .map((part) => part[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();
    return (
        <div className="flex min-w-0 items-center gap-2.5 rounded-xl bg-white/[0.03] p-2 ring-1 ring-white/[0.06] transition-colors hover:bg-white/[0.06]">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-muted to-primary/20 ring-1 ring-white/10">
                {member.profile_path && !failed ? (
                    <img
                        src={member.profile_path}
                        alt=""
                        loading="lazy"
                        onError={() => setFailed(true)}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <span className="text-xs font-semibold text-foreground/70">{initials}</span>
                )}
            </span>
            <span className="min-w-0">
                <span className="block truncate text-xs font-semibold" title={member.name}>
                    {member.name}
                </span>
                {member.character && (
                    <span className="block truncate text-[11px] text-muted-foreground" title={member.character}>
                        {member.character}
                    </span>
                )}
            </span>
        </div>
    );
}

/** Fiche TMDB indisponible alors que l'aperçu est affiché. */
function DetailError({ error, retrying, onRetry }: { error: unknown; retrying: boolean; onRetry: () => void }) {
    const message = error instanceof Error ? error.message : "";
    // Seule erreur « attendue » : la clé TMDB n'est pas configurée (HTTP 400).
    const noKey = /TMDB_API_KEY/i.test(message);
    return (
        <div className="mt-5 flex items-start gap-3 rounded-xl bg-warning/10 p-3 text-xs ring-1 ring-warning/25">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <div className="min-w-0 flex-1">
                <p className="font-medium text-warning">Détails TMDB indisponibles</p>
                <p className="mt-0.5 break-words text-muted-foreground">
                    {noKey
                        ? "Ajoute TMDB_API_KEY au fichier .env du backend pour voir le casting et la bande-annonce."
                        : message || "Le service TMDB n'a pas répondu."}
                </p>
            </div>
            {!noKey && (
                <Button variant="ghost" size="sm" onClick={onRetry} disabled={retrying} className="shrink-0">
                    {retrying ? <Loader2 className="animate-spin" /> : <RotateCcw />} Réessayer
                </Button>
            )}
        </div>
    );
}

/** Squelette complet (ouverture sans aperçu). */
function FullSkeleton() {
    return (
        <div aria-busy="true">
            <DialogTitle className="sr-only">Chargement de la fiche</DialogTitle>
            <DialogDescription className="sr-only">La fiche TMDB est en cours de chargement.</DialogDescription>
            <Shimmer className="h-40 w-full rounded-none sm:h-64" />
            <div className="relative -mt-20 flex gap-4 px-5 pb-6 sm:-mt-28 sm:gap-6 sm:px-7">
                <Shimmer className="aspect-[2/3] w-24 shrink-0 rounded-2xl ring-1 ring-white/10 sm:w-36" />
                <div className="flex-1 space-y-3 pt-[4.5rem] sm:pt-24">
                    <Shimmer className="h-4 w-32 rounded-full" />
                    <Shimmer className="h-7 w-3/4 rounded-lg" />
                    <Shimmer className="h-3 w-40 rounded-md" />
                </div>
            </div>
            <div className="space-y-2 px-5 pb-7 sm:px-7">
                <Shimmer className="h-3.5 w-full rounded-md" />
                <Shimmer className="h-3.5 w-11/12 rounded-md" />
                <Shimmer className="h-3.5 w-2/3 rounded-md" />
            </div>
        </div>
    );
}
