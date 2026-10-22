"use client";

/**
 * En-tête « cinéma » de la fiche média.
 * ----------------------------------------------------------------
 * - `HeroBackdrop` : l'image de fond (fanart) plein cadre, placée DERRIÈRE
 *   la barre du haut, avec parallaxe au défilement (l'image descend moins vite
 *   que la page), vignettage vers la couleur de fond et grain argentique.
 * - `MediaHero` : le vrai boîtier Blu-ray / 4K / DVD du titre (l'affiche en
 *   jaquette) qui s'ouvre pour recevoir son disque, avec halo coloré ; grand
 *   titre (ou ClearLogo, le logo-titre officiel, quand il est connu),
 *   studio / chaîne et badges techniques du fichier (4K, HDR, Atmos…),
 *   méta (année, durée, certification, statut traduit), genres, notes
 *   animées, synopsis repliable, barre d'actions et liens externes.
 *
 * Performance : la parallaxe n'anime que `transform` et `opacity` (GPU),
 * et est neutralisée si l'utilisateur a demandé « réduire les animations ».
 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import {
    Calendar,
    Clock,
    Eye,
    EyeOff,
    Film,
    Globe,
    HardDrive,
    Layers,
    Star,
    Tv,
    ExternalLink,
    ChevronDown,
} from "lucide-react";
import type { FileInfo, MediaDetail, SeasonDetail } from "@/hooks/use-media";
import { MediaTechBadges, parseTechSpecs } from "@/components/media/media-tech-badges";
import { StudioNetworkLogo } from "@/components/media/studio-network-logo";
import { OpeningCase, caseFormat } from "@/components/media/disc-art";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { RingGauge } from "@/components/fx/ring-gauge";
import { StatusDot } from "@/components/fx/status-dot";
import { Badge } from "@/components/ui/badge";
import { formatBytes, formatDuration } from "@/lib/format";
import { EASE_OUT, fadeUp, scaleIn, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { hdrLabel, resolutionLabel, seriesStats, statusInfo, type StatusTone } from "./labels";
import { translateGenre } from "@/lib/genres";

/* ════════════════════════════════════════════════════════════════
   Fond plein cadre avec parallaxe
   ════════════════════════════════════════════════════════════════ */

export function HeroBackdrop({ src }: { src?: string | null }) {
    const reduce = useReducedMotion();
    const { scrollY } = useScroll();
    // L'image descend à ~35 % de la vitesse du scroll et s'estompe : effet de profondeur.
    const y = useTransform(scrollY, [0, 700], [0, reduce ? 0 : 240]);
    const opacity = useTransform(scrollY, [0, 650], [1, 0.25]);
    const [loaded, setLoaded] = useState(false);
    const imgRef = useRef<HTMLImageElement>(null);

    // Image déjà en cache navigateur : onLoad peut avoir été déclenché avant
    // l'hydratation → on vérifie `complete` au montage.
    useEffect(() => {
        setLoaded(false);
        const img = imgRef.current;
        if (img?.complete && img.naturalWidth > 0) setLoaded(true);
    }, [src]);

    return (
        <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[560px] overflow-hidden sm:h-[640px] lg:h-[720px]"
        >
            <motion.div style={{ y, opacity }} className="absolute inset-0 will-change-transform">
                {src ? (
                    <motion.img
                        ref={imgRef}
                        src={src}
                        alt=""
                        onLoad={() => setLoaded(true)}
                        initial={false}
                        // Entrée « Ken Burns » : léger dézoom + fondu une fois l'image chargée.
                        animate={loaded ? { opacity: 1, scale: 1.04 } : { opacity: 0, scale: 1.14 }}
                        transition={{ duration: 1.8, ease: EASE_OUT }}
                        className="h-full w-full object-cover object-[center_25%]"
                    />
                ) : (
                    // Pas de fanart : nappe de lumière de marque à la place.
                    <div
                        className="h-full w-full"
                        style={{
                            background:
                                "radial-gradient(ellipse 70% 60% at 30% 20%, hsl(var(--primary) / 0.28), transparent 70%), radial-gradient(ellipse 60% 50% at 80% 10%, hsl(var(--brand) / 0.18), transparent 70%)",
                        }}
                    />
                )}
            </motion.div>

            {/* Vignettage : bas → fond de page, gauche → lisibilité du texte, coins assombris */}
            <div className="absolute inset-0 bg-gradient-to-t from-background via-background/70 to-background/5" />
            <div className="absolute inset-0 bg-gradient-to-r from-background/90 via-background/45 to-transparent" />
            <div
                className="absolute inset-0"
                style={{ background: "radial-gradient(ellipse 120% 90% at 60% 0%, transparent 45%, hsl(var(--background) / 0.85) 100%)" }}
            />
            {/* Grain argentique très léger (évite l'aplat « numérique ») */}
            <div className="absolute inset-0 bg-noise opacity-[0.08] mix-blend-overlay" />
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-background to-transparent" />
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Affiche
   ════════════════════════════════════════════════════════════════ */

function PosterImage({
    src,
    title,
    isMovie,
    className,
    iconClassName,
}: {
    src: string | null;
    title: string;
    isMovie: boolean;
    className?: string;
    iconClassName?: string;
}) {
    const [loaded, setLoaded] = useState(false);
    const [failed, setFailed] = useState(false);
    const Icon = isMovie ? Film : Tv;
    return (
        <div className={cn("relative aspect-[2/3] overflow-hidden bg-muted/40", className)}>
            {src && !failed ? (
                <img
                    src={src}
                    alt={`Affiche de ${title}`}
                    onLoad={() => setLoaded(true)}
                    onError={() => setFailed(true)}
                    className={cn(
                        "h-full w-full object-cover transition-all duration-700 ease-smooth",
                        loaded ? "opacity-100 blur-0" : "opacity-0 blur-md",
                    )}
                />
            ) : (
                <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/60 via-muted/30 to-primary/15">
                    <Icon className={cn("h-14 w-14 text-muted-foreground/30", iconClassName)} strokeWidth={1.4} />
                </div>
            )}
            {src && !loaded && !failed && <div className="shimmer absolute inset-0" />}
        </div>
    );
}

/**
 * Grand boîtier desktop : le vrai boîtier du titre (format d'après le fichier)
 * qui s'ouvre et reçoit son disque, + halo = copie floutée de l'affiche
 * (couleurs du film). Le disque : rond imprimé (dossier du film ou
 * fanart.tv), sinon dessiné à partir de l'affiche.
 */
function HeroCase({ media, techFile }: { media: MediaDetail; techFile: FileInfo | null }) {
    const poster = media.images?.poster ?? null;
    const format =
        media.type === "movie"
            ? caseFormat(media.file?.resolution, !!media.has_file)
            : caseFormat(techFile?.resolution, !!techFile);
    return (
        <div className="relative isolate">
            {poster ? (
                // Halo « respirant » : on anime seulement l'opacité (la classe
                // animate-pulse-glow écraserait le `filter: blur` du halo).
                <motion.img
                    aria-hidden
                    src={poster}
                    alt=""
                    initial={{ opacity: 0 }}
                    animate={{ opacity: [0.45, 0.7, 0.45] }}
                    transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute inset-0 -z-10 h-full w-full scale-105 rounded-3xl object-cover blur-3xl saturate-150"
                />
            ) : (
                <div aria-hidden className="absolute inset-0 -z-10 rounded-3xl bg-primary/30 blur-3xl" />
            )}
            <OpeningCase
                poster={poster}
                discart={media.images?.discart}
                format={format}
                title={media.title}
            />
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Petites briques du hero
   ════════════════════════════════════════════════════════════════ */

const STATUS_TONE_STYLE: Record<StatusTone, { dot: "online" | "warning" | "primary" | "unknown" | "error"; badge: string }> = {
    success: { dot: "online", badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" },
    warning: { dot: "warning", badge: "border-amber-500/30 bg-amber-500/10 text-amber-300" },
    primary: { dot: "primary", badge: "border-primary/30 bg-primary/10 text-primary" },
    muted: { dot: "unknown", badge: "border-white/10 bg-white/[0.04] text-muted-foreground" },
    danger: { dot: "error", badge: "border-red-500/30 bg-red-500/10 text-red-300" },
};

/** Note avec étoile et compteur animé (IMDb 7,8 /10, RT 92 %…). */
function RatingPill({
    label,
    value,
    percent = false,
}: {
    label: string;
    value: number | null | undefined;
    /** Valeur exprimée en % (Rotten Tomatoes, Metacritic) au lieu de /10. */
    percent?: boolean;
}) {
    if (!value) return null;
    return (
        <div className="glass flex items-center gap-2 rounded-xl px-3 py-1.5">
            <Star className="h-4 w-4 fill-amber-400 text-amber-400 drop-" aria-hidden />
            <span className="text-sm font-bold">
                <AnimatedNumber value={value} decimals={percent ? 0 : 1} suffix={percent ? " %" : ""} />
            </span>
            {!percent && <span className="-ml-1 text-[10px] text-muted-foreground">/10</span>}
            <span className="text-xs font-medium text-muted-foreground">{label}</span>
        </div>
    );
}

/** Lien externe compact (IMDb, TMDb, TVDB, site officiel). */
function ExternalChip({ href, label, icon: Icon = ExternalLink }: { href: string; label: string; icon?: typeof ExternalLink }) {
    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Ouvrir sur ${label} (nouvel onglet)`}
            className="chip hover:text-primary"
        >
            <Icon className="h-3 w-3" aria-hidden />
            {label}
        </a>
    );
}

/**
 * Synopsis replié à 4 lignes avec « Lire la suite ».
 * La troncature est MESURÉE (et non devinée au nombre de caractères) : un
 * texte moyen peut tenir sur desktop mais être coupé sur mobile.
 */
function Overview({ text }: { text: string }) {
    const ref = useRef<HTMLParagraphElement>(null);
    const [expanded, setExpanded] = useState(false);
    const [clamped, setClamped] = useState(false);

    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        const check = () => setClamped(el.scrollHeight > el.clientHeight + 1);
        check();
        const ro = new ResizeObserver(check);
        ro.observe(el);
        return () => ro.disconnect();
    }, [text]);

    return (
        <div className="max-w-3xl">
            <p ref={ref} className={cn("text-sm leading-relaxed text-foreground/80 md:text-[15px]", !expanded && "line-clamp-4")}>
                {text}
            </p>
            {(clamped || expanded) && (
                <button
                    type="button"
                    onClick={() => setExpanded((v) => !v)}
                    aria-expanded={expanded}
                    className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                    {expanded ? "Réduire" : "Lire la suite"}
                    <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} aria-hidden />
                </button>
            )}
        </div>
    );
}

/** Classes du grand titre texte (aussi utilisé en repli du ClearLogo). */
const TITLE_CLASS =
    "text-balance bg-gradient-to-b from-white via-white to-white/65 bg-clip-text pb-1 text-3xl font-bold leading-[1.05] tracking-tight text-transparent sm:text-4xl lg:text-5xl xl:text-6xl";

/**
 * Titre du média : le ClearLogo (logo-titre transparent) s'il existe, sinon
 * le titre en texte.
 * - Accessibilité : le <h1> garde le vrai titre en texte masqué (sr-only),
 *   l'image est décorative (alt vide) → lu une seule fois.
 * - Hauteur réservée pendant le chargement : pas de saut de mise en page.
 * - Image introuvable / bloquée (onError) : repli immédiat sur le texte.
 */
function HeroTitle({ media }: { media: MediaDetail }) {
    const logo = media.images?.clearlogo || media.images?.logo || null;
    const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
    const imgRef = useRef<HTMLImageElement>(null);

    // Nouvelle image : on repart de zéro. Si elle est déjà en cache, onLoad a
    // pu partir avant l'hydratation → on vérifie `complete` nous-mêmes.
    useEffect(() => {
        setState("loading");
        const img = imgRef.current;
        if (img?.complete) setState(img.naturalWidth > 0 ? "ready" : "failed");
    }, [logo]);

    if (!logo || state === "failed") return <h1 className={TITLE_CLASS}>{media.title}</h1>;

    return (
        <h1 className="pb-1">
            <span className="sr-only">{media.title}</span>
            <span className="block h-16 sm:h-20 lg:h-28" aria-hidden>
                <motion.img
                    ref={imgRef}
                    src={logo}
                    alt=""
                    onLoad={() => setState("ready")}
                    onError={() => setState("failed")}
                    initial={false}
                    animate={state === "ready" ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 10, scale: 0.97 }}
                    transition={{ duration: 0.8, ease: EASE_OUT }}
                    // object-contain + ancrage en bas à gauche : un logo très large
                    // rétrécit dans la boîte au lieu de déborder.
                    className="h-full w-auto max-w-full object-contain object-left-bottom"
                />
            </span>
        </h1>
    );
}

/**
 * Série : fichier « représentatif » pour les badges du hero = la signature
 * technique (résolution + HDR + audio) la plus fréquente parmi les épisodes
 * présents. Plus juste que le 1er épisode, souvent d'une autre release.
 */
function dominantEpisodeFile(seasons: SeasonDetail[] | undefined): FileInfo | null {
    const groups = new Map<string, { file: FileInfo; count: number }>();
    for (const season of seasons ?? []) {
        for (const ep of season.episodes) {
            const f = ep.file;
            if (!f) continue;
            const key = [resolutionLabel(f.resolution), hdrLabel(f) ?? "", f.audio_codec, f.audio_channels].join("|");
            const g = groups.get(key);
            if (g) g.count++;
            else groups.set(key, { file: f, count: 1 });
        }
    }
    const best = Array.from(groups.values()).reduce<{ file: FileInfo; count: number } | null>(
        (acc, g) => (!acc || g.count > acc.count ? g : acc),
        null,
    );
    return best?.file ?? null;
}

/* ════════════════════════════════════════════════════════════════
   Hero complet
   ════════════════════════════════════════════════════════════════ */

export function MediaHero({ media, actions }: { media: MediaDetail; actions?: ReactNode }) {
    const isMovie = media.type === "movie";
    const status = statusInfo(media.status, media.type);
    const statusStyle = status ? STATUS_TONE_STYLE[status.tone] : null;
    const stats = !isMovie ? seriesStats(media.seasons) : null;
    const regularSeasons = (media.seasons ?? []).filter((s) => s.season_number > 0).length;
    // Défensif : un payload partiel (service *arr dégradé) ne doit pas faire planter la fiche.
    const genres = media.genres ?? [];

    // Fichier principal pour les badges techniques : celui du film, ou
    // l'épisode « type » d'une série (calcul sur toutes les saisons → mémoïsé).
    const techFile = useMemo(
        () => (isMovie ? media.file ?? null : dominantEpisodeFile(media.seasons)),
        [isMovie, media.file, media.seasons],
    );
    const hasTech = parseTechSpecs(techFile).length > 0;
    const studioName = isMovie ? media.studio : media.network;

    const ratings = media.ratings ?? {};
    const hasRatings = isMovie
        ? !!(ratings.imdb || ratings.tmdb || ratings.rotten_tomatoes || ratings.metacritic)
        : !!ratings.value;

    const links: { href: string; label: string; icon?: typeof ExternalLink }[] = [];
    if (media.imdb_id) links.push({ href: `https://www.imdb.com/title/${media.imdb_id}`, label: "IMDb" });
    // Les séries n'ont pas d'id TMDb dans Sonarr mais un id TVDB → lien TVDB.
    if (isMovie && media.tmdb_id) links.push({ href: `https://www.themoviedb.org/movie/${media.tmdb_id}`, label: "TMDb" });
    if (!isMovie && media.tvdb_id) links.push({ href: `https://www.thetvdb.com/dereferrer/series/${media.tvdb_id}`, label: "TVDB" });
    if (media.website) links.push({ href: media.website, label: "Site officiel", icon: Globe });

    return (
        <motion.section
            variants={stagger(0.05, 0.07)}
            initial="hidden"
            animate="show"
            aria-label={`Présentation de ${media.title}`}
            className="relative grid gap-6 pt-4 md:grid-cols-[220px_minmax(0,1fr)] md:gap-8 md:pt-14 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-10 lg:pt-20"
        >
            {/* Affiche (desktop / tablette) */}
            <motion.div variants={scaleIn} className="hidden self-start md:block">
                <HeroCase media={media} techFile={techFile} />
            </motion.div>

            <div className="min-w-0 space-y-5">
                {/* Titre (+ mini-affiche sur mobile) */}
                <motion.div variants={fadeUp} className="flex items-end gap-4">
                    <div className="w-24 shrink-0 overflow-hidden rounded-xl shadow-[0_16px_40px_-12px_rgb(0_0_0/0.9)] ring-1 ring-white/10 sm:w-28 md:hidden">
                        <PosterImage src={media.images?.poster ?? null} title={media.title} isMovie={isMovie} iconClassName="h-8 w-8" />
                    </div>
                    <div className="min-w-0 space-y-2">
                        <p className="eyebrow flex items-center gap-1.5 text-foreground/60">
                            {isMovie ? <Film className="h-3 w-3" aria-hidden /> : <Tv className="h-3 w-3" aria-hidden />}
                            {isMovie ? "Film" : "Série"}
                        </p>
                        <HeroTitle key={media.id} media={media} />
                        {media.original_title && media.original_title !== media.title && (
                            <p className="text-sm italic text-muted-foreground">{media.original_title}</p>
                        )}
                    </div>
                </motion.div>

                {/* Studio / chaîne + badges techniques du fichier principal */}
                {(studioName || hasTech) && (
                    <motion.div
                        variants={fadeUp}
                        className="flex flex-wrap items-center gap-1.5"
                        title={!isMovie && hasTech ? "Badges techniques : qualité la plus fréquente parmi les épisodes" : undefined}
                    >
                        <StudioNetworkLogo name={studioName} kind={isMovie ? "studio" : "network"} variant="hero" />
                        {/* `contents` : les pastilles rejoignent la même rangée que le studio. */}
                        <MediaTechBadges specs={techFile} variant="hero" className="contents" />
                    </motion.div>
                )}

                {/* Méta : année · durée · certification · statut · surveillance · taille */}
                <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
                    {!!media.year && (
                        <span className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5" aria-hidden /> {media.year}
                        </span>
                    )}
                    {!!media.runtime && (
                        <span className="flex items-center gap-1.5">
                            <Clock className="h-3.5 w-3.5" aria-hidden />
                            {formatDuration(media.runtime * 60)}
                            {!isMovie && <span className="text-muted-foreground/70">/ épisode</span>}
                        </span>
                    )}
                    {!isMovie && regularSeasons > 0 && (
                        <span className="flex items-center gap-1.5">
                            <Layers className="h-3.5 w-3.5" aria-hidden />
                            {regularSeasons} saison{regularSeasons > 1 ? "s" : ""}
                        </span>
                    )}
                    {media.certification && (
                        <span className="rounded-md border border-white/20 px-1.5 py-px text-[11px] font-semibold text-foreground/80">
                            {media.certification}
                        </span>
                    )}
                    {status && statusStyle && (
                        <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", statusStyle.badge)}>
                            <StatusDot tone={statusStyle.dot} size="sm" pulse={status.tone === "success" && !isMovie} />
                            {status.label}
                        </span>
                    )}
                    <span
                        className={cn(
                            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
                            media.monitored
                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                                : "border-white/10 bg-white/[0.04] text-muted-foreground",
                        )}
                    >
                        {media.monitored ? <Eye className="h-3 w-3" aria-hidden /> : <EyeOff className="h-3 w-3" aria-hidden />}
                        {media.monitored ? "Surveillé" : "Non surveillé"}
                    </span>
                    {media.size_on_disk > 0 && (
                        <span className="flex items-center gap-1.5">
                            <HardDrive className="h-3.5 w-3.5" aria-hidden /> {formatBytes(media.size_on_disk)}
                        </span>
                    )}
                </motion.div>

                {/* Genres (+ alerte fichier manquant) */}
                {(genres.length > 0 || (isMovie && !media.has_file)) && (
                    <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-1.5">
                        {isMovie && !media.has_file && (
                            <Badge variant="warning" className="rounded-full px-2.5">
                                Fichier manquant
                            </Badge>
                        )}
                        {genres.map((g) => (
                            <span key={g} className="chip">
                                {translateGenre(g)}
                            </span>
                        ))}
                    </motion.div>
                )}

                {/* Notes + complétude (série) */}
                {(hasRatings || (stats && stats.total > 0)) && (
                    <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-2">
                        {isMovie ? (
                            <>
                                <RatingPill label="IMDb" value={ratings.imdb} />
                                <RatingPill label="TMDb" value={ratings.tmdb} />
                                <RatingPill label="Rotten Tomatoes" value={ratings.rotten_tomatoes} percent />
                                <RatingPill label="Metacritic" value={ratings.metacritic} percent />
                            </>
                        ) : (
                            <RatingPill label="Note" value={ratings.value} />
                        )}
                        {stats && stats.total > 0 && (
                            <div className="glass flex items-center gap-3 rounded-xl py-1 pl-1.5 pr-3">
                                <RingGauge value={stats.pct} size={36} stroke={4} tone={stats.missing === 0 ? "emerald" : "amber"}>
                                    <span className="text-[9px] font-bold tabular-nums">{stats.pct}%</span>
                                </RingGauge>
                                <div className="leading-tight">
                                    <p className="text-sm font-bold tabular-nums">
                                        <AnimatedNumber value={stats.have} />
                                        <span className="text-muted-foreground">/{stats.aired}</span>
                                        <span className="ml-1 text-xs font-medium text-muted-foreground">épisodes</span>
                                    </p>
                                    <p className="text-[11px] text-muted-foreground">
                                        {stats.missing > 0 ? (
                                            <span className="text-amber-400">{stats.missing} manquant{stats.missing > 1 ? "s" : ""}</span>
                                        ) : (
                                            <span className="text-emerald-400">Complète</span>
                                        )}
                                        {stats.upcoming > 0 && ` · ${stats.upcoming} à venir`}
                                    </p>
                                </div>
                            </div>
                        )}
                    </motion.div>
                )}

                {/* Synopsis */}
                {media.overview && (
                    <motion.div variants={fadeUp}>
                        <Overview text={media.overview} />
                    </motion.div>
                )}

                {/* Actions */}
                {actions && <motion.div variants={fadeUp}>{actions}</motion.div>}

                {/* Liens externes */}
                {links.length > 0 && (
                    <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-1.5">
                        <span className="eyebrow mr-1">Voir sur</span>
                        {links.map((l) => (
                            <ExternalChip key={l.label} {...l} />
                        ))}
                    </motion.div>
                )}
            </div>
        </motion.section>
    );
}
