"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface DashboardStats {
    movies: {
        total: number;
        with_files: number;
        monitored: number;
    };
    series: {
        total: number;
        with_files: number;
        monitored: number;
        total_episodes: number;
        have_episodes: number;
    };
    total_size_bytes: number;
    total_size_human: string;
    total_items: number;
}

export function useDashboardStats() {
    return useQuery<DashboardStats>({
        queryKey: ["dashboard", "stats"],
        queryFn: () => apiFetch("/api/dashboard/stats"),
        staleTime: 60_000,
    });
}
