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
import { StudioNetworkLogo } from "@/components/media/studio-network-logo";

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
    const progress = episodeProgress(item);
    const quality = qualityLabel(item);
    const isMovie = item.type === "movie";
    const hasTech = techBadgesOf(item).length > 0;
    return (
        <PosterCard
            title={item.title}
            subtitle={
                // Studio / chaîne en pastille discrète à droite, tronquée si le nom est long.
                <span className="flex min-w-0 items-center justify-between gap-1.5">
                    <span className="shrink-0">
                        {item.year ?? "—"} · {isMovie ? "Film" : "Série"}
                    </span>
                    <StudioNetworkLogo
                        name={isMovie ? item.studio : item.network}
                        kind={isMovie ? "studio" : "network"}
                        variant="mini"
                        className="max-w-[60%]"
                    />
                </span>
            }
            posterUrl={item.poster_url}
            type={item.type}
            href={mediaHref(item)}
            dimmed={!item.has_file}
            progress={progress}
            badges={
                <>
                    {hasTech ? <MediaTechBadges specs={item} variant="card" /> : quality && <PosterBadge>{quality}</PosterBadge>}
                    <MediaStateBadges sub={sub} watch={watch} />
                </>
            }
            corner={!item.has_file ? <PosterBadge tone="danger">Manquant</PosterBadge> : undefined}
            meta={
                <div className="flex flex-wrap items-center gap-1">
                    {item.type === "series" && item.episodes_total ? (
                        <span className="rounded bg-primary/25 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-white">
                            {item.episodes_have ?? 0}/{item.episodes_total} ép.
                        </span>
                    ) : null}
                    {item.genres.slice(0, 3).map((g) => (
                        <span key={g} className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-white/80 backdrop-blur">
                            {translateGenre(g)}
                        </span>
                    ))}
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
        <div className="hidden items-center gap-3 px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/60 md:flex">
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
                        "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-colors",
                        selected ? "border-primary bg-primary text-primary-foreground" : "border-white/30",
                    )}
                >
                    {selected && <Check className="h-3 w-3" strokeWidth={3} />}
                </span>
            )}
            <MediaThumb src={item.poster_url} alt={item.title} type={item.type} className={cn("h-[60px] w-10", !item.has_file && "opacity-60 grayscale-[50%]")} />

            {/* Titre + infos (empilées sur mobile) */}
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold transition-colors group-hover:text-primary">{item.title}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                        <TypeIcon className="h-3 w-3" />
                        {item.year ?? "—"}
                    </span>
                    {item.genres.length > 0 && <span className="hidden truncate lg:inline">{item.genres.slice(0, 2).map(translateGenre).join(" · ")}</span>}
                    {/* Infos des colonnes, repliées sous le titre sur mobile */}
                    {qualityText && <span className="md:hidden">{qualityText}</span>}
                    <span className="tabular-nums md:hidden">{item.size_bytes > 0 ? formatBytes(item.size_bytes) : ""}</span>
                    {sub && <span className={cn("md:hidden", sub === "present" ? "text-emerald-400" : "text-amber-400")}>ST FR {sub === "present" ? "✓" : "✗"}</span>}
                    {watch?.watched && <span className="text-violet-300 md:hidden">Vu</span>}
                </div>
                {typeof progress === "number" && (
                    <div className="mt-1.5 h-1 w-full max-w-[220px] overflow-hidden rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-gradient-to-r from-primary to-brand" style={{ width: `${progress}%` }} />
                    </div>
                )}
            </div>

            <span className="hidden w-28 truncate text-xs md:block">
                {tech.length > 0 ? (
                    <MediaTechBadges specs={item} variant="card" max={2} className="flex-nowrap" />
                ) : quality ? (
                    <span className="rounded-md bg-white/[0.05] px-1.5 py-0.5 ring-1 ring-white/[0.08]">{quality}</span>
                ) : (
                    <span className="text-muted-foreground/50">—</span>
                )}
            </span>
            <span className="hidden w-20 text-right text-xs tabular-nums text-muted-foreground md:block">{formatBytes(item.size_bytes)}</span>
            <span className="hidden w-16 text-center text-xs md:block">
                {sub === "present" ? (
                    <span className="text-emerald-400">✓</span>
                ) : sub === "missing" ? (
                    <span className="text-amber-400">✗</span>
                ) : (
                    <span className="text-muted-foreground/40">—</span>
                )}
            </span>
            <span className="hidden w-16 text-center text-xs md:block">
                {watch?.watched ? (
                    <span className="text-violet-300">Vu</span>
                ) : watch?.progress ? (
                    <span className="tabular-nums text-violet-300">{watch.progress} %</span>
                ) : (
                    <span className="text-muted-foreground/40">—</span>
                )}
            </span>
            <span className="flex w-auto shrink-0 justify-end md:w-24">
                {item.has_file ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 ring-1 ring-emerald-500/25">
                        {item.monitored ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                        Présent
                    </span>
                ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-medium text-red-400 ring-1 ring-red-500/25">
                        {item.monitored ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                        Manquant
                    </span>
                )}
            </span>
        </>
    );

    const rowClass = cn(
        "group flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-all duration-300 ease-smooth",
        selected
            ? "bg-primary/10 ring-1 ring-primary/40"
            : "ring-1 ring-transparent hover:bg-white/[0.04] hover:ring-white/[0.08]",
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
