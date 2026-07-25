"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
    tmdb_id?: number | null;
    order?: number;
}

/* ── Actor filmography (cast click → library + discovery) ───── */

export interface PersonInfo {
    tmdb_id: number;
    name: string;
    photo: string | null;
    biography: string;
    known_for: string;
    birthday: string | null;
    place_of_birth: string | null;
}

export interface PersonMovie {
    tmdb_id: number;
    title: string;
    year: number | null;
    character: string;
    poster: string | null;
    vote_average: number;
    popularity: number;
    /** Present only for in-library entries. */
    radarr_id?: number;
    has_file?: boolean;
}

export interface PersonFilmography {
    person: PersonInfo | null;
    in_library: PersonMovie[];
    discover: PersonMovie[];
    counts: { in_library: number; discover: number };
    error?: string;
}

export function usePersonFilmography(personId: number | null, enabled: boolean) {
    return useQuery<PersonFilmography>({
        queryKey: ["media", "person", personId],
        queryFn: () => apiFetch(`/api/media/person/${personId}`),
        enabled: enabled && !!personId,
        staleTime: 5 * 60_000,
    });
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
    monitored?: boolean;
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
    quality_profile_id?: number | null;
    series_type?: string;
    minimum_availability?: string;
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

export interface RootFolder {
    path: string;
    accessible: boolean;
    freeSpace: number;
    unmappedFolders: any[];
}

export function useMediaRootFolders(type: "movie" | "series", id: string) {
    return useQuery<RootFolder[]>({
        queryKey: ["media", "rootfolders", type, id],
        queryFn: () => apiFetch(`/api/media/${type}/${id}/rootfolders`),
        enabled: !!id,
    });
}

export function useUpdateMediaPath() {
    const queryClient = useQueryClient();
    return useMutation<any, Error, { type: "movie" | "series"; id: string; new_path: string }>({
        mutationFn: ({ type, id, new_path }) =>
            apiFetch(`/api/media/${type}/${id}/path`, {
                method: "PUT",
                body: JSON.stringify({ new_path }),
            }),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", variables.type, variables.id] });
            queryClient.invalidateQueries({ queryKey: ["media"] });
        },
    });
}

// ── Edit media (monitored / quality profile / tags / …) ──────

export interface QualityProfileOption {
    id: number;
    name: string;
}

export interface TagOption {
    id: number;
    label: string;
}

export interface MediaEditOptions {
    quality_profiles: QualityProfileOption[];
    tags: TagOption[];
}

export function useMediaEditOptions(type: "movie" | "series", enabled: boolean) {
    return useQuery<MediaEditOptions>({
        queryKey: ["media", "options", type],
        queryFn: () => apiFetch(`/api/media/options/${type}`),
        enabled,
        staleTime: 300_000,
    });
}

export interface MediaEditPayload {
    monitored?: boolean;
    quality_profile_id?: number;
    tags?: number[];
    minimum_availability?: string;
    series_type?: string;
}

export function useUpdateMedia() {
    const queryClient = useQueryClient();
    return useMutation<any, Error, { type: "movie" | "series"; id: string | number; data: MediaEditPayload }>({
        mutationFn: ({ type, id, data }) =>
            apiFetch(`/api/media/${type}/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", variables.type, String(variables.id)] });
            queryClient.invalidateQueries({ queryKey: ["media"] });
        },
    });
}

export function useCreateTag() {
    const queryClient = useQueryClient();
    return useMutation<TagOption, Error, { type: "movie" | "series"; label: string }>({
        mutationFn: ({ type, label }) =>
            apiFetch(`/api/media/tag/${type}`, {
                method: "POST",
                body: JSON.stringify({ label }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "options", variables.type] });
        },
    });
}

export function useUpdateSeasonMonitoring() {
    const queryClient = useQueryClient();
    return useMutation<any, Error, { id: string | number; season: number; monitored: boolean }>({
        mutationFn: ({ id, season, monitored }) =>
            apiFetch(`/api/media/series/${id}/season/${season}`, {
                method: "PATCH",
                body: JSON.stringify({ monitored }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["media", "detail", "series", String(variables.id)] });
            queryClient.invalidateQueries({ queryKey: ["media"] });
        },
    });
}
