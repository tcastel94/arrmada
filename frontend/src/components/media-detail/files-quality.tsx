"use client";

/**
 * Onglet « Fichiers & qualité » (fusion des anciens onglets Fichier + Qualité).
 * ----------------------------------------------------------------
 * - Film : fiche technique complète du fichier.
 * - Série : synthèse sur TOUS les épisodes (avant : qualité = fichier du
 *   1er épisode seulement, et liste tronquée à 5 fichiers sans le dire),
 *   puis la liste complète des fichiers, saison par saison.
 * - Version & qualité : version voulue pour ce titre (VF, MULTi, VOSTFR, VO),
 *   ce que contient le fichier actuel, et le bouton pour en changer.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    AudioLines,
    Calendar,
    ChevronRight,
    Clock,
    FileVideo,
    Gauge,
    HardDrive,
    Languages,
    Monitor,
    Sparkles,
    Subtitles,
    Tag,
    Users,
} from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type EpisodeDetail, type FileInfo, type MediaDetail } from "@/hooks/use-media";
import { useMediaVersion } from "@/hooks/use-media-version";
import { formatBytes, formatShortDate, percent } from "@/lib/format";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { FileVerdict } from "./version-dialog";
import { versionLabel } from "./version-options";
import { audioChannelsLabel, episodeCode, hdrLabel, resolutionLabel, seasonLabel, sortSeasons, sourceLabel } from "./labels";

export function FilesQualityTab({ media, onVersion }: { media: MediaDetail; onVersion: () => void }) {
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
                <VersionPanel media={media} onVersion={onVersion} />
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
   Version & qualité voulues pour CE titre
   ════════════════════════════════════════════════════════════════ */

/**
 * Résumé de la version voulue (VF, MULTi…) et de ce que contient le fichier,
 * avec le bouton qui ouvre le réglage. Remplace l'ancien panneau « Profil de
 * qualité », qui demandait de connaître les noms de profils TRaSH.
 */
function VersionPanel({ media, onVersion }: { media: MediaDetail; onVersion: () => void }) {
    const isMovie = media.type === "movie";
    const arr = isMovie ? "Radarr" : "Sonarr";
    const state = useMediaVersion(media.type, media.id);
    const data = state.data;

    return (
        <Panel title="Version & qualité" icon={Languages}>
            {state.isLoading ? (
                <div className="space-y-3">
                    <Shimmer className="h-7 w-40 rounded-md" />
                    <Shimmer className="h-12 w-full rounded-xl" />
                    <Shimmer className="h-10 w-full rounded-xl" />
                </div>
            ) : state.isError || !data ? (
                <ErrorState compact error={state.error} onRetry={() => state.refetch()} title="Version indisponible" />
            ) : (
                <div className="space-y-4">
                    <div>
                        <p className="eyebrow">Version voulue</p>
                        {data.version ? (
                            <p className="mt-1 text-[22px] font-bold tracking-tight">{versionLabel(data.version)}</p>
                        ) : (
                            <>
                                <p className="mt-1 text-[17px] font-semibold">Non choisie</p>
                                <p className="mt-1 text-xs leading-snug text-muted-foreground">
                                    Ce {isMovie ? "film" : "titre"} suit le profil général « {data.profile?.name ?? "inconnu"} ». Choisis une version pour
                                    le distinguer du reste (par exemple la VF pour un dessin animé).
                                </p>
                            </>
                        )}
                    </div>

                    <div className="rounded-xl border border-white/[0.06] bg-background/40 p-3">
                        <p className="eyebrow">{isMovie ? "Fichier actuel" : "Épisodes téléchargés"}</p>
                        <FileVerdict file={data.file} isMovie={isMovie} showVerdict={!!data.version} className="mt-1.5" />
                    </div>

                    <Button className="w-full" onClick={onVersion}>
                        <Languages /> {data.version ? "Changer de version…" : "Choisir une version…"}
                    </Button>

                    <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                        <span>Profil {arr}</span>
                        <span className="min-w-0 truncate text-right" title={data.profile?.name}>
                            {data.profile?.name ?? "—"}
                        </span>
                    </div>
                </div>
            )}
        </Panel>
    );
}
