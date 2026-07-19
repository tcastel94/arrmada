"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Calendar ──────────────────────────────────────────────── */

export interface CalendarEntry {
  id: string;
  title: string;
  subtitle: string;
  type: "episode" | "movie";
  season?: number;
  episode?: number;
  label: string;
  air_date: string;
  has_file: boolean;
  monitored: boolean;
  poster_url?: string;
  overview: string;
  service: string;
  service_type: string;
}

export function useCalendar(days = 30) {
  return useQuery<{
    items: CalendarEntry[];
    by_date: Record<string, CalendarEntry[]>;
    total: number;
  }>({
    queryKey: ["calendar", days],
    queryFn: () => apiFetch(`/api/calendar?days=${days}`),
    staleTime: 300_000,
  });
}

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

/* ── Prowlarr Stats ────────────────────────────────────────── */

export interface IndexerStat {
  indexer_id: number;
  indexer_name: string;
  queries: number;
  grabs: number;
  failed_queries: number;
  failed_grabs: number;
  success_rate: number;
  grab_rate: number;
  avg_response_time: number;
  source: string;
}

export interface ProwlarrIndexer {
  id: number;
  name: string;
  protocol: string;
  privacy: string;
  enable: boolean;
  status_messages: { title?: string; message?: string }[];
  priority: number;
  tags: number[];
  source: string;
}

export function useProwlarrStats() {
  return useQuery<{
    indexers: ProwlarrIndexer[];
    stats: IndexerStat[];
    summary: {
      total_indexers: number;
      enabled_indexers: number;
      total_queries: number;
      total_grabs: number;
      average_success_rate: number;
      problematic: IndexerStat[];
    };
  }>({
    queryKey: ["prowlarr", "stats"],
    queryFn: () => apiFetch("/api/prowlarr/stats"),
    staleTime: 600_000,
  });
}

/* ── Prowlarr indexer management ───────────────────────────── */

export function useTestIndexer() {
  return useMutation<
    { ok: boolean; status_code: number; errors?: unknown },
    Error,
    { id: number }
  >({
    mutationFn: ({ id }) =>
      apiFetch(`/api/prowlarr/indexers/${id}/test`, { method: "POST" }),
  });
}

export function useToggleIndexer() {
  const queryClient = useQueryClient();
  return useMutation<
    { status: string; id: number; enable: boolean },
    Error,
    { id: number; enable: boolean }
  >({
    mutationFn: ({ id, enable }) =>
      apiFetch(`/api/prowlarr/indexers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enable }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prowlarr", "stats"] });
    },
  });
}

export function useDeleteIndexer() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; id: number }, Error, { id: number }>({
    mutationFn: ({ id }) =>
      apiFetch(`/api/prowlarr/indexers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prowlarr", "stats"] });
    },
  });
}

/* ── Quality Upgrade Tracker ───────────────────────────────── */

export interface UpgradeableItem {
  title: string;
  year?: number;
  type: string;
  quality: string;
  quality_tier: number;
  size_bytes: number;
  size_human: string;
  profile: string;
  service: string;
}

export function useQualityOverview() {
  return useQuery<{
    movies: {
      total: number;
      quality_distribution: Record<string, { count: number; percent: number }>;
      resolution_distribution: Record<string, { count: number; percent: number }>;
    };
    series: { total: number; total_episodes: number };
    upgradeable: {
      count: number;
      items: UpgradeableItem[];
      total_current_size: string;
      estimated_space_needed: string;
    };
  }>({
    queryKey: ["quality", "overview"],
    queryFn: () => apiFetch("/api/quality"),
    staleTime: 600_000,
  });
}

/* ── Smart Cleanup ─────────────────────────────────────────── */

export interface CleanupItem {
  title: string;
  year?: number;
  type: string;
  quality?: string;
  size_bytes: number;
  size_human: string;
  poster_url?: string;
  service: string;
  reason: string;
  suggestion: string;
}

export function useCleanupScan() {
  return useQuery<{
    unmonitored: { items: CleanupItem[]; total: number; reclaimable_human: string };
    low_quality: { items: CleanupItem[]; total: number };
    oversized: { items: CleanupItem[]; total: number };
    incomplete_ended: { items: CleanupItem[]; total: number };
    summary: {
      total_issues: number;
      total_reclaimable_bytes: number;
      total_reclaimable_human: string;
    };
  }>({
    queryKey: ["cleanup", "scan"],
    queryFn: () => apiFetch("/api/cleanup"),
    staleTime: 600_000,
  });
}

/* ── TMDB Recommendations ──────────────────────────────────── */

export interface TMDBItem {
  tmdb_id: number;
  title: string;
  type: string;
  year?: string;
  overview: string;
  rating?: number;
  poster_url?: string;
  backdrop_url?: string;
  in_library?: boolean;
}

export function useRecommendations() {
  return useQuery<{
    trending_movies: TMDBItem[];
    trending_series: TMDBItem[];
    because_you_have: {
      base_title: string;
      base_poster?: string;
      recommendations: TMDBItem[];
    }[];
    wanted: Record<string, unknown>[];
    tmdb_available: boolean;
  }>({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch("/api/recommendations"),
    staleTime: 3600_000,
  });
}
