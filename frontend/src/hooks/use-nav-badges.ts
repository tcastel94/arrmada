"use client";

/**
 * Compteurs affichés dans la navigation (sidebar, barre mobile, header).
 * Réutilise les mêmes clés de cache React Query que les pages : pas de
 * requête en double, juste un rafraîchissement plus espacé ici.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { DownloadsResponse } from "@/hooks/use-downloads";
import type { MediaFacets } from "@/hooks/use-media";

export function useNavBadges() {
    const downloads = useQuery<DownloadsResponse>({
        queryKey: ["downloads"],
        queryFn: () => apiFetch("/api/downloads"),
        refetchInterval: 30_000,
        staleTime: 10_000,
    });
    const unread = useQuery<{ unread_count: number }>({
        queryKey: ["notifications", "count"],
        queryFn: () => apiFetch("/api/notifications/count"),
        refetchInterval: 30_000,
    });
    const facets = useQuery<MediaFacets>({
        queryKey: ["media", "facets"],
        queryFn: () => apiFetch("/api/media/facets"),
        staleTime: 5 * 60_000,
    });

    return {
        downloads: downloads.data?.total ?? downloads.data?.items?.length ?? 0,
        notifications: unread.data?.unread_count ?? 0,
        missing: facets.data?.missing_monitored_count ?? facets.data?.missing_count ?? 0,
    };
}
