"use client";

/**
 * Imports de fichiers : historique SABnzbd, chemins NAS, téléchargements
 * terminés mais jamais importés (« bloqués »), import manuel / groupé et
 * rapports de l'auto-import périodique.
 * Utilisé par l'onglet « Imports » de /downloads (ex-page /fichiers).
 * (Les hooks Docker ont déménagé dans use-docker.ts.)
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

// ── Historique SABnzbd ───────────────────────────────────────

export interface StageAction {
    stage: string;
    actions: string[];
}

export interface HistoryItem {
    nzo_id: string;
    name: string;
    /** Statut SABnzbd brut (anglais) : Completed | Failed | Extracting… */
    status: string;
    category: string;
    size_bytes: number;
    size_human: string;
    /** Fin du téléchargement, en secondes UNIX (SABnzbd). */
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

/** Plafond côté backend (Query le=200). */
export const SAB_HISTORY_MAX = 200;

export function useSabnzbdHistory(limit = 50, enabled = true) {
    return useQuery<HistoryResponse>({
        queryKey: ["sabnzbd-history", limit],
        queryFn: () => apiFetch(`/api/files/history?limit=${Math.min(limit, SAB_HISTORY_MAX)}`),
        enabled,
        // « Voir plus » augmente `limit` : on garde la liste affichée pendant
        // le chargement de la suivante (pas de retour aux squelettes).
        placeholderData: keepPreviousData,
    });
}

// ── Chemins NAS ──────────────────────────────────────────────

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
        staleTime: 10 * 60_000, // config statique : inutile de la relire souvent
    });
}

// ── Téléchargements bloqués (terminés mais pas importés) ─────

export interface StuckDownload {
    nzo_id: string;
    name: string;
    category: string;
    /** "movie" | "series" | "unknown" (détection automatique côté backend). */
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
        // Avant : jamais rafraîchi → un import réussi restait affiché.
        refetchInterval: 60_000,
    });
}

// ── Import manuel ────────────────────────────────────────────

export interface ImportResponse {
    success: boolean;
    service?: string;
    command_id?: number;
    files_count?: number;
    message?: string;
    error?: string;
    candidates_total?: number;
}

export interface ImportPayload {
    download_path: string;
    media_type: string;
}

export function useManualImport() {
    const queryClient = useQueryClient();
    return useMutation<ImportResponse, Error, ImportPayload>({
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

/**
 * Import groupé : le backend répond IMMÉDIATEMENT puis traite les fichiers
 * en tâche de fond. Un succès signifie donc « lancé », pas « importé ».
 */
export function useBulkImport() {
    const queryClient = useQueryClient();
    return useMutation<{ success: boolean; message: string }, Error, { items: ImportPayload[] }>({
        mutationFn: (payload) =>
            apiFetch("/api/files/import/bulk", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["stuck-downloads"] });
            queryClient.invalidateQueries({ queryKey: ["sabnzbd-history"] });
        },
    });
}

// ── Rapports d'auto-import ───────────────────────────────────

export interface AutoImportReportItem {
    name: string;
    storage_path: string;
    media_type: string;
    status: "success" | "failed";
    message?: string;
}

export interface AutoImportReport {
    timestamp: string;
    duration_seconds: number;
    scanned_count: number;
    imported_count: number;
    failed_count: number;
    items: AutoImportReportItem[];
}

/**
 * @param live  vrai quand la section est affichée : le rafraîchissement
 *              toutes les 30 s ne tourne QUE dans ce cas (avant, il tournait
 *              en permanence, même section masquée).
 */
export function useAutoImportReports(live = true) {
    return useQuery<AutoImportReport[]>({
        queryKey: ["auto-import-reports"],
        queryFn: () => apiFetch("/api/files/auto-import/reports"),
        enabled: live,
        refetchInterval: live ? 30_000 : false,
    });
}
