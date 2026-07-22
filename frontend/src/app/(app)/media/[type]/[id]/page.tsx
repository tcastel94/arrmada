"use client";

import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api-client";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    ArrowLeft,
    Calendar,
    Clock,
    Download,
    CloudDownload,
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
    Search,
    Loader2,
    Send,
    Pencil,
    Plus,
} from "lucide-react";
import {
    useMediaDetail,
    type MediaDetail,
    type FileInfo,
    type SeasonDetail,
    type EpisodeDetail,
    type CastMember,
    useMediaRootFolders,
    useUpdateMediaPath,
    useMediaEditOptions,
    useUpdateMedia,
    useCreateTag,
    useUpdateSeasonMonitoring,
} from "@/hooks/use-media";
import { Switch } from "@/components/ui/switch";
import { useProfileOverrides, useAvailableProfiles, useCreateOverride, useDeleteOverride, useApplyOverride } from "@/hooks/use-profile-overrides";
import { useTriggerMediaSearch, useMediaReleases, useGrabRelease, useSearchEpisodes, type Release } from "@/hooks/use-media-actions";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";
import { toast } from "sonner";

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

function SeasonSection({ seasons, seriesId }: { seasons: SeasonDetail[]; seriesId: string | number }) {
    const [openSeason, setOpenSeason] = useState<number | null>(null);
    const seasonMonitor = useUpdateSeasonMonitoring();
    const [pendingSeason, setPendingSeason] = useState<number | null>(null);
    const searchEpisodes = useSearchEpisodes();
    const [searchingSeason, setSearchingSeason] = useState<number | null>(null);
    const [searchingEp, setSearchingEp] = useState<number | null>(null);

    const toggleSeason = (seasonNumber: number, monitored: boolean) => {
        setPendingSeason(seasonNumber);
        seasonMonitor.mutate(
            { id: seriesId, season: seasonNumber, monitored },
            {
                onSuccess: () =>
                    toast.success(
                        `Saison ${seasonNumber} ${monitored ? "surveillée" : "non surveillée"}.`,
                    ),
                onError: (e) => toast.error("Erreur : " + e.message),
                onSettled: () => setPendingSeason(null),
            },
        );
    };

    // Automatic search for a season's missing episodes (episodes without a file).
    const searchMissingSeason = (season: SeasonDetail) => {
        const ids = season.episodes.filter((e) => !e.has_file).map((e) => e.id);
        if (ids.length === 0) return;
        setSearchingSeason(season.season_number);
        searchEpisodes.mutate(
            { id: seriesId, episodeIds: ids },
            {
                onSuccess: (d) =>
                    toast.success(
                        `Recherche lancée pour ${d.count} épisode${d.count > 1 ? "s" : ""} manquant${d.count > 1 ? "s" : ""}.`,
                    ),
                onError: (e) => toast.error("Erreur : " + e.message),
                onSettled: () => setSearchingSeason(null),
            },
        );
    };

    // Automatic search for a single episode.
    const searchOneEpisode = (episodeId: number) => {
        setSearchingEp(episodeId);
        searchEpisodes.mutate(
            { id: seriesId, episodeIds: [episodeId] },
            {
                onSuccess: () => toast.success("Recherche lancée pour l'épisode."),
                onError: (e) => toast.error("Erreur : " + e.message),
                onSettled: () => setSearchingEp(null),
            },
        );
    };

    return (
        <div className="space-y-3">
            {seasons.filter(s => s.season_number > 0).map((season) => (
                <Card key={season.season_number} className="bg-card/50 border-border/50">
                    <div className="flex items-center">
                        <button
                            className="flex-1 text-left"
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
                        <div className="flex items-center gap-2 pr-4">
                            {season.episodes_have < season.episode_count && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 px-2 text-xs shrink-0"
                                    disabled={searchingSeason === season.season_number}
                                    title="Rechercher automatiquement les épisodes manquants"
                                    onClick={() => searchMissingSeason(season)}
                                >
                                    {searchingSeason === season.season_number ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <>
                                            <Download className="h-3.5 w-3.5 mr-1" />
                                            Manquants ({season.episode_count - season.episodes_have})
                                        </>
                                    )}
                                </Button>
                            )}
                            <Eye
                                title={season.monitored ? "Surveillée" : "Non surveillée"}
                                className={cn(
                                    "h-3.5 w-3.5",
                                    season.monitored ? "text-emerald-400" : "text-muted-foreground/50",
                                )}
                            />
                            <Switch
                                checked={!!season.monitored}
                                disabled={pendingSeason === season.season_number}
                                onCheckedChange={(v) => toggleSeason(season.season_number, v)}
                                aria-label="Surveiller la saison"
                            />
                        </div>
                    </div>
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
                                        {!ep.has_file && (
                                            <Button
                                                size="icon"
                                                variant="ghost"
                                                className="h-6 w-6 shrink-0"
                                                disabled={searchingEp === ep.id}
                                                title="Rechercher cet épisode"
                                                onClick={() => searchOneEpisode(ep.id)}
                                            >
                                                {searchingEp === ep.id ? (
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                ) : (
                                                    <Search className="h-3.5 w-3.5" />
                                                )}
                                            </Button>
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

const MOVIE_AVAILABILITY = [
    { value: "announced", label: "Annoncé" },
    { value: "inCinemas", label: "En salle" },
    { value: "released", label: "Sorti" },
];

const SERIES_TYPES = [
    { value: "standard", label: "Standard" },
    { value: "daily", label: "Quotidien (daily)" },
    { value: "anime", label: "Anime" },
];

function EditMediaDialog({
    type,
    media,
    open,
    onOpenChange,
}: {
    type: "movie" | "series";
    media: MediaDetail;
    open: boolean;
    onOpenChange: (v: boolean) => void;
}) {
    const isMovie = type === "movie";
    const { data: options } = useMediaEditOptions(type, open);
    const updateMedia = useUpdateMedia();
    const createTag = useCreateTag();

    const [monitored, setMonitored] = useState<boolean>(media.monitored);
    const [qualityProfileId, setQualityProfileId] = useState<number | undefined>(
        media.quality_profile_id ?? undefined,
    );
    const [tags, setTags] = useState<number[]>(media.tags ?? []);
    const [minimumAvailability, setMinimumAvailability] = useState<string>(
        media.minimum_availability ?? "released",
    );
    const [seriesType, setSeriesType] = useState<string>(media.series_type || "standard");
    const [newTag, setNewTag] = useState("");

    const toggleTag = (id: number) => {
        setTags((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
    };

    const handleAddTag = () => {
        const label = newTag.trim();
        if (!label) return;
        createTag.mutate(
            { type, label },
            {
                onSuccess: (tag) => {
                    setTags((prev) => [...prev, tag.id]);
                    setNewTag("");
                    toast.success(`Tag « ${tag.label} » créé.`);
                },
                onError: (e) => toast.error("Erreur : " + e.message),
            },
        );
    };

    const handleSave = () => {
        const payload: Record<string, unknown> = { monitored };
        if (qualityProfileId !== undefined) payload.quality_profile_id = qualityProfileId;
        payload.tags = tags;
        if (isMovie) payload.minimum_availability = minimumAvailability;
        else payload.series_type = seriesType;

        updateMedia.mutate(
            { type, id: media.id, data: payload },
            {
                onSuccess: () => {
                    toast.success("Média mis à jour dans " + (isMovie ? "Radarr" : "Sonarr") + " !");
                    onOpenChange(false);
                },
                onError: (e) => toast.error("Erreur : " + e.message),
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[520px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Pencil className="h-4 w-4" /> Éditer « {media.title} »
                    </DialogTitle>
                    <DialogDescription>
                        Modifie les paramètres {isMovie ? "du film" : "de la série"} dans{" "}
                        {isMovie ? "Radarr" : "Sonarr"}.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5 py-2">
                    {/* Monitored */}
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Surveillé</p>
                            <p className="text-xs text-muted-foreground">
                                {isMovie ? "Recherche auto du film" : "Recherche auto des épisodes"}
                            </p>
                        </div>
                        <Switch checked={monitored} onCheckedChange={setMonitored} />
                    </div>

                    {/* Quality profile */}
                    <div className="space-y-1.5">
                        <p className="text-sm font-medium">Profil de qualité</p>
                        <select
                            className="w-full h-9 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                            value={qualityProfileId ?? ""}
                            onChange={(e) => setQualityProfileId(Number(e.target.value) || undefined)}
                        >
                            {(options?.quality_profiles ?? []).map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Movie: minimum availability */}
                    {isMovie && (
                        <div className="space-y-1.5">
                            <p className="text-sm font-medium">Disponibilité minimale</p>
                            <select
                                className="w-full h-9 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                value={minimumAvailability}
                                onChange={(e) => setMinimumAvailability(e.target.value)}
                            >
                                {MOVIE_AVAILABILITY.map((o) => (
                                    <option key={o.value} value={o.value}>
                                        {o.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    {/* Series: type */}
                    {!isMovie && (
                        <div className="space-y-1.5">
                            <p className="text-sm font-medium">Type de série</p>
                            <select
                                className="w-full h-9 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                value={seriesType}
                                onChange={(e) => setSeriesType(e.target.value)}
                            >
                                {SERIES_TYPES.map((o) => (
                                    <option key={o.value} value={o.value}>
                                        {o.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    {/* Tags */}
                    <div className="space-y-2">
                        <p className="text-sm font-medium">Tags</p>
                        <div className="flex flex-wrap gap-1.5">
                            {(options?.tags ?? []).map((t) => {
                                const active = tags.includes(t.id);
                                return (
                                    <button
                                        key={t.id}
                                        type="button"
                                        onClick={() => toggleTag(t.id)}
                                        className={cn(
                                            "px-2 py-1 rounded-md text-xs border transition-colors",
                                            active
                                                ? "bg-primary/20 border-primary/40 text-primary"
                                                : "bg-card/50 border-border/50 text-muted-foreground hover:text-foreground",
                                        )}
                                    >
                                        {t.label}
                                    </button>
                                );
                            })}
                            {(options?.tags ?? []).length === 0 && (
                                <span className="text-xs text-muted-foreground">Aucun tag existant</span>
                            )}
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                            <input
                                className="flex-1 h-8 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                placeholder="Nouveau tag…"
                                value={newTag}
                                onChange={(e) => setNewTag(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        e.preventDefault();
                                        handleAddTag();
                                    }
                                }}
                            />
                            <Button
                                size="sm"
                                variant="outline"
                                disabled={!newTag.trim() || createTag.isPending}
                                onClick={handleAddTag}
                            >
                                {createTag.isPending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Plus className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={updateMedia.isPending}>
                        Annuler
                    </Button>
                    <Button onClick={handleSave} disabled={updateMedia.isPending}>
                        {updateMedia.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        Enregistrer
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export default function MediaDetailPage() {
    const params = useParams();
    const router = useRouter();
    const type = params.type as "movie" | "series";
    const id = params.id as string;

    const { data: media, isLoading, error } = useMediaDetail(type, id);
    const [isScraping, setIsScraping] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteFiles, setDeleteFiles] = useState(true);
    const [deleteDownloads, setDeleteDownloads] = useState(true);
    const [isDeleting, setIsDeleting] = useState(false);

    const [moveDialogOpen, setMoveDialogOpen] = useState(false);
    const [selectedRootFolder, setSelectedRootFolder] = useState("");
    const [customMovePath, setCustomMovePath] = useState("");
    const [editOpen, setEditOpen] = useState(false);

    const { data: rootFolders } = useMediaRootFolders(type, id);
    const updatePathMutation = useUpdateMediaPath();
    const triggerSearch = useTriggerMediaSearch();

    const handleDelete = async () => {
        if (!media) return;
        setIsDeleting(true);
        try {
            await apiFetch(`/api/media/${type}/${media.id}?delete_files=${deleteFiles}&delete_downloads=${deleteDownloads}`, {
                method: "DELETE"
            });
            toast.success("Média supprimé avec succès !");
            setDeleteDialogOpen(false);
            router.push("/media");
        } catch (e) {
            toast.error("Erreur lors de la suppression du média.");
        } finally {
            setIsDeleting(false);
        }
    };

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
                                <Button
                                    variant="default"
                                    size="sm"
                                    className="bg-emerald-600 hover:bg-emerald-500 text-white"
                                    disabled={triggerSearch.isPending}
                                    onClick={() => {
                                        triggerSearch.mutate(
                                            { type, id: media.id },
                                            {
                                                onSuccess: () =>
                                                    toast.success("Recherche automatique lancée dans " + (isMovie ? "Radarr" : "Sonarr") + " !"),
                                                onError: (e) => toast.error("Erreur : " + e.message),
                                            },
                                        );
                                    }}
                                >
                                    {triggerSearch.isPending ? (
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                        <Search className="h-4 w-4 mr-2" />
                                    )}
                                    Rechercher
                                </Button>
                                <Button
                                    variant="default"
                                    size="sm"
                                    className="bg-sky-600 hover:bg-sky-500 text-white"
                                    onClick={() => setEditOpen(true)}
                                >
                                    <Pencil className="h-4 w-4 mr-2" />
                                    Éditer
                                </Button>
                                <Button 
                                    variant="default" 
                                    size="sm" 
                                    className="bg-indigo-600 hover:bg-indigo-500 text-white"
                                    disabled={isScraping}
                                    onClick={async () => {
                                        setIsScraping(true);
                                        try {
                                            const payload = {
                                                movie_id: media.id,
                                                tmdb_id: media.tmdb_id,
                                                imdb_id: media.imdb_id,
                                                source_service: "radarr"
                                            };
                                            await apiFetch("/api/media/scrape", {
                                                method: "POST",
                                                body: JSON.stringify({ items: [payload] })
                                            });
                                            toast.success("Scraping terminé avec succès !");
                                        } catch (e) {
                                            toast.error("Erreur lors du scraping.");
                                        }
                                        setIsScraping(false);
                                    }}
                                >
                                    {isScraping ? (
                                        <CloudDownload className="h-4 w-4 mr-2 animate-bounce" />
                                    ) : (
                                        <CloudDownload className="h-4 w-4 mr-2" />
                                    )}
                                    Scraper (NFO/Art)
                                </Button>
                                <Button 
                                    variant="destructive" 
                                    size="sm"
                                    onClick={() => setDeleteDialogOpen(true)}
                                >
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Supprimer
                                </Button>
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
                        <TabsTrigger value="search">Recherche</TabsTrigger>
                    </TabsList>

                    {/* Seasons tab (series only) */}
                    {!isMovie && media.seasons && (
                        <TabsContent value="seasons">
                            <SeasonSection seasons={media.seasons} seriesId={media.id} />
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
                                    <div className="flex items-center justify-between gap-2 border border-white/5 bg-muted/10 p-2.5 rounded-lg">
                                        <div className="min-w-0">
                                            <p className="text-xs text-muted-foreground">Chemin</p>
                                            <p className="font-mono text-xs break-all text-foreground/80">{media.path}</p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 px-2.5 text-xs gap-1 border-white/10 shrink-0"
                                            onClick={() => {
                                                setSelectedRootFolder(rootFolders?.[0]?.path || "");
                                                // Prepopulate with current base name
                                                const parts = media.path.replace(/\/+$/, "").split("/");
                                                const folderName = parts[parts.length - 1] || "";
                                                setCustomMovePath(folderName);
                                                setMoveDialogOpen(true);
                                            }}
                                        >
                                            <FolderOpen className="h-3.5 w-3.5 text-sky-400" />
                                            Déplacer
                                        </Button>
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

                    {/* Interactive release search tab */}
                    <TabsContent value="search">
                        <InteractiveSearchTab type={type} media={media} />
                    </TabsContent>
                </Tabs>
            </div>

            <EditMediaDialog type={type} media={media} open={editOpen} onOpenChange={setEditOpen} />

            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmer la suppression</DialogTitle>
                        <DialogDescription>
                            Voulez-vous vraiment supprimer « {media.title} » de {isMovie ? "Radarr" : "Sonarr"} ? Cette action est irréversible.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-2 space-y-3">
                        <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={deleteFiles} 
                                onChange={(e) => setDeleteFiles(e.target.checked)}
                                className="h-4.5 w-4.5 rounded border-white/10 bg-muted text-red-600 focus:ring-red-500 focus:ring-offset-background"
                            />
                            <span>Supprimer également les fichiers téléchargés du disque</span>
                        </label>
                        <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={deleteDownloads} 
                                onChange={(e) => setDeleteDownloads(e.target.checked)}
                                className="h-4.5 w-4.5 rounded border-white/10 bg-muted text-red-600 focus:ring-red-500 focus:ring-offset-background"
                            />
                            <span>Supprimer de la file d&apos;attente et de l&apos;historique (SABnzbd, torrents, etc.)</span>
                        </label>
                    </div>
                    <DialogFooter>
                        <Button 
                            variant="outline" 
                            onClick={() => setDeleteDialogOpen(false)}
                            disabled={isDeleting}
                        >
                            Annuler
                        </Button>
                        <Button 
                            variant="destructive" 
                            onClick={handleDelete}
                            disabled={isDeleting}
                        >
                            {isDeleting ? "Suppression..." : "Supprimer"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={moveDialogOpen} onOpenChange={setMoveDialogOpen}>
                <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FolderOpen className="h-5 w-5 text-sky-400" />
                            Déplacer le média
                        </DialogTitle>
                        <DialogDescription>
                            Modifiez le répertoire racine de ce média. Sonarr/Radarr déplacera physiquement tous les fichiers sur le disque.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="py-4 space-y-4">
                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                Dossier Racine Cible
                            </label>
                            <select
                                value={selectedRootFolder}
                                onChange={(e) => setSelectedRootFolder(e.target.value)}
                                className="w-full h-10 px-3 rounded-lg border border-white/10 bg-muted text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
                            >
                                {!rootFolders || rootFolders.length === 0 ? (
                                    <option value="">Aucun dossier racine disponible</option>
                                ) : (
                                    rootFolders.map((rf) => (
                                        <option key={rf.path} value={rf.path}>
                                            {rf.path} ({formatBytes(rf.freeSpace)} libres)
                                        </option>
                                    ))
                                )}
                            </select>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                Nom du Dossier de Destination
                            </label>
                            <input
                                type="text"
                                value={customMovePath}
                                onChange={(e) => setCustomMovePath(e.target.value)}
                                className="w-full h-10 px-3 rounded-lg border border-white/10 bg-muted text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
                                placeholder="Nom du dossier..."
                            />
                        </div>

                        <div className="bg-white/[0.02] border border-white/5 rounded-lg p-3 space-y-1.5">
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                Aperçu du Nouveau Chemin Cible
                            </p>
                            <code className="text-xs font-mono text-sky-400 block break-all">
                                {selectedRootFolder ? (
                                    `${selectedRootFolder.endsWith("/") ? selectedRootFolder : `${selectedRootFolder}/`}${customMovePath}`
                                ) : (
                                    "Sélectionnez un dossier racine..."
                                )}
                            </code>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setMoveDialogOpen(false)}
                            disabled={updatePathMutation.isPending}
                        >
                            Annuler
                        </Button>
                        <Button
                            onClick={() => {
                                if (!selectedRootFolder) {
                                    toast.error("Veuillez sélectionner un dossier racine.");
                                    return;
                                }
                                if (!customMovePath.trim()) {
                                    toast.error("Veuillez spécifier un nom de dossier.");
                                    return;
                                }
                                const fullNewPath = selectedRootFolder.endsWith("/")
                                    ? `${selectedRootFolder}${customMovePath.trim()}`
                                    : `${selectedRootFolder}/${customMovePath.trim()}`;
                                
                                updatePathMutation.mutate({
                                    type,
                                    id,
                                    new_path: fullNewPath,
                                }, {
                                    onSuccess: () => {
                                        toast.success("Déplacement initié avec succès ! Les fichiers sont en cours de transfert.");
                                        setMoveDialogOpen(false);
                                    },
                                    onError: (err: any) => {
                                        toast.error(`Erreur lors du déplacement : ${err.message || err}`);
                                    }
                                });
                            }}
                            disabled={updatePathMutation.isPending || !selectedRootFolder}
                        >
                            {updatePathMutation.isPending ? "Déplacement en cours..." : "Déplacer les fichiers"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
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
    const applyOverride = useApplyOverride();
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
                        <div className="space-y-3">
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
                                <div className="flex gap-1">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-red-400 hover:text-red-300"
                                        onClick={() => deleteOverride.mutate(currentOverride.id)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                            <Button
                                className="w-full gap-2"
                                onClick={() => applyOverride.mutate(currentOverride.id)}
                                disabled={applyOverride.isPending}
                            >
                                {applyOverride.isPending ? (
                                    <><Download className="h-4 w-4 animate-spin" /> Application en cours...</>
                                ) : (
                                    <><Download className="h-4 w-4" /> Appliquer à {isMovie ? 'Radarr' : 'Sonarr'}</>
                                )}
                            </Button>
                            {applyOverride.isSuccess && (
                                <div className="p-3 rounded-lg border bg-emerald-500/10 text-emerald-400 text-sm">
                                    ✅ Profil appliqué ! {applyOverride.data.cfs_created} CFs créés, {applyOverride.data.cfs_updated} mis à jour.
                                    {applyOverride.data.media_updated && " Série mise à jour."}
                                </div>
                            )}
                            {applyOverride.isError && (
                                <div className="p-3 rounded-lg border bg-red-500/10 text-red-400 text-sm">
                                    ❌ Erreur : {applyOverride.error.message}
                                </div>
                            )}
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


// ── Interactive Search Tab ──────────────────────────────────

function InteractiveSearchTab({ type, media }: { type: "movie" | "series"; media: MediaDetail }) {
    const isSeries = type === "series";
    // Real seasons only (exclude specials / season 0).
    const seasons = (media.seasons ?? [])
        .filter((s) => s.season_number > 0)
        .sort((a, b) => a.season_number - b.season_number);
    const seasonOptions = seasons.map((s) => s.season_number);
    const [enabled, setEnabled] = useState(false);
    // "season" = season-pack search (slow fan-out across every episode);
    // "episode" = single-episode search (fast) — the escape hatch for very
    // large anime seasons that would otherwise time out.
    const [searchMode, setSearchMode] = useState<"season" | "episode">("season");
    const [selectedSeason, setSelectedSeason] = useState<number | undefined>(
        isSeries ? seasonOptions[0] : undefined,
    );
    const [selectedEpisode, setSelectedEpisode] = useState<number | undefined>(undefined);

    const episodeOptions = isSeries
        ? (seasons.find((s) => s.season_number === selectedSeason)?.episodes ?? [])
        : [];
    // Fall back to the first episode of the season when none is explicitly picked.
    const effectiveEpisode = selectedEpisode ?? episodeOptions[0]?.id;

    const { data, isFetching, error, refetch } = useMediaReleases(
        type,
        media.id,
        enabled,
        searchMode === "season" ? selectedSeason : undefined,
        searchMode === "episode" ? effectiveEpisode : undefined,
    );
    const grab = useGrabRelease();
    const [grabbing, setGrabbing] = useState<string | null>(null);

    const canSearch =
        !isSeries ||
        (searchMode === "season"
            ? selectedSeason !== undefined
            : effectiveEpisode !== undefined);

    const handleGrab = (r: Release) => {
        setGrabbing(r.guid);
        grab.mutate(
            { type, id: media.id, guid: r.guid, indexer_id: r.indexer_id },
            {
                onSuccess: () => toast.success("Release envoyée au client de téléchargement !"),
                onError: (e) => toast.error("Échec du grab : " + e.message),
                onSettled: () => setGrabbing(null),
            },
        );
    };

    return (
        <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                    Recherche interactive sur les indexeurs via {type === "movie" ? "Radarr" : "Sonarr"}.
                    {isSeries
                        ? " Choisissez une saison (pack) ou un épisode précis, puis lancez la recherche. L'épisode est plus rapide sur les très grosses saisons."
                        : " Choisissez une release à envoyer au client de téléchargement."}
                </p>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                    {isSeries && (
                        <>
                            <select
                                className="h-9 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                value={searchMode}
                                title="Mode de recherche"
                                onChange={(e) => {
                                    setSearchMode(e.target.value as "season" | "episode");
                                    setEnabled(false); // force an explicit re-search for the new mode
                                }}
                            >
                                <option value="season">Season pack</option>
                                <option value="episode">Épisode</option>
                            </select>
                            <select
                                className="h-9 rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                value={selectedSeason ?? ""}
                                onChange={(e) => {
                                    const n = Number(e.target.value);
                                    setSelectedSeason(Number.isNaN(n) ? undefined : n);
                                    setSelectedEpisode(undefined); // reset episode for the new season
                                    setEnabled(false); // force an explicit re-search for the new season
                                }}
                            >
                                {seasonOptions.length === 0 && <option value="">Aucune saison</option>}
                                {seasonOptions.map((n) => (
                                    <option key={n} value={n}>
                                        Saison {n}
                                    </option>
                                ))}
                            </select>
                            {searchMode === "episode" && (
                                <select
                                    className="h-9 max-w-[16rem] rounded-md border border-border/60 bg-card/50 px-2 text-sm"
                                    value={effectiveEpisode ?? ""}
                                    onChange={(e) => {
                                        const n = Number(e.target.value);
                                        setSelectedEpisode(Number.isNaN(n) ? undefined : n);
                                        setEnabled(false); // force an explicit re-search for the new episode
                                    }}
                                >
                                    {episodeOptions.length === 0 && <option value="">Aucun épisode</option>}
                                    {episodeOptions.map((ep) => (
                                        <option key={ep.id} value={ep.id}>
                                            E{String(ep.episode_number).padStart(2, "0")}
                                            {ep.title ? ` — ${ep.title}` : ""}
                                        </option>
                                    ))}
                                </select>
                            )}
                        </>
                    )}
                    <Button
                        size="sm"
                        variant="outline"
                        className="shrink-0"
                        disabled={isFetching || !canSearch}
                        onClick={() => {
                            if (!enabled) setEnabled(true);
                            else refetch();
                        }}
                    >
                        {isFetching ? (
                            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Recherche…</>
                        ) : (
                            <><Search className="h-4 w-4 mr-2" /> {enabled ? "Relancer" : "Lancer la recherche"}</>
                        )}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="p-3 rounded-lg border bg-red-500/10 text-red-400 text-sm">
                    Erreur : {error.message}
                </div>
            )}

            {isFetching && !data && (
                <div className="space-y-2">
                    {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="h-14 bg-muted/40 rounded-lg animate-pulse" />
                    ))}
                </div>
            )}

            {data && data.items.length === 0 && !isFetching && (
                <p className="text-sm text-muted-foreground">Aucune release trouvée.</p>
            )}

            {data && data.items.length > 0 && (
                <div className="space-y-2">
                    {data.items.map((r) => (
                        <Card key={r.guid} className={cn("bg-card/50 border-border/50", r.rejected && "opacity-60")}>
                            <CardContent className="p-3 flex items-center gap-3">
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium truncate" title={r.title}>{r.title}</p>
                                    <div className="flex flex-wrap items-center gap-1.5 mt-1">
                                        <Badge variant="outline" className="text-[10px]">{r.quality}</Badge>
                                        <Badge variant="secondary" className="text-[10px]">{r.indexer}</Badge>
                                        <Badge variant="secondary" className="text-[10px]">{r.protocol}</Badge>
                                        <span className="text-[10px] text-muted-foreground">{formatBytes(r.size_bytes)}</span>
                                        {r.protocol === "torrent" && (
                                            <span className="text-[10px] text-muted-foreground">↑{r.seeders ?? 0}</span>
                                        )}
                                        <span className="text-[10px] text-muted-foreground">{Math.round(r.age_days)}j</span>
                                        <Badge
                                            variant="outline"
                                            className={cn(
                                                "text-[10px]",
                                                r.custom_format_score > 0 && "text-emerald-400 border-emerald-500/30",
                                                r.custom_format_score < 0 && "text-red-400 border-red-500/30",
                                            )}
                                        >
                                            CF {r.custom_format_score}
                                        </Badge>
                                        {r.rejected && (
                                            <Badge
                                                variant="outline"
                                                className="text-[10px] text-amber-400 border-amber-500/30"
                                                title={r.rejections.join("; ")}
                                            >
                                                Rejeté
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                                <Button
                                    size="sm"
                                    variant={r.rejected ? "outline" : "default"}
                                    className="shrink-0"
                                    disabled={grabbing === r.guid}
                                    onClick={() => handleGrab(r)}
                                >
                                    {grabbing === r.guid ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <><Send className="h-4 w-4 mr-1" /> Grab</>
                                    )}
                                </Button>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
