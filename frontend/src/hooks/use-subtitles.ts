"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Default subtitle language tracked across the UI. */
export const DEFAULT_SUB_LANG = "fr";

/* ── Types ─────────────────────────────────────────────────── */

export interface SubtitleTrack {
    language: string;
    code2: string;
    code3?: string;
    path?: string | null;
    forced: boolean;
    hi: boolean;
}

/** Movie subtitle block returned in MediaDetail.subtitles (single element). */
export interface MovieSubtitleInfo {
    radarr_id: number;
    subtitles: SubtitleTrack[];
    missing: SubtitleTrack[];
}

/** Per-episode subtitle block returned in MediaDetail.subtitles for a series. */
export interface EpisodeSubtitleInfo {
    episode_id: number;
    season: number;
    episode: number;
    title: string;
    monitored: boolean;
    subtitles: SubtitleTrack[];
    missing: SubtitleTrack[];
}

/** A candidate subtitle from a provider (interactive search). */
export interface ProviderSubtitle {
    subtitle: string;
    provider: string;
    language: string;
    release_info: string;
    score: number | null;
    uploader: string | null;
    url: string | null;
    original_format: string;
    hi: boolean;
    forced: boolean;
}

export interface SeriesSubStatus {
    state: "missing";
    missing_episodes: number;
}

export interface SubtitleStatusResponse {
    language: string;
    available: boolean;
    /** radarrId → "present" | "missing" */
    movies: Record<string, "present" | "missing">;
    /** sonarrSeriesId → status */
    series: Record<string, SeriesSubStatus>;
}

/* ── Library-wide status (badges + filter) ─────────────────── */

export function useSubtitleStatus(language: string = DEFAULT_SUB_LANG, enabled = true) {
    return useQuery<SubtitleStatusResponse>({
        queryKey: ["subtitles", "status", language],
        queryFn: () => apiFetch(`/api/subtitles/status?language=${language}`),
        enabled,
        staleTime: 60_000,
    });
}

/* ── Automatic (one-click) download ────────────────────────── */

interface AutoArgs {
    language?: string;
    forced?: boolean;
    hi?: boolean;
}

function autoQs({ language = DEFAULT_SUB_LANG, forced = false, hi = false }: AutoArgs) {
    return `?language=${language}&forced=${forced}&hi=${hi}`;
}

/** Ask Bazarr to auto-download the best subtitle for a movie. */
export function useAutoDownloadMovieSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { radarrId: number | string } & AutoArgs
    >({
        mutationFn: ({ radarrId, ...args }) =>
            apiFetch(`/api/subtitles/movie/${radarrId}/search${autoQs(args)}`, {
                method: "POST",
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "movie"] });
        },
    });
}

/** Ask Bazarr to auto-download the best subtitle for a single episode. */
export function useAutoDownloadEpisodeSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { seriesId: number | string; episodeId: number } & AutoArgs
    >({
        mutationFn: ({ seriesId, episodeId, ...args }) =>
            apiFetch(
                `/api/subtitles/episode/${seriesId}/${episodeId}/search${autoQs(args)}`,
                { method: "POST" },
            ),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "series"] });
        },
    });
}

/** Auto-download every missing subtitle across a whole series. */
export function useAutoDownloadSeriesSubs() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; triggered: number },
        Error,
        { seriesId: number | string } & AutoArgs
    >({
        mutationFn: ({ seriesId, ...args }) =>
            apiFetch(`/api/subtitles/series/${seriesId}/search${autoQs(args)}`, {
                method: "POST",
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "series"] });
        },
    });
}

/* ── Interactive provider search ───────────────────────────── */

export function useMovieSubProviders(radarrId: number | string, enabled: boolean) {
    return useQuery<{ items: ProviderSubtitle[]; total: number }>({
        queryKey: ["subtitles", "providers", "movie", String(radarrId)],
        queryFn: () => apiFetch(`/api/subtitles/movie/${radarrId}/providers`),
        enabled: enabled && !!radarrId,
        staleTime: 60_000,
        retry: false,
    });
}

export function useEpisodeSubProviders(episodeId: number | null, enabled: boolean) {
    return useQuery<{ items: ProviderSubtitle[]; total: number }>({
        queryKey: ["subtitles", "providers", "episode", String(episodeId)],
        queryFn: () => apiFetch(`/api/subtitles/episode/${episodeId}/providers`),
        enabled: enabled && !!episodeId,
        staleTime: 60_000,
        retry: false,
    });
}

/* ── Download a chosen provider subtitle ───────────────────── */

function providerBody(s: ProviderSubtitle) {
    return JSON.stringify({
        subtitle: s.subtitle,
        provider: s.provider,
        original_format: s.original_format,
        hi: s.hi,
        forced: s.forced,
    });
}

export function useDownloadMovieProviderSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { radarrId: number | string; sub: ProviderSubtitle }
    >({
        mutationFn: ({ radarrId, sub }) =>
            apiFetch(`/api/subtitles/movie/${radarrId}/download`, {
                method: "POST",
                body: providerBody(sub),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "movie"] });
        },
    });
}

export function useDownloadEpisodeProviderSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { seriesId: number | string; episodeId: number; sub: ProviderSubtitle }
    >({
        mutationFn: ({ seriesId, episodeId, sub }) =>
            apiFetch(`/api/subtitles/episode/${seriesId}/${episodeId}/download`, {
                method: "POST",
                body: providerBody(sub),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "series"] });
        },
    });
}

/* ── Delete a subtitle file ────────────────────────────────── */

export function useDeleteMovieSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { radarrId: number | string; track: SubtitleTrack }
    >({
        mutationFn: ({ radarrId, track }) =>
            apiFetch(`/api/subtitles/movie/${radarrId}`, {
                method: "DELETE",
                body: JSON.stringify({
                    language: track.code2,
                    path: track.path ?? "",
                    forced: track.forced,
                    hi: track.hi,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "movie"] });
        },
    });
}

/* ── Synchronise a subtitle to the video (ffsubsync, audio ref) ── */

export function useSyncMovieSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { radarrId: number | string; track: SubtitleTrack }
    >({
        mutationFn: ({ radarrId, track }) =>
            apiFetch(`/api/subtitles/movie/${radarrId}/sync`, {
                method: "POST",
                body: JSON.stringify({
                    path: track.path ?? "",
                    language: track.code2,
                    forced: track.forced,
                    hi: track.hi,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["media", "detail", "movie"] });
        },
    });
}

export function useSyncEpisodeSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { seriesId: number | string; episodeId: number; track: SubtitleTrack }
    >({
        mutationFn: ({ seriesId, episodeId, track }) =>
            apiFetch(`/api/subtitles/episode/${seriesId}/${episodeId}/sync`, {
                method: "POST",
                body: JSON.stringify({
                    path: track.path ?? "",
                    language: track.code2,
                    forced: track.forced,
                    hi: track.hi,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["media", "detail", "series"] });
        },
    });
}

export function useDeleteEpisodeSub() {
    const qc = useQueryClient();
    return useMutation<
        { status: string },
        Error,
        { seriesId: number | string; episodeId: number; track: SubtitleTrack }
    >({
        mutationFn: ({ seriesId, episodeId, track }) =>
            apiFetch(`/api/subtitles/episode/${seriesId}/${episodeId}`, {
                method: "DELETE",
                body: JSON.stringify({
                    language: track.code2,
                    path: track.path ?? "",
                    forced: track.forced,
                    hi: track.hi,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["subtitles", "status"] });
            qc.invalidateQueries({ queryKey: ["media", "detail", "series"] });
        },
    });
}
