"use client";

/**
 * File de téléchargement unifiée (Radarr + Sonarr) et actions associées.
 * ----------------------------------------------------------------
 * - `useDownloads()` : la file, rafraîchie toutes les 10 s (la sidebar lit
 *   la même clé de cache ["downloads"] pour son badge, sans requête en double).
 * - `useRemoveQueueItem()` / `useRetryQueueItem()` : actions sur UNE ligne.
 *   Elles portent une `mutationKey` commune pour que l'interface sache
 *   quelles lignes ont une action en cours (`usePendingQueueKeys`) — avant,
 *   un seul `isPending` global bloquait toute la page.
 * - Après succès, la ligne est retirée tout de suite du cache (la carte
 *   disparaît avec son animation) puis la file est re-téléchargée.
 */
import { useMutation, useMutationState, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiFetch } from "@/lib/api-client";

export interface DownloadItem {
    id: number;
    title: string;
    /** Statut *arr brut : downloading | queued | paused | completed | delay | warning | failed… */
    status: string;
    /** 0 → 100. */
    progress: number;
    size_bytes: number;
    size_left_bytes: number;
    /** Temps restant au format *arr « HH:MM:SS » ou « J.HH:MM:SS ». */
    time_left: string | null;
    source_service: string;
    service_type: string;
    movie_id: number | null;
    series_id: number | null;
    download_client: string;
    protocol: string; // "usenet" | "torrent"
    tracked_state: string; // "downloading" | "importPending" | "importing" | "importBlocked" | ...
    error: string; // vraie erreur de téléchargement
    detail: string; // message d'état (ex : pourquoi l'import attend)
    indexer: string;
    quality: string;
    /**
     * Épisodes couverts par ce téléchargement (pack de saison). Sonarr compte
     * une ligne par épisode : le serveur les regroupe en une seule carte.
     */
    episode_count?: number;
    /**
     * Affiche, fond et logo du film / de la série suivi, ajoutés par le
     * serveur depuis la médiathèque (absents si le titre n'y est pas).
     */
    poster_url?: string | null;
    fanart_url?: string | null;
    clearlogo_url?: string | null;
    /** Titre propre du média (« Dune »), à côté du nom de release. */
    media_title?: string | null;
}

export interface DownloadsResponse {
    items: DownloadItem[];
    total: number;
}

export const DOWNLOADS_KEY = ["downloads"] as const;

export function useDownloads() {
    return useQuery<DownloadsResponse>({
        queryKey: DOWNLOADS_KEY,
        queryFn: () => apiFetch("/api/downloads"),
        refetchInterval: 10_000, // la file bouge vite : 10 s
    });
}

// ── Actions sur la file ──────────────────────────────────────

/** Identifiant unique d'une ligne (les ids Radarr et Sonarr peuvent se chevaucher). */
export function queueItemKey(item: { service_type: string; id: number }): string {
    return `${item.service_type}-${item.id}`;
}

/** Clé commune à toutes les mutations de la file (sert au suivi « par ligne »). */
const QUEUE_MUTATION_KEY = ["downloads", "action"] as const;

/** Retire immédiatement une ligne du cache (animation de sortie sans attendre le refetch). */
function dropFromCache(qc: QueryClient, type: string, id: number) {
    qc.setQueryData<DownloadsResponse>(DOWNLOADS_KEY, (old) => {
        if (!old) return old;
        const items = old.items.filter((it) => !(it.service_type === type && it.id === id));
        return { ...old, items, total: items.length };
    });
}

export interface RemoveQueueVars {
    type: string;
    id: number;
    removeFromClient?: boolean;
    blocklist?: boolean;
}

export function useRemoveQueueItem() {
    const queryClient = useQueryClient();
    return useMutation<{ status: string; id: number; blocklisted: boolean }, Error, RemoveQueueVars>({
        mutationKey: QUEUE_MUTATION_KEY,
        mutationFn: ({ type, id, removeFromClient = true, blocklist = false }) =>
            apiFetch(`/api/downloads/queue/${type}/${id}/remove`, {
                method: "POST",
                body: JSON.stringify({ removeFromClient, blocklist }),
            }),
        onSuccess: (_data, vars) => {
            dropFromCache(queryClient, vars.type, vars.id);
            queryClient.invalidateQueries({ queryKey: DOWNLOADS_KEY });
        },
    });
}

export interface RetryQueueVars {
    type: string;
    id: number;
    movie_id?: number | null;
    series_id?: number | null;
}

export function useRetryQueueItem() {
    const queryClient = useQueryClient();
    return useMutation<{ status: string; id: number; search_triggered: boolean }, Error, RetryQueueVars>({
        mutationKey: QUEUE_MUTATION_KEY,
        mutationFn: ({ type, id, movie_id, series_id }) =>
            apiFetch(`/api/downloads/queue/${type}/${id}/retry`, {
                method: "POST",
                body: JSON.stringify({ movie_id, series_id }),
            }),
        onSuccess: (_data, vars) => {
            // « Relancer » = blocklist + retrait + nouvelle recherche : la ligne
            // actuelle quitte donc la file elle aussi.
            dropFromCache(queryClient, vars.type, vars.id);
            queryClient.invalidateQueries({ queryKey: DOWNLOADS_KEY });
        },
    });
}

/**
 * Ensemble des lignes (clé `type-id`) qui ont une action en cours.
 * Lit l'état de TOUTES les mutations de la file : plusieurs lignes peuvent
 * être traitées en parallèle, chacune affiche son propre indicateur.
 */
export function usePendingQueueKeys(): Set<string> {
    const pending = useMutationState<RemoveQueueVars | RetryQueueVars | undefined>({
        filters: { mutationKey: QUEUE_MUTATION_KEY, status: "pending" },
        select: (m) => m.state.variables as RemoveQueueVars | RetryQueueVars | undefined,
    });
    // Clé texte stable → le Set n'est recalculé que si la liste change vraiment.
    const signature = pending
        .filter((v): v is RemoveQueueVars | RetryQueueVars => !!v)
        .map((v) => `${v.type}-${v.id}`)
        .sort()
        .join("|");
    return useMemo(() => new Set(signature ? signature.split("|") : []), [signature]);
}
