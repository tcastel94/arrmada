"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface DownloadItem {
    id: number;
    title: string;
    status: string;
    progress: number;
    size_bytes: number;
    size_left_bytes: number;
    time_left: string | null;
    source_service: string;
    service_type: string;
    download_client: string;
    indexer: string;
    quality: string;
}

export interface DownloadsResponse {
    items: DownloadItem[];
    total: number;
}

export function useDownloads() {
    return useQuery<DownloadsResponse>({
        queryKey: ["downloads"],
        queryFn: () => apiFetch("/api/downloads"),
        refetchInterval: 10_000, // Refresh every 10s for active downloads
    });
}
