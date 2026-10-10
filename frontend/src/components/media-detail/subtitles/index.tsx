"use client";

/**
 * Onglet « Sous-titres » : aiguille vers le panneau film ou série selon la
 * forme des données Bazarr (un bloc unique pour un film, un bloc par
 * épisode pour une série).
 */
import { Subtitles } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import type { MediaDetail } from "@/hooks/use-media";
import type { EpisodeSubtitleInfo, MovieSubtitleInfo } from "@/hooks/use-subtitles";
import { MovieSubtitlePanel } from "./movie-panel";
import { SeriesSubtitlePanel } from "./series-panel";

const isEpisodeBlock = (b: MovieSubtitleInfo | EpisodeSubtitleInfo): b is EpisodeSubtitleInfo => "episode_id" in b;
const isMovieBlock = (b: MovieSubtitleInfo | EpisodeSubtitleInfo): b is MovieSubtitleInfo => "radarr_id" in b || !("episode_id" in b);

/** Nombre d'épisodes / films sans sous-titre FR (pastille de l'onglet). */
export function countMissingFr(media: MediaDetail, lang = "fr"): number {
    const blocks = media.subtitles ?? [];
    if (media.type === "movie") {
        const b = blocks.find(isMovieBlock);
        return b && !b.subtitles.some((s) => s.code2 === lang) ? 1 : 0;
    }
    return blocks.filter(isEpisodeBlock).filter((e) => !e.subtitles.some((s) => s.code2 === lang)).length;
}

export function SubtitlesTab({ media }: { media: MediaDetail }) {
    const blocks = media.subtitles ?? [];
    const empty = (
        <EmptyState
            icon={Subtitles}
            title="Aucune information de sous-titres"
            description={`Vérifie que ce ${media.type === "movie" ? "film" : "titre"} est suivi par Bazarr et qu'un fichier vidéo est présent.`}
        />
    );

    if (media.type === "movie") {
        const block = blocks.find(isMovieBlock);
        return block ? <MovieSubtitlePanel media={media} block={block} /> : empty;
    }
    const episodes = blocks.filter(isEpisodeBlock);
    return episodes.length > 0 ? <SeriesSubtitlePanel media={media} episodes={episodes} /> : empty;
}
