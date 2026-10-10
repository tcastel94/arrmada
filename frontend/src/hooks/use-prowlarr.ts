"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

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
