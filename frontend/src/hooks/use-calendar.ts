"use client";

import { useQuery } from "@tanstack/react-query";
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
