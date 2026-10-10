"use client";

/**
 * Onglet « Fichiers & qualité » (fusion des anciens onglets Fichier + Qualité).
 * ----------------------------------------------------------------
 * - Film : fiche technique complète du fichier.
 * - Série : synthèse sur TOUS les épisodes (avant : qualité = fichier du
 *   1er épisode seulement, et liste tronquée à 5 fichiers sans le dire),
 *   puis la liste complète des fichiers, saison par saison.
 * - Profil de qualité : profil *arr actuel + profil TRaSH personnalisé
 *   (attribution, application, retrait avec confirmation).
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import {
    AudioLines,
    Calendar,
    ChevronRight,
    Clock,
    FileVideo,
    Gauge,
    HardDrive,
    Languages,
    Loader2,
    Monitor,
    Sparkles,
    Subtitles,
    Tag,
    Target,
    Trash2,
    Users,
} from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useMediaEditOptions, type EpisodeDetail, type FileInfo, type MediaDetail } from "@/hooks/use-media";
import {
    useApplyOverride,
    useAvailableProfiles,
    useCreateOverride,
    useDeleteOverride,
    useProfileOverrides,
} from "@/hooks/use-profile-overrides";
import { useServices } from "@/hooks/use-services";
import { formatBytes, formatShortDate, percent } from "@/lib/format";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { audioChannelsLabel, episodeCode, hdrLabel, resolutionLabel, seasonLabel, sortSeasons, sourceLabel } from "./labels";

export function FilesQualityTab({ media }: { media: MediaDetail }) {
    return (
        <motion.div
            variants={stagger(0, 0.08)}
            initial="hidden"
            animate="show"
            className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_400px]"
        >
            <motion.div variants={fadeUp} className="min-w-0 space-y-6">
                {media.type === "movie" ? <MovieFilePanel file={media.file ?? null} /> : <SeriesFiles media={media} />}
            </motion.div>
            <motion.div variants={fadeUp} className="min-w-0">
                <QualityProfilePanel media={media} />
            </motion.div>
        </motion.div>
    );
}

/* ════════════════════════════════════════════════════════════════
   Fiche technique d'un fichier
   ════════════════════════════════════════════════════════════════ */

function Spec({ icon: Icon, label, value }: { icon: typeof HardDrive; label: string; value?: string | null }) {
    if (!value) return null;
    return (
        <div className="flex items-start gap-2.5 rounded-xl border border-white/[0.06] bg-background/40 p-3">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary/80" aria-hidden />
            <div className="min-w-0">
                <p className="eyebrow">{label}</p>
                <p className="break-words text-sm font-medium">{value}</p>
            </div>
        </div>
    );
}

function MovieFilePanel({ file }: { file: FileInfo | null }) {
    if (!file) {
        return (
            <Panel title="Fichier" icon={FileVideo}>
                <EmptyState
                    compact
                    icon={FileVideo}
                    title="Aucun fichier sur le disque"
                    description="Lance une recherche automatique ou choisis une release dans l'onglet Releases."
                />
            </Panel>
        );
    }
    const hdr = hdrLabel(file);
    return (
        <Panel title="Fichier" icon={FileVideo} action={<Badge variant="default">{file.quality}</Badge>}>
            <p className="mb-4 break-all font-mono text-xs text-muted-foreground">{file.relative_path || file.path}</p>
            <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                <Spec icon={Monitor} label="Résolution" value={[resolutionLabel(file.resolution), sourceLabel(file.quality_source)].filter(Boolean).join(" · ")} />
                <Spec icon={FileVideo} label="Codec vidéo" value={file.video_codec} />
                <Spec icon={Sparkles} label="Plage dynamique" value={hdr ?? "SDR"} />
                <Spec icon={AudioLines} label="Audio" value={[file.audio_codec, audioChannelsLabel(file.audio_channels)].filter(Boolean).join(" ")} />
                <Spec icon={Languages} label="Langues audio" value={file.audio_languages} />
                <Spec icon={Subtitles} label="Sous-titres intégrés" value={file.subtitle_languages} />
                <Spec icon={HardDrive} label="Taille" value={formatBytes(file.size_bytes)} />
                <Spec icon={Clock} label="Durée" value={file.run_time} />
                <Spec icon={Users} label="Groupe de release" value={file.release_group} />
                <Spec icon={Tag} label="Édition" value={file.edition} />
                <Spec icon={Calendar} label="Importé" value={formatShortDate(file.date_added)} />
            </div>
        </Panel>
    );
}

/* ════════════════════════════════════════════════════════════════
   Série : synthèse + liste complète
   ════════════════════════════════════════════════════════════════ */

/** Compte les occurrences d'une valeur (qualité, codec…) triées par fréquence. */
function countBy(files: FileInfo[], pick: (f: FileInfo) => string | null | undefined) {
    const m = new Map<string, number>();
    for (const f of files) {
        const k = (pick(f) || "").trim();
        if (k) m.set(k, (m.get(k) ?? 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1]);
}

function SeriesFiles({ media }: { media: MediaDetail }) {
    const seasons = useMemo(() => sortSeasons(media.seasons ?? []), [media.seasons]);
    const episodes = useMemo(() => seasons.flatMap((s) => s.episodes).filter((e) => e.file), [seasons]);
    const files = episodes.map((e) => e.file as FileInfo);
    const totalSize = files.reduce((acc, f) => acc + (f.size_bytes || 0), 0);
    const qualities = countBy(files, (f) => f.quality);
    const codecs = countBy(files, (f) => f.video_codec);
    const hdr = countBy(files, (f) => hdrLabel(f));
    const audio = countBy(files, (f) => [f.audio_codec, audioChannelsLabel(f.audio_channels)].filter(Boolean).join(" "));
    const [openSeasons, setOpenSeasons] = useState<Set<number>>(new Set());

    if (files.length === 0) {
        return (
            <Panel title="Fichiers" icon={FileVideo}>
                <EmptyState compact icon={FileVideo} title="Aucun épisode sur le disque" description="Les fichiers apparaîtront ici dès le premier import." />
            </Panel>
        );
    }

    return (
        <>
            <Panel title="Vue d'ensemble" icon={Gauge}>
                <div className="grid gap-5 md:grid-cols-[auto_minmax(0,1fr)]">
                    <div className="flex gap-6 md:flex-col md:gap-3 md:border-r md:border-white/[0.05] md:pr-6">
                        <div>
                            <p className="eyebrow">Fichiers</p>
                            <p className="text-2xl font-bold tracking-tight">
                                <AnimatedNumber value={files.length} />
                            </p>
                        </div>
                        <div>
                            <p className="eyebrow">Taille totale</p>
                            <p className="text-2xl font-bold tracking-tight">{formatBytes(totalSize || media.size_on_disk)}</p>
                        </div>
                    </div>
                    <div className="min-w-0 space-y-4">
                        <div className="space-y-2.5">
                            <p className="eyebrow">Qualités</p>
                            {qualities.map(([q, n]) => (
                                <div key={q} className="space-y-1">
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="font-medium">{q}</span>
                                        <span className="tabular-nums text-muted-foreground">
                                            {n} épisode{n > 1 ? "s" : ""} · {Math.round(percent(n, files.length))} %
                                        </span>
                                    </div>
                                    <GradientProgress value={percent(n, files.length)} glow={false} />
                                </div>
                            ))}
                        </div>
                        {[
                            { label: "Codecs vidéo", items: codecs },
                            { label: "HDR", items: hdr },
                            { label: "Audio", items: audio },
                        ]
                            .filter((g) => g.items.length > 0)
                            .map((g) => (
                                <div key={g.label} className="space-y-1.5">
                                    <p className="eyebrow">{g.label}</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {g.items.map(([v, n]) => (
                                            <span key={v} className="chip">
                                                {v}
                                                <span className="tabular-nums text-muted-foreground/70">×{n}</span>
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                    </div>
                </div>
            </Panel>

            <Panel
                title="Fichiers par saison"
                icon={FileVideo}
                action={<span className="text-xs text-muted-foreground">{files.length} fichier{files.length > 1 ? "s" : ""} au total</span>}
                bodyClassName="p-2 sm:p-3"
            >
                <div className="space-y-1">
                    {seasons.map((season) => {
                        const eps = season.episodes.filter((e) => e.file);
                        if (eps.length === 0) return null;
                        const isOpen = openSeasons.has(season.season_number) || seasons.length === 1;
                        const size = eps.reduce((acc, e) => acc + (e.file?.size_bytes || 0), 0);
                        const panelId = `files-season-${season.season_number}`;
                        return (
                            <div key={season.season_number} className="rounded-xl">
                                <button
                                    type="button"
                                    aria-expanded={isOpen}
                                    aria-controls={panelId}
                                    onClick={() =>
                                        setOpenSeasons((prev) => {
                                            const next = new Set(prev);
                                            if (next.has(season.season_number)) next.delete(season.season_number);
                                            else next.add(season.season_number);
                                            return next;
                                        })
                                    }
                                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70"
                                >
                                    <ChevronRight
                                        className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300", isOpen && "rotate-90")}
                                        aria-hidden
                                    />
                                    <span className="flex-1 text-sm font-medium">{seasonLabel(season.season_number)}</span>
                                    <span className="text-xs tabular-nums text-muted-foreground">
                                        {eps.length} fichier{eps.length > 1 ? "s" : ""} · {formatBytes(size)}
                                    </span>
                                </button>
                                <AnimatePresence initial={false}>
                                    {isOpen && (
                                        <motion.ul
                                            id={panelId}
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: "auto", opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            transition={{ duration: 0.3, ease: EASE_OUT }}
                                            className="overflow-hidden px-2 pb-2"
                                        >
                                            {eps.map((ep) => (
                                                <EpisodeFileRow key={ep.id} ep={ep} />
                                            ))}
                                        </motion.ul>
                                    )}
                                </AnimatePresence>
                            </div>
                        );
                    })}
                </div>
            </Panel>
        </>
    );
}

function EpisodeFileRow({ ep }: { ep: EpisodeDetail }) {
    const f = ep.file as FileInfo;
    const hdr = hdrLabel(f);
    return (
        <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-white/[0.04] px-1 py-2 text-xs first:border-t-0">
            <span className="w-14 shrink-0 font-mono text-muted-foreground">{episodeCode(ep.season_number, ep.episode_number)}</span>
            <span className="min-w-0 flex-1 truncate" title={f.relative_path}>
                {ep.title || f.relative_path}
            </span>
            <span className="flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="text-[10px]">{f.quality}</Badge>
                {f.video_codec && <span className="text-muted-foreground">{f.video_codec}</span>}
                {hdr && <span className="text-primary">{hdr}</span>}
                <span className="tabular-nums text-muted-foreground">{formatBytes(f.size_bytes)}</span>
            </span>
        </li>
    );
}

/* ════════════════════════════════════════════════════════════════
   Profil de qualité (*arr + TRaSH)
   ════════════════════════════════════════════════════════════════ */

function QualityProfilePanel({ media }: { media: MediaDetail }) {
    const isMovie = media.type === "movie";
    const serviceType = isMovie ? "radarr" : "sonarr";
    const arr = isMovie ? "Radarr" : "Sonarr";

    const overrides = useProfileOverrides();
    const profiles = useAvailableProfiles(serviceType);
    const options = useMediaEditOptions(media.type, true);
    const { data: services } = useServices();
    const createOverride = useCreateOverride();
    const deleteOverride = useDeleteOverride();
    const applyOverride = useApplyOverride();
    const [selected, setSelected] = useState("");
    const [confirmRemove, setConfirmRemove] = useState(false);

    // Correspondance par id ET type : un film et une série peuvent partager le même id *arr.
    const current = overrides.data?.find((o) => o.external_id === media.id && o.media_type === media.type);
    const currentName =
        profiles.data?.find((p) => p.filename === current?.profile_name)?.display_name ?? current?.profile_name.replace(/-/g, " ");
    const arrProfile = options.data?.quality_profiles.find((p) => p.id === media.quality_profile_id)?.name;
    // Vrai id du service Radarr/Sonarr (avant : 0 codé en dur → doublons possibles).
    const serviceId = services?.find((s) => s.type === serviceType && s.is_enabled)?.id ?? 0;

    const assign = () => {
        if (!selected) return;
        createOverride.mutate(
            {
                media_type: media.type,
                external_id: media.id,
                title: media.title,
                profile_name: selected,
                service_id: serviceId,
            },
            {
                onSuccess: () => {
                    toast.success("Profil personnalisé attribué", {
                        description: `Clique sur « Appliquer à ${arr} » pour l'activer.`,
                    });
                    // Le choix n'est réinitialisé qu'en cas de succès (avant : avant même la réponse).
                    setSelected("");
                },
                onError: (e) => toast.error("Attribution impossible", { description: e.message }),
            },
        );
    };

    const apply = () => {
        if (!current) return;
        applyOverride.mutate(current.id, {
            onSuccess: (r) => {
                toast.success(`Profil appliqué dans ${arr}`, {
                    description: `${r.cfs_created} format${r.cfs_created > 1 ? "s" : ""} personnalisé${r.cfs_created > 1 ? "s" : ""} créé${r.cfs_created > 1 ? "s" : ""}, ${r.cfs_updated} mis à jour${
                        r.media_updated ? ` · ${isMovie ? "film mis à jour" : "série mise à jour"}` : ""
                    }.`,
                });
                if (r.errors?.length) toast.warning("Application partielle", { description: r.errors.slice(0, 3).join(" · ") });
            },
            onError: (e) => toast.error("Application impossible", { description: e.message }),
        });
    };

    return (
        <Panel title="Profil de qualité" icon={Target} iconClassName="text-amber-300">
            <div className="space-y-5">
                {/* Profil actuellement appliqué dans Radarr/Sonarr */}
                <div className="flex items-center justify-between gap-3">
                    <p className="text-xs text-muted-foreground">Profil {arr}</p>
                    {options.isLoading ? (
                        <Shimmer className="h-5 w-28 rounded-md" />
                    ) : (
                        <Badge variant="secondary">{arrProfile ?? (media.quality_profile_id ? `#${media.quality_profile_id}` : "—")}</Badge>
                    )}
                </div>

                {/* Profil TRaSH personnalisé */}
                {overrides.isLoading ? (
                    <Shimmer className="h-24 w-full" />
                ) : overrides.isError ? (
                    <ErrorState compact error={overrides.error} onRetry={() => overrides.refetch()} title="Profils personnalisés indisponibles" />
                ) : current ? (
                    <div className="border-gradient relative space-y-3 rounded-2xl bg-primary/[0.06] p-4">
                        <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <p className="flex items-center gap-1.5 text-xs font-semibold text-primary">
                                    <Sparkles className="h-3.5 w-3.5" aria-hidden /> Profil personnalisé actif
                                </p>
                                <p className="mt-1 truncate text-sm font-semibold capitalize">{currentName}</p>
                                {current.note && <p className="mt-1 text-xs italic text-muted-foreground">{current.note}</p>}
                            </div>
                            <Button
                                size="icon-sm"
                                variant="ghost"
                                className="shrink-0 text-muted-foreground hover:text-red-400"
                                aria-label="Retirer le profil personnalisé"
                                onClick={() => setConfirmRemove(true)}
                            >
                                <Trash2 />
                            </Button>
                        </div>
                        <Button className="w-full" onClick={apply} disabled={applyOverride.isPending}>
                            {applyOverride.isPending ? <Loader2 className="animate-spin" /> : <Target />}
                            {applyOverride.isPending ? "Application en cours…" : `Appliquer à ${arr}`}
                        </Button>
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">
                        Ce {isMovie ? "film" : "titre"} suit le profil TRaSH par défaut de {arr}.
                    </p>
                )}

                {/* Attribution d'un profil */}
                <div className="space-y-2">
                    <Label htmlFor={`trash-profile-${media.id}`} className="text-xs text-muted-foreground">
                        {current ? "Remplacer par un autre profil TRaSH" : "Attribuer un profil TRaSH personnalisé"}
                    </Label>
                    {profiles.isError ? (
                        <ErrorState compact error={profiles.error} onRetry={() => profiles.refetch()} title="Profils TRaSH indisponibles" />
                    ) : (
                        <div className="flex gap-2">
                            <Select value={selected} onValueChange={setSelected} disabled={profiles.isLoading}>
                                <SelectTrigger id={`trash-profile-${media.id}`} className="flex-1">
                                    <SelectValue placeholder={profiles.isLoading ? "Chargement des profils…" : "Choisir un profil…"} />
                                </SelectTrigger>
                                <SelectContent className="max-h-72">
                                    {(profiles.data ?? []).map((p) => (
                                        <SelectItem key={p.filename} value={p.filename}>
                                            {p.display_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Button variant="outline" disabled={!selected || createOverride.isPending} onClick={assign}>
                                {createOverride.isPending && <Loader2 className="animate-spin" />}
                                Attribuer
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            <ConfirmDialog
                open={confirmRemove}
                onOpenChange={setConfirmRemove}
                destructive
                title="Retirer le profil personnalisé ?"
                description={`« ${media.title} » repassera sur le profil TRaSH par défaut. Le profil déjà appliqué dans ${arr} n'est pas modifié.`}
                confirmLabel="Retirer"
                onConfirm={async () => {
                    if (!current) return;
                    try {
                        await deleteOverride.mutateAsync(current.id);
                        toast.success("Profil personnalisé retiré");
                    } catch (e) {
                        toast.error("Retrait impossible", { description: e instanceof Error ? e.message : String(e) });
                        throw e;
                    }
                }}
            />
        </Panel>
    );
}
