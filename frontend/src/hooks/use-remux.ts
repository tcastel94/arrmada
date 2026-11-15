"use client";

/**
 * Remux à alléger (onglet « Remux » de /health, ADR-021).
 * ----------------------------------------------------------------
 * `GET /api/remux` rend TOUS les films dont le fichier est un remux que
 * leur profil qualité n'autorise plus (pas de plafond), du plus lourd au
 * plus léger, avec le réglage de la corbeille de Radarr et l'état du lot
 * de remplacement en cours.
 *
 * Remplacer = pour chaque film, le serveur cherche un remplaçant plus
 * léger, le met en téléchargement, puis seulement supprime le fichier du
 * remux (jamais le film). C'est un lot en tâche de fond, 10 films au plus :
 * tant qu'il tourne, la liste est relue toutes les 3 secondes.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type RemuxStatus = "ready" | "unmonitored" | "suspect";

export interface RemuxItem {
    movie_id: number;
    file_id: number;
    tmdb_id?: number | null;
    title: string;
    year?: number | null;
    /** « Remux-2160p » ou « Remux-1080p ». */
    quality: string;
    resolution: number;
    size_bytes: number;
    /** Taille attendue du remplaçant (ordre de grandeur, selon la durée). */
    estimated_bytes: number;
    /** 0 si le film n'est pas remplaçable. */
    gain_bytes: number;
    profile_id: number;
    profile_name: string;
    monitored: boolean;
    poster_url?: string | null;
    status: RemuxStatus;
    /** Pourquoi le film n'est pas remplaçable (vide si `ready`). */
    note: string;
}

export interface RemuxResult {
    movie_id: number;
    title: string;
    status: "replaced" | "skipped" | "error";
    message: string;
    freed_bytes: number;
    replacement: { title: string; quality: string; size_bytes: number; indexer?: string; choices: number } | null;
}

export interface RemuxJob {
    id: string;
    state: "running" | "done" | "stopped";
    total: number;
    done: number;
    current: string | null;
    replaced: number;
    skipped: number;
    errors: number;
    freed_bytes: number;
    results: RemuxResult[];
    started_at: string;
    finished_at: string | null;
}

export interface RemuxKeepProfile {
    id: number;
    name: string;
    /** Films en remux déjà rangés dans ce profil. */
    remux_kept: number;
}

export interface RemuxData {
    items: RemuxItem[];
    total: number;
    /** Films remplaçables (statut `ready`). */
    ready: number;
    /** Taille actuelle des films remplaçables. */
    size_bytes: number;
    /** Gain estimé si tous les films remplaçables le sont. */
    reclaimable_bytes: number;
    keep_profiles: RemuxKeepProfile[];
    recycle_bin: { enabled: boolean; path: string | null; cleanup_days: number };
    batch_max: number;
    include_1080p: boolean;
    job: RemuxJob | null;
}

const remuxKey = (include1080p: boolean) => ["remux", include1080p] as const;

export function useRemux(include1080p = false) {
    return useQuery<RemuxData>({
        queryKey: remuxKey(include1080p),
        queryFn: () => apiFetch<RemuxData>(`/api/remux${include1080p ? "?include_1080p=true" : ""}`),
        staleTime: 60_000,
        // Lot en cours : on suit son avancement (et la liste qui se vide).
        refetchInterval: (query) => (query.state.data?.job?.state === "running" ? 3000 : false),
    });
}

/** Tout ce qui dépend du contenu de la médiathèque est à relire après un lot. */
function useInvalidate() {
    const qc = useQueryClient();
    return () => {
        qc.invalidateQueries({ queryKey: ["remux"] });
        qc.invalidateQueries({ queryKey: ["cleanup"] });
        qc.invalidateQueries({ queryKey: ["quality"] });
        qc.invalidateQueries({ queryKey: ["media"] });
    };
}

/** Lance un lot de remplacement (10 films au plus). */
export function useReplaceRemux() {
    const invalidate = useInvalidate();
    return useMutation<{ job: RemuxJob }, Error, { movieIds: number[]; include1080p: boolean }>({
        mutationFn: ({ movieIds, include1080p }) =>
            apiFetch("/api/remux/replace", {
                method: "POST",
                body: JSON.stringify({ movie_ids: movieIds, include_1080p: include1080p }),
            }),
        onSuccess: invalidate,
    });
}

/** Arrête le lot après le film en cours. */
export function useStopRemuxJob() {
    const invalidate = useInvalidate();
    return useMutation<{ job: RemuxJob | null }, Error, void>({
        mutationFn: () => apiFetch("/api/remux/job/stop", { method: "POST" }),
        onSuccess: invalidate,
    });
}

/** Garde le remux : passe des films dans un profil qui l'autorise. */
export function useKeepRemux() {
    const invalidate = useInvalidate();
    return useMutation<{ changed: number; profile_name: string }, Error, { movieIds: number[]; profileId: number }>({
        mutationFn: ({ movieIds, profileId }) =>
            apiFetch("/api/remux/keep", {
                method: "POST",
                body: JSON.stringify({ movie_ids: movieIds, profile_id: profileId }),
            }),
        onSuccess: invalidate,
    });
}
