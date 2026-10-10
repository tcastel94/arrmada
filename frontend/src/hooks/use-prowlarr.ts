"use client";

/**
 * Indexers Prowlarr : statistiques + gestion (tester, activer, supprimer).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export const PROWLARR_STATS_KEY = ["prowlarr", "stats"] as const;

/** Statistiques d'un indexer sur la période gardée par Prowlarr. */
export interface IndexerStat {
    indexer_id: number;
    indexer_name: string;
    queries: number;
    /** « Grabs » Prowlarr = releases envoyées au client de téléchargement. */
    grabs: number;
    failed_queries: number;
    failed_grabs: number;
    /**
     * % de requêtes réussies. `null` quand l'indexer n'a reçu aucune
     * requête (avant correctif backend : 0, affiché à tort en rouge).
     */
    success_rate: number | null;
    /** % de récupérations réussies (`null` si aucune récupération). */
    grab_rate: number | null;
    /** Millisecondes. */
    avg_response_time: number;
    /** Nom de l'instance Prowlarr. */
    source: string;
}

export interface IndexerStatusMessage {
    title?: string;
    message?: string;
}

export interface ProwlarrIndexer {
    id: number;
    name: string;
    /** torrent | usenet */
    protocol: string;
    /** public | semiPrivate | private */
    privacy: string;
    enable: boolean;
    /** Messages d'erreur remontés par Prowlarr (indexer en échec, désactivé temporairement…). */
    status_messages: IndexerStatusMessage[];
    priority: number;
    tags: number[];
    source: string;
}

export interface ProwlarrSummary {
    total_indexers: number;
    enabled_indexers: number;
    total_queries: number;
    total_grabs: number;
    total_failed_queries?: number;
    average_success_rate: number;
    /** Indexers avec un taux de succès < 80 %. */
    problematic: IndexerStat[];
}

export interface ProwlarrStatsResponse {
    indexers: ProwlarrIndexer[];
    stats: IndexerStat[];
    summary: ProwlarrSummary;
}

export function useProwlarrStats() {
    return useQuery<ProwlarrStatsResponse>({
        queryKey: PROWLARR_STATS_KEY,
        queryFn: () => apiFetch<ProwlarrStatsResponse>("/api/prowlarr/stats"),
        staleTime: 600_000,
    });
}

/* ── Gestion des indexers ──────────────────────────────────── */

/** Erreur de validation renvoyée par Prowlarr lors d'un test. */
export interface IndexerTestError {
    propertyName?: string;
    errorMessage?: string;
    severity?: string;
}

export interface IndexerTestResult {
    ok: boolean;
    status_code: number;
    errors?: IndexerTestError[] | string | Record<string, unknown>;
}

/**
 * Teste un indexer. Un test peut changer son état (Prowlarr réactive un
 * indexer qui répond de nouveau) → on relit les stats après coup.
 * `skipRefresh` : pour « Tester tout », on ne relit qu'une fois à la fin
 * au lieu d'une relecture complète après chaque indexer.
 */
export function useTestIndexer() {
    const qc = useQueryClient();
    return useMutation<IndexerTestResult, Error, { id: number; skipRefresh?: boolean }>({
        mutationFn: ({ id }) => apiFetch<IndexerTestResult>(`/api/prowlarr/indexers/${id}/test`, { method: "POST" }),
        onSettled: (_res, _err, vars) => {
            if (!vars.skipRefresh) qc.invalidateQueries({ queryKey: PROWLARR_STATS_KEY });
        },
    });
}

export function useToggleIndexer() {
    const qc = useQueryClient();
    return useMutation<{ status: string; id: number; enable: boolean }, Error, { id: number; enable: boolean }>({
        mutationFn: ({ id, enable }) =>
            apiFetch(`/api/prowlarr/indexers/${id}`, {
                method: "PATCH",
                body: JSON.stringify({ enable }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: PROWLARR_STATS_KEY });
        },
    });
}

export function useDeleteIndexer() {
    const qc = useQueryClient();
    return useMutation<{ status: string; id: number }, Error, { id: number }>({
        mutationFn: ({ id }) => apiFetch(`/api/prowlarr/indexers/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: PROWLARR_STATS_KEY });
        },
    });
}
