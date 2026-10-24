"use client";

/**
 * En-tête « cinéma » de la fiche média.
 * ----------------------------------------------------------------
 * - `HeroBackdrop` : l'image de fond (fanart) plein cadre, placée DERRIÈRE
 *   la barre du haut, avec parallaxe au défilement (l'image descend moins vite
 *   que la page) et fondu vers le noir en bas, comme l'app TV d'Apple.
 * - `MediaHero` : le vrai boîtier Blu-ray / 4K / DVD du titre (l'affiche en
 *   jaquette) qui s'ouvre pour recevoir son disque (ordinateur) ; grand
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
    Eye,
    EyeOff,
    Film,
    Globe,
    HardDrive,
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
            className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[78vw] max-h-[560px] overflow-hidden sm:h-[600px] sm:max-h-none lg:h-[700px]"
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
                    // Pas d'image : simple dégradé gris neutre.
                    <div className="h-full w-full bg-gradient-to-b from-[hsl(240_3%_16%)] to-background" />
                )}
            </motion.div>

            {/* Fondu vers le noir : en bas (mobile et ordinateur) et à gauche
                (ordinateur, pour la lisibilité du texte posé sur l'image). */}
            <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
            <div className="absolute inset-0 hidden bg-gradient-to-r from-background/90 via-background/40 to-transparent md:block" />
            <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-black/50 to-transparent" />
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Boîtier
   ════════════════════════════════════════════════════════════════ */

/**
 * Grand boîtier (tablette / ordinateur) : le vrai boîtier du titre (format
 * d'après le fichier) qui s'ouvre et reçoit son disque, posé avec une ombre
 * portée. Le disque : rond imprimé (dossier du film ou fanart.tv), sinon
 * dessiné à partir de l'affiche.
 */
function HeroCase({ media, techFile }: { media: MediaDetail; techFile: FileInfo | null }) {
    const poster = media.images?.poster ?? null;
    const format =
        media.type === "movie"
            ? caseFormat(media.file?.resolution, !!media.has_file)
            : caseFormat(techFile?.resolution, !!techFile);
    return (
        <div className="relative isolate drop-shadow-[0_24px_40px_rgb(0_0_0/0.7)]">
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
    success: { dot: "online", badge: "border-success/30 bg-success/10 text-success" },
    warning: { dot: "warning", badge: "border-warning/30 bg-warning/10 text-warning" },
    primary: { dot: "primary", badge: "border-primary/30 bg-primary/10 text-primary" },
    muted: { dot: "unknown", badge: "border-white/10 bg-white/[0.04] text-muted-foreground" },
    danger: { dot: "error", badge: "border-destructive/30 bg-destructive/10 text-destructive" },
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
        <div className="flex items-center gap-1.5">
            <Star className="h-3.5 w-3.5 fill-current text-foreground/80" aria-hidden />
            <span className="text-[15px] font-semibold">
                <AnimatedNumber value={value} decimals={percent ? 0 : 1} suffix={percent ? " %" : ""} />
            </span>
            {!percent && <span className="-ml-1 text-[10px] text-muted-foreground">/10</span>}
            <span className="text-[13px] text-muted-foreground">{label}</span>
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
            <p ref={ref} className={cn("text-[15px] leading-relaxed text-foreground/85", !expanded && "line-clamp-4")}>
                {text}
            </p>
            {(clamped || expanded) && (
                <button
                    type="button"
                    onClick={() => setExpanded((v) => !v)}
                    aria-expanded={expanded}
                    className="mt-1 inline-flex items-center gap-1 text-[14px] font-medium text-primary"
                >
                    {expanded ? "Réduire" : "Lire la suite"}
                    <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} aria-hidden />
                </button>
            )}
        </div>
    );
}

/** Classes du grand titre texte (aussi utilisé en repli du ClearLogo). */
const TITLE_CLASS = "text-balance pb-1 text-[30px] font-bold leading-[1.05] tracking-tight sm:text-4xl lg:text-5xl";

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
            <span className="flex h-16 justify-center sm:h-20 md:justify-start lg:h-28" aria-hidden>
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
                    className="h-full w-auto max-w-full object-contain object-bottom md:object-left-bottom"
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

    // Ligne d'infos unique, façon app TV : « 2024 · 2 h 46 · 3 saisons · Science-fiction, Aventure »
    const metaParts = [
        media.year ? String(media.year) : null,
        media.runtime ? `${formatDuration(media.runtime * 60)}${isMovie ? "" : " / ép."}` : null,
        !isMovie && regularSeasons > 0 ? `${regularSeasons} saison${regularSeasons > 1 ? "s" : ""}` : null,
        genres.length ? genres.slice(0, 3).map(translateGenre).join(", ") : null,
    ].filter(Boolean);

    return (
        <motion.section
            variants={stagger(0.05, 0.06)}
            initial="hidden"
            animate="show"
            aria-label={`Présentation de ${media.title}`}
            // Mobile : le texte commence en bas de l'image de fond (≈ 16:9)
            className="relative grid gap-6 pt-[44vw] sm:pt-48 md:grid-cols-[220px_minmax(0,1fr)] md:gap-8 md:pt-20 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-10 lg:pt-24"
        >
            {/* Boîtier animé (tablette / ordinateur) */}
            <motion.div variants={scaleIn} className="hidden self-start md:block">
                <HeroCase media={media} techFile={techFile} />
            </motion.div>

            <div className="min-w-0 space-y-4">
                {/* Titre (ou logo-titre), centré sur mobile comme l'app TV */}
                <motion.div variants={fadeUp} className="space-y-1.5 text-center md:text-left">
                    <p className="flex items-center justify-center gap-1.5 text-[13px] font-medium text-foreground/70 md:justify-start">
                        {isMovie ? <Film className="h-3.5 w-3.5" aria-hidden /> : <Tv className="h-3.5 w-3.5" aria-hidden />}
                        {isMovie ? "Film" : "Série"}
                    </p>
                    <HeroTitle key={media.id} media={media} />
                    {media.original_title && media.original_title !== media.title && (
                        <p className="text-[14px] italic text-muted-foreground">{media.original_title}</p>
                    )}
                    {metaParts.length > 0 && (
                        <p className="flex flex-wrap items-center justify-center gap-x-1.5 text-[14px] text-foreground/75 md:justify-start">
                            {metaParts.join(" · ")}
                            {media.certification && (
                                <span className="ml-1 rounded-[4px] border border-white/30 px-1 text-[11px] font-semibold leading-4 text-foreground/80">
                                    {media.certification}
                                </span>
                            )}
                        </p>
                    )}
                </motion.div>

                {/* Studio / chaîne + badges techniques du fichier principal */}
                {(studioName || hasTech) && (
                    <motion.div
                        variants={fadeUp}
                        className="flex flex-wrap items-center justify-center gap-1.5 md:justify-start"
                        title={!isMovie && hasTech ? "Badges techniques : qualité la plus fréquente parmi les épisodes" : undefined}
                    >
                        <StudioNetworkLogo name={studioName} kind={isMovie ? "studio" : "network"} variant="hero" />
                        {/* `contents` : les pastilles rejoignent la même rangée que le studio. */}
                        <MediaTechBadges specs={techFile} variant="hero" className="contents" />
                    </motion.div>
                )}

                {/* Actions (Sur la TV, recherche…) */}
                {actions && <motion.div variants={fadeUp}>{actions}</motion.div>}

                {/* Synopsis */}
                {media.overview && (
                    <motion.div variants={fadeUp}>
                        <Overview text={media.overview} />
                    </motion.div>
                )}

                {/* Notes + complétude (série) */}
                {(hasRatings || (stats && stats.total > 0)) && (
                    <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-x-5 gap-y-2">
                        {isMovie ? (
                            <>
                                <RatingPill label="IMDb" value={ratings.imdb} />
                                {/* TMDB seulement sans IMDb (la plus fiable) : même règle que les affiches */}
                                <RatingPill label="TMDB" value={ratings.imdb ? null : ratings.tmdb} />
                                <RatingPill label="Rotten Tomatoes" value={ratings.rotten_tomatoes} percent />
                                <RatingPill label="Metacritic" value={ratings.metacritic} percent />
                            </>
                        ) : (
                            <RatingPill label="Note" value={ratings.value} />
                        )}
                        {stats && stats.total > 0 && (
                            <div className="flex items-center gap-2.5">
                                <RingGauge value={stats.pct} size={32} stroke={4} tone={stats.missing === 0 ? "emerald" : "amber"} />
                                <div className="leading-tight">
                                    <p className="text-[14px] font-semibold tabular-nums">
                                        <AnimatedNumber value={stats.have} />
                                        <span className="text-muted-foreground">/{stats.aired}</span>
                                        <span className="ml-1 text-[13px] font-normal text-muted-foreground">épisodes</span>
                                    </p>
                                    <p className="text-[12px] text-muted-foreground">
                                        {stats.missing > 0 ? (
                                            <span className="text-warning">{stats.missing} manquant{stats.missing > 1 ? "s" : ""}</span>
                                        ) : (
                                            <span className="text-success">Complète</span>
                                        )}
                                        {stats.upcoming > 0 && ` · ${stats.upcoming} à venir`}
                                    </p>
                                </div>
                            </div>
                        )}
                    </motion.div>
                )}

                {/* État : statut, surveillance, taille, fichier manquant */}
                <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-muted-foreground">
                    {isMovie && !media.has_file && <span className="font-medium text-warning">Fichier manquant</span>}
                    {status && statusStyle && (
                        <span className="inline-flex items-center gap-1.5">
                            <StatusDot tone={statusStyle.dot} size="sm" />
                            {status.label}
                        </span>
                    )}
                    <span className="inline-flex items-center gap-1.5">
                        {media.monitored ? <Eye className="h-3.5 w-3.5" aria-hidden /> : <EyeOff className="h-3.5 w-3.5" aria-hidden />}
                        {media.monitored ? "Surveillé" : "Non surveillé"}
                    </span>
                    {media.size_on_disk > 0 && (
                        <span className="inline-flex items-center gap-1.5">
                            <HardDrive className="h-3.5 w-3.5" aria-hidden /> {formatBytes(media.size_on_disk)}
                        </span>
                    )}
                </motion.div>

                {/* Liens externes */}
                {links.length > 0 && (
                    <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-1.5">
                        {links.map((l) => (
                            <ExternalChip key={l.label} {...l} />
                        ))}
                    </motion.div>
                )}
            </div>
        </motion.section>
    );
}
