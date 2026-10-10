"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── System Monitor ────────────────────────────────────────── */

export interface DiskInfo {
  path: string;
  label: string;
  total_bytes: number;
  free_bytes: number;
  used_bytes: number;
  total_human: string;
  free_human: string;
  used_human: string;
  usage_percent: number;
  source_service: string;
}

export interface KodiSession {
  instance: string;
  title: string;
  type: string;
  year?: number;
  progress_percent: number;
  is_paused: boolean;
  elapsed_seconds: number;
  total_seconds: number;
  thumbnail: string;
}

export function useSystemOverview() {
  return useQuery<{
    disks: DiskInfo[];
    resources: Record<string, unknown>;
    kodi_sessions: KodiSession[];
    kodi_active: number;
  }>({
    queryKey: ["system", "overview"],
    queryFn: () => apiFetch("/api/system/overview"),
    staleTime: 120_000,
  });
}

export function useDiskSpace() {
  return useQuery<{ disks: DiskInfo[] }>({
    queryKey: ["system", "disk"],
    queryFn: () => apiFetch("/api/system/disk"),
    staleTime: 120_000,
  });
}

export function useKodiSessions() {
  return useQuery<{ sessions: KodiSession[]; active: number }>({
    queryKey: ["system", "kodi"],
    queryFn: () => apiFetch("/api/system/kodi/sessions"),
    refetchInterval: 15_000, // Refresh every 15s for live playback
  });
}
