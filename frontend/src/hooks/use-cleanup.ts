"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

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
