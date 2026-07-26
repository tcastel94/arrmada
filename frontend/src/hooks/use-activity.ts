"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Dashboard activity feed (Radarr/Sonarr history widget) ──── */

export interface ActivityItem {
    id: string;
    event_type: string;
    event_label: string;
    source: "sonarr" | "radarr";
    title: string;
    subtitle: string;
    quality: string | null;
    languages: string | null;
    date: string;
    timestamp: number;
    icon_type: string;
    status: "success" | "warning" | "error" | "info";
    size_bytes: number | null;
    indexer: string | null;
    download_client: string | null;
    poster_url: string | null;
}

export interface ActivityFeed {
    items: ActivityItem[];
    total: number;
    has_more: boolean;
}

export function useActivityFeed(limit: number = 30) {
    return useQuery<ActivityFeed>({
        queryKey: ["dashboard", "activity", limit],
        queryFn: () => apiFetch(`/api/dashboard/activity?limit=${limit}`),
        refetchInterval: 30_000,
    });
}

/* ── Unified activity timeline (persisted events + *arr history) ─ */

export interface TimelineItem {
    id: string;
    ts: number; // epoch seconds
    category: string; // download | subtitle | playback | library | telegram | system
    action: string;
    status: "ok" | "ko" | "info";
    source: string; // arrmada | kodi | radarr | sonarr | bazarr | telegram
    media_type: string | null;
    media_id: string | null;
    tmdb_id: number | null;
    title: string | null;
    subtitle: string | null;
    detail: string | null;
    duration_ms: number | null;
    device: string | null;
    size_bytes?: number | null;
    poster_url?: string | null;
}

export interface TimelineGroup {
    key: string;
    title: string;
    media_type: string | null;
    media_id: string | null;
    tmdb_id: number | null;
    poster_url: string | null;
    count: number;
    last_ts: number;
    items: TimelineItem[];
}

export interface TimelineResponse {
    items?: TimelineItem[];
    groups?: TimelineGroup[];
    total: number;
    grouped: boolean;
}

export interface TimelineFilters {
    categories?: string[];
    statuses?: string[];
    source?: string;
    search?: string;
    group?: "none" | "media";
    limit?: number;
}

export function useActivityTimeline(filters: TimelineFilters) {
    const qs = new URLSearchParams();
    if (filters.categories?.length) qs.set("categories", filters.categories.join(","));
    if (filters.statuses?.length) qs.set("statuses", filters.statuses.join(","));
    if (filters.source) qs.set("source", filters.source);
    if (filters.search) qs.set("search", filters.search);
    if (filters.group) qs.set("group", filters.group);
    qs.set("limit", String(filters.limit ?? 200));

    return useQuery<TimelineResponse>({
        queryKey: ["activity", "timeline", filters],
        queryFn: () => apiFetch(`/api/activity/timeline?${qs.toString()}`),
        refetchInterval: 20_000,
    });
}
