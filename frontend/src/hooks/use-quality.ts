"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

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
