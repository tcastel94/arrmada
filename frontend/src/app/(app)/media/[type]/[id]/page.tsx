"use client";

import { useParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    ArrowLeft,
    Calendar,
    Clock,
    Download,
    ExternalLink,
    Film,
    FolderOpen,
    HardDrive,
    Info,
    Languages,
    Monitor,
    Play,
    Star,
    Subtitles,
    Tv,
    Users,
    Eye,
    CheckCircle2,
    XCircle,
    Volume2,
    Target,
    Trash2,
} from "lucide-react";
import {
    useMediaDetail,
    type MediaDetail,
    type FileInfo,
    type SeasonDetail,
    type EpisodeDetail,
    type CastMember,
} from "@/hooks/use-media";
import { useProfileOverrides, useAvailableProfiles, useCreateOverride, useDeleteOverride } from "@/hooks/use-profile-overrides";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatRuntime(minutes: number | null): string {
    if (!minutes) return "—";
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

function RatingBadge({ label, value }: { label: string; value: number | null | undefined }) {
    if (!value) return null;
    return (
        <div className="flex items-center gap-1.5 bg-card/50 rounded-lg px-3 py-2 border border-border/50">
            <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
            <span className="text-sm font-medium">{typeof value === "number" ? value.toFixed(1) : value}</span>
            <span className="text-xs text-muted-foreground">{label}</span>
        </div>
    );
}

function FileInfoCard({ file }: { file: FileInfo }) {
    return (
        <Card className="bg-card/50 border-border/50">
            <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate flex-1 mr-2">{file.relative_path}</span>
                    <Badge variant="outline" className="shrink-0">{file.quality}</Badge>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3  text-sm">
                    <div className="space-y-0.5">
                        <p className="text-xs text-muted-foreground">Codec Vidéo</p>
                        <p className="font-medium">{file.video_codec || "—"}</p>
                    </div>
                    <div className="space-y-0.5">
                        <p className="text-xs text-muted-foreground">HDR</p>
                        <p className="font-medium">{file.video_dynamic_range || "SDR"}</p>
                    </div>
                    <div className="space-y-0.5">
                        <p className="text-xs text-muted-foreground">Audio</p>
                        <p className="font-medium">
                            {file.audio_codec || "—"}
                            {file.audio_channels ? ` ${file.audio_channels}ch` : ""}
                        </p>
                    </div>
                    <div className="space-y-0.5">
                        <p className="text-xs text-muted-foreground">Taille</p>
                        <p className="font-medium">{formatBytes(file.size_bytes)}</p>
                    </div>
                </div>
                {(file.audio_languages || file.subtitle_languages) && (
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="space-y-0.5">
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                                <Volume2 className="h-3 w-3" /> Langues audio
                            </p>
                            <p className="font-medium">{file.audio_languages || "—"}</p>
                        </div>
                        <div className="space-y-0.5">
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                                <Subtitles className="h-3 w-3" /> Sous-titres embarqués
                            </p>
                            <p className="font-medium">{file.subtitle_languages || "—"}</p>
                        </div>
                    </div>
                )}
                {file.release_group && (
                    <p className="text-xs text-muted-foreground">
                        Release: <span className="text-foreground">{file.release_group}</span>
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

function CastSection({ cast, crew }: { cast?: CastMember[]; crew?: CastMember[] }) {
    if ((!cast || cast.length === 0) && (!crew || crew.length === 0)) return null;
    return (
        <div className="space-y-4">
            {cast && cast.length > 0 && (
                <>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Users className="h-5 w-5" /> Casting
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                        {cast.slice(0, 10).map((actor, i) => (
                            <div key={i} className="flex items-center gap-3 bg-card/50 rounded-lg p-2 border border-border/50">
                                {actor.photo ? (
                                    <img
                                        src={actor.photo}
                                        alt={actor.name}
                                        className="w-10 h-10 rounded-full object-cover shrink-0"
                                    />
                                ) : (
                                    <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center shrink-0">
                                        <Users className="h-4 w-4 text-muted-foreground" />
                                    </div>
                                )}
                                <div className="min-w-0">
                                    <p className="text-sm font-medium truncate">{actor.name}</p>
                                    <p className="text-xs text-muted-foreground truncate">{actor.character}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
            {crew && crew.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {crew.map((person, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                            {person.name} ({person.type})
                        </Badge>
                    ))}
                </div>
            )}
        </div>
    );
}

function SeasonSection({ seasons }: { seasons: SeasonDetail[] }) {
    const [openSeason, setOpenSeason] = useState<number | null>(null);

    return (
        <div className="space-y-3">
            {seasons.filter(s => s.season_number > 0).map((season) => (
                <Card key={season.season_number} className="bg-card/50 border-border/50">
                    <button
                        className="w-full text-left"
                        onClick={() =>
                            setOpenSeason(
                                openSeason === season.season_number ? null : season.season_number
                            )
                        }
                    >
                        <CardHeader className="p-4 pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base">
                                    Saison {season.season_number}
                                </CardTitle>
                                <div className="flex items-center gap-2">
                                    <Badge
                                        variant={
                                            season.episodes_have === season.episode_count
                                                ? "default"
                                                : "secondary"
                                        }
                                        className={cn(
                                            "text-xs",
                                            season.episodes_have === season.episode_count
                                                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                                                : ""
                                        )}
                                    >
                                        {season.episodes_have}/{season.episode_count} épisodes
                                    </Badge>
                                </div>
                            </div>
                        </CardHeader>
                    </button>
                    {openSeason === season.season_number && (
                        <CardContent className="px-4 pb-4">
                            <div className="space-y-1">
                                {season.episodes.map((ep) => (
                                    <div
                                        key={ep.id}
                                        className={cn(
                                            "flex items-center gap-3 p-2 rounded-md text-sm",
                                            ep.has_file
                                                ? "bg-emerald-500/5"
                                                : "bg-destructive/5"
                                        )}
                                    >
                                        <span className="w-8 text-center text-muted-foreground font-mono text-xs">
                                            E{String(ep.episode_number).padStart(2, "0")}
                                        </span>
                                        {ep.has_file ? (
                                            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                                        ) : (
                                            <XCircle className="h-4 w-4 text-destructive shrink-0" />
                                        )}
                                        <span className="flex-1 truncate">
                                            {ep.title || "—"}
                                        </span>
                                        {ep.air_date && (
                                            <span className="text-xs text-muted-foreground">
                                                {new Date(ep.air_date).toLocaleDateString("fr-FR")}
                                            </span>
                                        )}
                                        {ep.file && (
                                            <Badge variant="outline" className="text-[10px]">
                                                {ep.file.quality}
                                            </Badge>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    )}
                </Card>
            ))}
        </div>
    );
}

export default function MediaDetailPage() {
    const params = useParams();
    const router = useRouter();
    const type = params.type as "movie" | "series";
    const id = params.id as string;

    const { data: media, isLoading, error } = useMediaDetail(type, id);

    if (isLoading) {
        return (
            <>
                <Header title="Chargement…" />
                <div className="p-6">
                    <div className="animate-pulse space-y-6">
                        <div className="h-[400px] bg-muted rounded-xl" />
                        <div className="h-8 bg-muted rounded w-1/3" />
                        <div className="h-32 bg-muted rounded" />
                    </div>
                </div>
            </>
        );
    }

    if (!media || media.error) {
        return (
            <>
                <Header title="Erreur" />
                <div className="p-6">
                    <p className="text-destructive">
                        {media?.error || "Impossible de charger les détails du média"}
                    </p>
                    <Button variant="outline" className="mt-4" onClick={() => router.back()}>
                        <ArrowLeft className="h-4 w-4 mr-2" /> Retour
                    </Button>
                </div>
            </>
        );
    }

    const isMovie = media.type === "movie";

    return (
        <>
            <Header title={media.title} />

            {/* Hero section with fanart backdrop */}
            <div className="relative">
                {/* Fanart background */}
                <div className="absolute inset-0 h-[450px] overflow-hidden">
                    {media.images?.fanart ? (
                        <img
                            src={media.images.fanart}
                            alt=""
                            className="w-full h-full object-cover opacity-30"
                        />
                    ) : (
                        <div className="w-full h-full bg-gradient-to-br from-primary/10 to-background" />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent" />
                </div>

                {/* Content over fanart */}
                <div className="relative z-10 p-6 pt-4">
                    {/* Back button */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.back()}
                        className="mb-4 -ml-2 text-muted-foreground hover:text-foreground"
                    >
                        <ArrowLeft className="h-4 w-4 mr-2" /> Médiathèque
                    </Button>

                    {/* Main info row */}
                    <div className="flex gap-6">
                        {/* Poster */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="hidden sm:block shrink-0"
                        >
                            <div className="w-[200px] lg:w-[240px] aspect-[2/3] rounded-xl overflow-hidden border-2 border-border shadow-2xl">
                                {media.images?.poster ? (
                                    <img
                                        src={media.images.poster}
                                        alt={media.title}
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full bg-muted flex items-center justify-center">
                                        {isMovie ? (
                                            <Film className="h-16 w-16 text-muted-foreground/30" />
                                        ) : (
                                            <Tv className="h-16 w-16 text-muted-foreground/30" />
                                        )}
                                    </div>
                                )}
                            </div>
                        </motion.div>

                        {/* Info */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 }}
                            className="flex-1 min-w-0 space-y-4"
                        >
                            {/* Title */}
                            <div>
                                <div className="flex items-center gap-3 flex-wrap">
                                    <h1 className="text-3xl lg:text-4xl font-bold tracking-tight">
                                        {media.title}
                                    </h1>
                                    {media.certification && (
                                        <Badge variant="outline" className="text-xs border-muted-foreground/30">
                                            {media.certification}
                                        </Badge>
                                    )}
                                </div>
                                {media.original_title && media.original_title !== media.title && (
                                    <p className="text-muted-foreground mt-1">{media.original_title}</p>
                                )}
                            </div>

                            {/* Meta tags */}
                            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                                {media.year && (
                                    <span className="flex items-center gap-1">
                                        <Calendar className="h-3.5 w-3.5" /> {media.year}
                                    </span>
                                )}
                                {media.runtime && (
                                    <span className="flex items-center gap-1">
                                        <Clock className="h-3.5 w-3.5" /> {formatRuntime(media.runtime)}
                                    </span>
                                )}
                                {isMovie ? (
                                    <Badge variant="secondary" className="text-xs">
                                        <Film className="h-3 w-3 mr-1" /> Film
                                    </Badge>
                                ) : (
                                    <Badge variant="secondary" className="text-xs">
                                        <Tv className="h-3 w-3 mr-1" /> Série
                                    </Badge>
                                )}
                                {!isMovie && media.season_count !== undefined && (
                                    <span>
                                        {media.season_count} saison{media.season_count !== 1 ? "s" : ""}
                                    </span>
                                )}
                                {!isMovie && media.episodes_have !== undefined && media.total_episodes !== undefined && (
                                    <span>
                                        {media.episodes_have}/{media.total_episodes} épisodes
                                    </span>
                                )}
                                <Badge
                                    variant={media.monitored ? "default" : "secondary"}
                                    className={cn(
                                        "text-xs",
                                        media.monitored
                                            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                                            : ""
                                    )}
                                >
                                    {media.monitored ? "Surveillé" : "Non surveillé"}
                                </Badge>
                                <span className="flex items-center gap-1">
                                    <HardDrive className="h-3.5 w-3.5" /> {formatBytes(media.size_on_disk)}
                                </span>
                            </div>

                            {/* Genres */}
                            {media.genres.length > 0 && (
                                <div className="flex flex-wrap gap-2">
                                    {media.genres.map((g) => (
                                        <Badge key={g} variant="outline" className="text-xs">
                                            {g}
                                        </Badge>
                                    ))}
                                </div>
                            )}

                            {/* Ratings */}
                            <div className="flex flex-wrap gap-2">
                                {isMovie && (
                                    <>
                                        <RatingBadge label="TMDb" value={media.ratings?.tmdb} />
                                        <RatingBadge label="IMDb" value={media.ratings?.imdb} />
                                        <RatingBadge label="RT" value={media.ratings?.rotten_tomatoes} />
                                    </>
                                )}
                                {!isMovie && (
                                    <RatingBadge label="Note" value={media.ratings?.value} />
                                )}
                            </div>

                            {/* Overview */}
                            {media.overview && (
                                <p className="text-sm leading-relaxed text-muted-foreground max-w-3xl">
                                    {media.overview}
                                </p>
                            )}

                            {/* Action buttons */}
                            <div className="flex flex-wrap gap-2 pt-2">
                                {media.youtube_trailer_id && (
                                    <Button variant="outline" size="sm" asChild>
                                        <a
                                            href={`https://www.youtube.com/watch?v=${media.youtube_trailer_id}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            <Play className="h-4 w-4 mr-2" /> Bande-annonce
                                        </a>
                                    </Button>
                                )}
                                {media.imdb_id && (
                                    <Button variant="outline" size="sm" asChild>
                                        <a
                                            href={`https://www.imdb.com/title/${media.imdb_id}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            <ExternalLink className="h-4 w-4 mr-2" /> IMDb
                                        </a>
                                    </Button>
                                )}
                                {media.tmdb_id && (
                                    <Button variant="outline" size="sm" asChild>
                                        <a
                                            href={`https://www.themoviedb.org/movie/${media.tmdb_id}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            <ExternalLink className="h-4 w-4 mr-2" /> TMDb
                                        </a>
                                    </Button>
                                )}
                            </div>
                        </motion.div>
                    </div>
                </div>
            </div>

            {/* Tabs section */}
            <div className="p-6 pt-2">
                <Tabs defaultValue={isMovie ? "file" : "seasons"} className="space-y-4">
                    <TabsList>
                        {!isMovie && <TabsTrigger value="seasons">Saisons</TabsTrigger>}
                        <TabsTrigger value="file">
                            {isMovie ? "Fichier" : "Fichiers"}
                        </TabsTrigger>
                        <TabsTrigger value="cast">Casting</TabsTrigger>
                        <TabsTrigger value="quality">Qualité</TabsTrigger>
                        <TabsTrigger value="info">Infos</TabsTrigger>
                    </TabsList>

                    {/* Seasons tab (series only) */}
                    {!isMovie && media.seasons && (
                        <TabsContent value="seasons">
                            <SeasonSection seasons={media.seasons} />
                        </TabsContent>
                    )}

                    {/* File tab */}
                    <TabsContent value="file" className="space-y-4">
                        {isMovie && media.file ? (
                            <FileInfoCard file={media.file} />
                        ) : !isMovie && media.seasons ? (
                            <div className="space-y-4">
                                <p className="text-sm text-muted-foreground">
                                    Les informations fichier sont disponibles dans chaque épisode de l&apos;onglet Saisons.
                                </p>
                                {/* Show a summary of all files */}
                                {media.seasons
                                    .flatMap((s) => s.episodes)
                                    .filter((ep) => ep.file)
                                    .slice(0, 5)
                                    .map((ep) => (
                                        <div key={ep.id} className="space-y-1">
                                            <p className="text-sm font-medium">
                                                S{String(ep.season_number).padStart(2, "0")}E
                                                {String(ep.episode_number).padStart(2, "0")} — {ep.title}
                                            </p>
                                            {ep.file && <FileInfoCard file={ep.file} />}
                                        </div>
                                    ))}
                            </div>
                        ) : (
                            <p className="text-muted-foreground">Aucun fichier disponible</p>
                        )}
                    </TabsContent>

                    {/* Cast tab */}
                    <TabsContent value="cast">
                        <CastSection cast={media.cast} crew={media.crew} />
                    </TabsContent>

                    {/* Quality tab */}
                    <TabsContent value="quality">
                        <QualityTab media={media} />
                    </TabsContent>

                    {/* Info tab */}
                    <TabsContent value="info">
                        <Card className="bg-card/50 border-border/50">
                            <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                <div className="space-y-3">
                                    <div>
                                        <p className="text-xs text-muted-foreground">Statut</p>
                                        <p className="font-medium capitalize">{media.status}</p>
                                    </div>
                                    {isMovie && media.studio && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">Studio</p>
                                            <p className="font-medium">{media.studio}</p>
                                        </div>
                                    )}
                                    {!isMovie && media.network && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">Chaîne</p>
                                            <p className="font-medium">{media.network}</p>
                                        </div>
                                    )}
                                    {media.added && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">Ajouté le</p>
                                            <p className="font-medium">
                                                {new Date(media.added).toLocaleDateString("fr-FR", {
                                                    year: "numeric",
                                                    month: "long",
                                                    day: "numeric",
                                                })}
                                            </p>
                                        </div>
                                    )}
                                </div>
                                <div className="space-y-3">
                                    <div>
                                        <p className="text-xs text-muted-foreground">Chemin</p>
                                        <p className="font-mono text-xs break-all">{media.path}</p>
                                    </div>
                                    {media.tmdb_id && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">TMDb ID</p>
                                            <p className="font-medium">{media.tmdb_id}</p>
                                        </div>
                                    )}
                                    {media.imdb_id && (
                                        <div>
                                            <p className="text-xs text-muted-foreground">IMDb ID</p>
                                            <p className="font-medium">{media.imdb_id}</p>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </>
    );
}

// ── Quality Tab ─────────────────────────────────────────────

function QualityTab({ media }: { media: MediaDetail }) {
    const isMovie = media.type === "movie";
    const serviceType = isMovie ? "radarr" : "sonarr";
    const { data: overrides } = useProfileOverrides();
    const { data: profiles } = useAvailableProfiles(serviceType);
    const createOverride = useCreateOverride();
    const deleteOverride = useDeleteOverride();
    const [selectedProfile, setSelectedProfile] = useState("");

    // Find current override for this media
    const currentOverride = overrides?.find(
        (o) => o.external_id === media.id
    );

    // File quality info
    const file = isMovie ? media.file : media.seasons?.flatMap(s => s.episodes).find(e => e.file)?.file;

    return (
        <div className="space-y-6">
            {/* File Quality Summary */}
            {file && (
                <Card className="bg-card/50 border-border/50">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <HardDrive className="h-4 w-4" />
                            Qualité du fichier
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {file.video_codec && (
                                <div>
                                    <p className="text-xs text-muted-foreground">Codec vidéo</p>
                                    <Badge variant="outline" className="mt-1">{file.video_codec}</Badge>
                                </div>
                            )}
                            {file.resolution && (
                                <div>
                                    <p className="text-xs text-muted-foreground">Résolution</p>
                                    <Badge variant="outline" className="mt-1">{file.resolution}</Badge>
                                </div>
                            )}
                            {file.audio_codec && (
                                <div>
                                    <p className="text-xs text-muted-foreground">Codec audio</p>
                                    <Badge variant="outline" className="mt-1">{file.audio_codec}</Badge>
                                </div>
                            )}
                            {file.audio_channels && (
                                <div>
                                    <p className="text-xs text-muted-foreground">Canaux audio</p>
                                    <Badge variant="outline" className="mt-1">{file.audio_channels}</Badge>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* TRaSH Profile Override */}
            <Card className="bg-card/50 border-border/50">
                <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                        <Target className="h-4 w-4" />
                        Profil TRaSH
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {currentOverride ? (
                        <div className="flex items-center justify-between p-3 rounded-lg border bg-primary/5">
                            <div>
                                <p className="text-sm font-medium">
                                    {currentOverride.profile_name.replace(/-/g, " ")}
                                </p>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Override actif — ce média utilise un profil personnalisé
                                </p>
                                {currentOverride.note && (
                                    <p className="text-xs text-muted-foreground mt-1 italic">
                                        {currentOverride.note}
                                    </p>
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-400 hover:text-red-300"
                                onClick={() => deleteOverride.mutate(currentOverride.id)}
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">
                            Ce média utilise le profil TRaSH par défaut.
                        </p>
                    )}

                    {/* Assign form */}
                    <div className="flex gap-2">
                        <select
                            value={selectedProfile}
                            onChange={(e) => setSelectedProfile(e.target.value)}
                            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                            <option value="">Choisir un profil...</option>
                            {(profiles ?? []).map((p) => (
                                <option key={p.filename} value={p.filename}>
                                    {p.display_name}
                                </option>
                            ))}
                        </select>
                        <Button
                            size="sm"
                            disabled={!selectedProfile || createOverride.isPending}
                            onClick={() => {
                                createOverride.mutate({
                                    media_type: isMovie ? "movie" : "series",
                                    external_id: media.id,
                                    title: media.title,
                                    profile_name: selectedProfile,
                                    service_id: 0,
                                });
                                setSelectedProfile("");
                            }}
                        >
                            Appliquer
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
