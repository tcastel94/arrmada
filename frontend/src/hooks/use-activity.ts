"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ActivityItem {
    id: string;
    event_type: string;
    source: "sonarr" | "radarr";
    title: string;
    subtitle: string;
    quality: string | null;
    date: string;
    timestamp: number;
    icon_type: string;
    status: "success" | "warning" | "error" | "info";
    size_bytes: number | null;
    indexer: string | null;
    download_client: string | null;
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
        refetchInterval: 30_000, // Auto-refresh every 30s
    });
}
