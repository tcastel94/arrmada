"use client";

/**
 * Représentations d'un média de la bibliothèque :
 *  - MediaPosterCard : carte affiche (vue grille) basée sur PosterCard
 *  - MediaListRow    : ligne compacte (vue liste)
 *  - MediaStateBadges: badges ST FR / Vu partagés par les deux vues
 *
 * Films : la qualité brute (« Bluray-2160p ») est remplacée par 2-3 badges
 * techniques courts (4K · DV · Atmos) quand Radarr fournit les infos du
 * fichier ; sinon on garde le nom de qualité. Séries : pas de fichier
 * unique → on garde le nom du profil qualité.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Eye, EyeOff, Film, HardDrive, Tv } from "lucide-react";
import type { MediaItem } from "@/hooks/use-media";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { fadeIn } from "@/lib/motion";
import { MediaThumb } from "./media-thumb";
import type { SubState, WatchState } from "./enrichment";
import { translateGenre } from "@/lib/genres";
import { MediaTechBadges, cardTechBadges } from "@/components/media/media-tech-badges";

/** Lien vers la fiche d'un média. */
export const mediaHref = (item: Pick<MediaItem, "type" | "external_id">) => `/media/${item.type}/${item.external_id}`;

/** Clé unique (un film et une série peuvent partager le même ID numérique). */
export const mediaKey = (item: Pick<MediaItem, "type" | "external_id">) => `${item.type}:${item.external_id}`;

/**
 * Qualité lisible du fichier, ou null.
 * Pour les séries, l'agrégateur backend renvoie l'ID du PROFIL qualité
 * (un nombre, ex: 8) dans `quality` : on ne l'affiche pas, ce n'est pas
 * une qualité de fichier (correctif backend à prévoir).
 */
export function qualityLabel(item: Pick<MediaItem, "quality">): string | null {
    return typeof item.quality === "string" && item.quality.trim() ? item.quality : null;
}

/** Progression des épisodes d'une série (0-100), sinon undefined. */
export function episodeProgress(item: MediaItem): number | undefined {
    if (item.type !== "series" || !item.episodes_total) return undefined;
    return ((item.episodes_have ?? 0) / item.episodes_total) * 100;
}

/** Badges sous-titres FR + lecture Kodi (sur l'affiche). */
export function MediaStateBadges({ sub, watch }: { sub: SubState; watch: WatchState }) {
    return (
        <>
            {sub === "present" && (
                <PosterBadge tone="success" title="Sous-titres français disponibles">
                    ST FR ✓
                </PosterBadge>
            )}
            {sub === "missing" && (
                <PosterBadge tone="warning" title="Sous-titres français manquants">
                    ST FR ✗
                </PosterBadge>
            )}
            {watch?.watched ? (
                <PosterBadge tone="violet" title="Vu sur une TV">
                    <Check className="h-2.5 w-2.5" strokeWidth={3} /> Vu
                </PosterBadge>
            ) : watch?.progress ? (
                <PosterBadge tone="violet" title={`En cours sur une TV — ${watch.progress} %`}>
                    ⏵ {watch.progress} %
                </PosterBadge>
            ) : watch?.episodes ? (
                <PosterBadge tone="violet" title={`${watch.episodes} épisode(s) vu(s) sur les TV`}>
                    <Eye className="h-2.5 w-2.5" strokeWidth={3} /> {watch.episodes} ép.
                </PosterBadge>
            ) : null}
        </>
    );
}

interface MediaViewProps {
    item: MediaItem;
    sub: SubState;
    watch: WatchState;
    selectable?: boolean;
    selected?: boolean;
    onToggleSelect?: () => void;
}

/** Badges techniques retenus pour l'affiche (films uniquement, max 3). */
function techBadgesOf(item: MediaItem) {
    return item.type === "movie" ? cardTechBadges(item) : [];
}

export function MediaPosterCard({ item, sub, watch, selectable, selected, onToggleSelect }: MediaViewProps) {
    const quality = qualityLabel(item);
    const isMovie = item.type === "movie";
    const hasTech = techBadgesOf(item).length > 0;
    // Affiche épurée (style app TV d'Apple) : seulement l'essentiel sur l'image
    //  - manquant → pastille rouge ; déjà vu → coche ronde ;
    //  - barre de progression : film commencé, ou épisodes présents d'une série.
    // Le détail (4K · DV · Atmos, ST FR, genres, taille) apparaît au survol.
    const progress = isMovie ? (watch && !watch.watched && watch.progress ? watch.progress : undefined) : episodeProgress(item);
    return (
        <PosterCard
            title={item.title}
            subtitle={[item.year, isMovie ? "Film" : "Série"].filter(Boolean).join(" · ")}
            posterUrl={item.poster_url}
            type={item.type}
            href={mediaHref(item)}
            dimmed={!item.has_file}
            progress={progress}
            corner={
                !item.has_file ? (
                    <PosterBadge tone="danger">Manquant</PosterBadge>
                ) : watch?.watched ? (
                    <span title="Vu sur une TV" className="flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur">
                        <Check className="h-3 w-3" strokeWidth={3} />
                    </span>
                ) : undefined
            }
            meta={
                <div className="flex flex-wrap items-center gap-1">
                    {hasTech ? <MediaTechBadges specs={item} variant="card" /> : quality && <PosterBadge>{quality}</PosterBadge>}
                    <MediaStateBadges sub={sub} watch={watch} />
                    {item.type === "series" && item.episodes_total ? (
                        <span className="text-[10px] font-medium tabular-nums text-white/85">
                            {item.episodes_have ?? 0}/{item.episodes_total} ép.
                        </span>
                    ) : null}
                    {item.size_bytes > 0 && (
                        <span className="inline-flex items-center gap-1 text-[10px] tabular-nums text-white/70">
                            <HardDrive className="h-2.5 w-2.5" />
                            {formatBytes(item.size_bytes)}
                        </span>
                    )}
                </div>
            }
            selectable={selectable}
            selected={selected}
            onToggleSelect={onToggleSelect}
        />
    );
}

/** En-tête de colonnes de la vue liste (desktop uniquement). */
export function MediaListHeader({ selectable }: { selectable?: boolean }) {
    return (
        <div className="hidden items-center gap-3 px-4 pb-1.5 pt-2.5 text-[12px] font-medium text-muted-foreground md:flex">
            {selectable && <span className="w-5" />}
            <span className="w-10" />
            <span className="min-w-0 flex-1">Titre</span>
            <span className="w-28">Qualité</span>
            <span className="w-20 text-right">Taille</span>
            <span className="w-16 text-center">ST FR</span>
            <span className="w-16 text-center">Vu</span>
            <span className="w-24 text-right">Statut</span>
        </div>
    );
}

export function MediaListRow({ item, sub, watch, selectable, selected, onToggleSelect }: MediaViewProps) {
    const progress = episodeProgress(item);
    const quality = qualityLabel(item);
    const tech = techBadgesOf(item);
    // Mobile (colonne Qualité masquée) : « 4K · DV · Atmos » en texte.
    const qualityText = tech.length > 0 ? tech.map((b) => b.short).join(" · ") : quality;
    const TypeIcon = item.type === "series" ? Tv : Film;

    const content = (
        <>
            {selectable && (
                <span
                    aria-hidden
                    className={cn(
                        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                        selected ? "border-primary bg-primary text-white" : "border-white/30",
                    )}
                >
                    {selected && <Check className="h-3 w-3" strokeWidth={3} />}
                </span>
            )}
            <MediaThumb src={item.poster_url} alt={item.title} type={item.type} className={cn("h-[60px] w-10", !item.has_file && "opacity-60 grayscale-[50%]")} />

            {/* Titre + infos (empilées sur mobile) */}
            <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-medium">{item.title}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                        <TypeIcon className="h-3 w-3" />
                        {item.year ?? "—"}
                    </span>
                    {item.genres.length > 0 && <span className="hidden truncate lg:inline">{item.genres.slice(0, 2).map(translateGenre).join(" · ")}</span>}
                    {/* Infos des colonnes, repliées sous le titre sur mobile */}
                    {qualityText && <span className="md:hidden">{qualityText}</span>}
                    <span className="tabular-nums md:hidden">{item.size_bytes > 0 ? formatBytes(item.size_bytes) : ""}</span>
                    {sub && <span className={cn("md:hidden", sub === "present" ? "text-success" : "text-warning")}>ST FR {sub === "present" ? "✓" : "✗"}</span>}
                    {watch?.watched && <span className="text-foreground/80 md:hidden">Vu</span>}
                </div>
                {typeof progress === "number" && (
                    <div className="mt-1.5 h-1 w-full max-w-[220px] overflow-hidden rounded-full bg-white/[0.12]">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
                    </div>
                )}
            </div>

            <span className="hidden w-28 truncate text-xs md:block">
                {tech.length > 0 ? (
                    <MediaTechBadges specs={item} variant="card" max={2} className="flex-nowrap" />
                ) : quality ? (
                    <span className="rounded-[5px] bg-white/[0.08] px-1.5 py-0.5">{quality}</span>
                ) : (
                    <span className="text-muted-foreground/50">—</span>
                )}
            </span>
            <span className="hidden w-20 text-right text-xs tabular-nums text-muted-foreground md:block">{formatBytes(item.size_bytes)}</span>
            <span className="hidden w-16 text-center text-xs md:block">
                {sub === "present" ? (
                    <span className="text-success">✓</span>
                ) : sub === "missing" ? (
                    <span className="text-warning">✗</span>
                ) : (
                    <span className="text-muted-foreground/40">—</span>
                )}
            </span>
            <span className="hidden w-16 text-center text-xs md:block">
                {watch?.watched ? (
                    <span className="text-foreground/85">Vu</span>
                ) : watch?.progress ? (
                    <span className="tabular-nums text-foreground/85">{watch.progress} %</span>
                ) : (
                    <span className="text-muted-foreground/40">—</span>
                )}
            </span>
            <span className="flex w-auto shrink-0 justify-end md:w-24">
                {item.has_file ? (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-success">
                        {item.monitored ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                        Présent
                    </span>
                ) : (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-destructive">
                        {item.monitored ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                        Manquant
                    </span>
                )}
            </span>
        </>
    );

    const rowClass = cn(
        "group flex w-full items-center gap-3 px-4 py-2 text-left transition-colors duration-150",
        selected ? "bg-primary/[0.14]" : "hover:bg-white/[0.03] active:bg-white/[0.06]",
    );

    return (
        <motion.div variants={fadeIn}>
            {selectable ? (
                <button type="button" onClick={onToggleSelect} aria-pressed={selected} className={rowClass}>
                    {content}
                </button>
            ) : (
                <Link href={mediaHref(item)} className={rowClass}>
                    {content}
                </Link>
            )}
        </motion.div>
    );
}
