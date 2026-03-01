"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

// ── SABnzbd History ──────────────────────────────────────────

export interface StageAction {
    stage: string;
    actions: string[];
}

export interface HistoryItem {
    nzo_id: string;
    name: string;
    status: string;
    category: string;
    size_bytes: number;
    size_human: string;
    completed_at: number | null;
    storage_path: string;
    download_path: string;
    stage_log: StageAction[];
    fail_message: string;
    script_log: string;
    has_been_moved: boolean;
    is_stuck: boolean;
}

export interface HistoryResponse {
    items: HistoryItem[];
    total: number;
    stuck_count: number;
}

export function useSabnzbdHistory(limit = 50) {
    return useQuery<HistoryResponse>({
        queryKey: ["sabnzbd-history", limit],
        queryFn: () => apiFetch(`/api/files/history?limit=${limit}`),
    });
}

// ── Docker ───────────────────────────────────────────────────

export interface DockerContainer {
    name: string;
    status: string;
    image: string;
    id: string;
    ports?: string[];
    service_name?: string;
    service_type?: string;
    service_url?: string;
    status_text?: string;
    state_raw?: string;
}

export interface DockerResponse {
    containers: DockerContainer[];
    total: number;
    running: number;
}

export function useDockerContainers() {
    return useQuery<DockerResponse>({
        queryKey: ["docker-containers"],
        queryFn: () => apiFetch("/api/files/docker"),
        refetchInterval: 15_000,
    });
}

export function useDockerAction() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: { container_id: string; action: string }) =>
            apiFetch("/api/files/docker/action", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["docker-containers"] });
        },
    });
}

// ── NAS Paths ────────────────────────────────────────────────

export interface PathMappings {
    service_mounts: Record<string, Array<{ host: string; container: string; rw: boolean }>>;
    downloads_host_path: string;
    movies_host_path: string;
    series_host_path: string;
}

export function usePathMappings() {
    return useQuery<PathMappings>({
        queryKey: ["path-mappings"],
        queryFn: () => apiFetch("/api/files/paths"),
    });
}

// ── Stuck Downloads ──────────────────────────────────────────

export interface StuckDownload {
    nzo_id: string;
    name: string;
    category: string;
    media_type: string;
    size_human: string;
    storage_path: string;
    completed: number | null;
}

export interface StuckResponse {
    items: StuckDownload[];
    total: number;
}

export function useStuckDownloads() {
    return useQuery<StuckResponse>({
        queryKey: ["stuck-downloads"],
        queryFn: () => apiFetch("/api/files/stuck"),
    });
}

// ── Manual Import ────────────────────────────────────────────

export interface ImportResponse {
    success: boolean;
    service?: string;
    command_id?: number;
    files_count?: number;
    message?: string;
    error?: string;
    candidates_total?: number;
}

export function useManualImport() {
    const queryClient = useQueryClient();
    return useMutation<ImportResponse, Error, { download_path: string; media_type: string }>({
        mutationFn: (payload) =>
            apiFetch("/api/files/import", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["stuck-downloads"] });
            queryClient.invalidateQueries({ queryKey: ["sabnzbd-history"] });
        },
    });
}
