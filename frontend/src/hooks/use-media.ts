"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface MediaItem {
    external_id: string;
    tmdb_id: number | null;
    title: string;
    type: "movie" | "series";
    year: number | null;
    genres: string[];
    quality: string | null;
    size_bytes: number;
    poster_url: string | null;
    source_service: string;
    has_file: boolean;
    monitored: boolean;
    status: string;
    added: string | null;
    rating: number | null;
    runtime: number | null;
    overview: string;
    seasons?: number;
    episodes_total?: number;
    episodes_have?: number;
}

export interface MediaResponse {
    items: MediaItem[];
    pagination: {
        page: number;
        per_page: number;
        total: number;
        total_pages: number;
    };
}

export interface SearchResponse {
    items: MediaItem[];
    total: number;
}

export function useMedia(params: {
    type?: string;
    search?: string;
    sort?: string;
    order?: string;
    page?: number;
    per_page?: number;
}) {
    const searchParams = new URLSearchParams();
    if (params.type) searchParams.set("type", params.type);
    if (params.search) searchParams.set("search", params.search);
    if (params.sort) searchParams.set("sort", params.sort);
    if (params.order) searchParams.set("order", params.order);
    if (params.page) searchParams.set("page", String(params.page));
    if (params.per_page) searchParams.set("per_page", String(params.per_page));

    const qs = searchParams.toString();

    return useQuery<MediaResponse>({
        queryKey: ["media", params],
        queryFn: () => apiFetch(`/api/media${qs ? `?${qs}` : ""}`),
    });
}

export function useMediaSearch(query: string) {
    return useQuery<SearchResponse>({
        queryKey: ["media", "search", query],
        queryFn: () => apiFetch(`/api/media/search?q=${encodeURIComponent(query)}`),
        enabled: query.length >= 2,
    });
}

// ── Detail types ─────────────────────────────────────────────

export interface FileInfo {
    id: number;
    relative_path: string;
    path: string;
    size_bytes: number;
    quality: string;
    quality_source: string;
    resolution: string;
    video_codec: string;
    video_dynamic_range: string;
    video_dynamic_range_type: string;
    audio_codec: string;
    audio_channels: number;
    audio_languages: string;
    subtitle_languages: string;
    run_time: string;
    release_group: string;
    edition: string;
    languages: string[];
    date_added: string | null;
}

export interface CastMember {
    name: string;
    character: string;
    type: string;
    photo?: string;
}

export interface SubtitleInfo {
    language: string;
    code2: string;
    code3?: string;
    path?: string;
    forced: boolean;
    hi: boolean;
}

export interface EpisodeDetail {
    id: number;
    episode_number: number;
    season_number: number;
    title: string;
    overview: string;
    air_date: string | null;
    has_file: boolean;
    monitored: boolean;
    file: FileInfo | null;
}

export interface SeasonDetail {
    season_number: number;
    episode_count: number;
    episodes_have: number;
    episodes: EpisodeDetail[];
}

export interface MediaDetail {
    id: number;
    type: "movie" | "series";
    title: string;
    original_title: string;
    year: number | null;
    overview: string;
    studio?: string;
    network?: string;
    genres: string[];
    runtime: number | null;
    status: string;
    monitored: boolean;
    has_file?: boolean;
    size_on_disk: number;
    added: string | null;
    path: string;
    certification: string;
    youtube_trailer_id?: string;
    tmdb_id?: number;
    imdb_id?: string;
    tvdb_id?: number;
    ratings: Record<string, number | null>;
    images: { poster: string | null; fanart: string | null; banner: string | null };
    file?: FileInfo | null;
    seasons?: SeasonDetail[];
    season_count?: number;
    total_episodes?: number;
    episodes_have?: number;
    cast?: CastMember[];
    crew?: CastMember[];
    subtitles: any[];
    tags: number[];
    error?: string;
}

export function useMediaDetail(type: "movie" | "series", id: string) {
    return useQuery<MediaDetail>({
        queryKey: ["media", "detail", type, id],
        queryFn: () => apiFetch(`/api/media/${type}/${id}`),
        enabled: !!id,
    });
}
