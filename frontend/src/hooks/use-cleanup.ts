"use client";

/**
 * Nettoyage intelligent (onglet « Nettoyage » de /health).
 * ----------------------------------------------------------------
 * `GET /api/cleanup` repère 4 familles de médias qui occupent de la place
 * pour rien : non surveillés, basse qualité ancienne, fichiers énormes,
 * séries terminées complètes à moins de 50 %.
 * Chaque liste est PLAFONNÉE côté serveur (30 ou 20 éléments, triés du
 * plus gros au plus petit) alors que `total` est le vrai nombre.
 *
 * Actions disponibles par ligne (API médias existante) :
 *  - « Ne plus surveiller » → PATCH /api/media/{type}/{id} {monitored:false}
 *  - « Supprimer »          → DELETE /api/media/{type}/{id}
 * Comme le scan est mis en cache 10 min par le backend, on retire aussi
 * l'élément du cache local pour que l'écran reflète l'action tout de suite.
 */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type CleanupCategory = "unmonitored" | "low_quality" | "oversized" | "incomplete_ended";

/** Taille max des listes renvoyées par le backend, par catégorie. */
export const CLEANUP_LIMITS: Record<CleanupCategory, number> = {
    unmonitored: 30,
    low_quality: 30,
    oversized: 20,
    incomplete_ended: 20,
};

export interface CleanupItem {
    title: string;
    year?: number | null;
    type: "movie" | "series";
    /** Films uniquement (nom de qualité *arr). */
    quality?: string;
    size_bytes: number;
    size_human: string;
    poster_url?: string | null;
    /** Nom de l'instance ArrMada (ex: "Radarr"). */
    service: string;
    service_type: "radarr" | "sonarr";
    /** ID Radarr/Sonarr (lien fiche + actions). */
    external_id: number;
    monitored: boolean;
    reason: CleanupCategory;
    /** Phrase explicative générée par le backend. */
    suggestion: string;
    /** Séries uniquement. */
    episodes_total?: number;
    episodes_have?: number;
    /** "continuing" | "ended"… (séries uniquement). */
    status?: string;
    /** Séries terminées incomplètes uniquement (0-100). */
    completion_percent?: number;
}

export interface CleanupBucket {
    items: CleanupItem[];
    /** Vrai total (la liste `items` peut être tronquée). */
    total: number;
}

export interface CleanupScan {
    unmonitored: CleanupBucket & { reclaimable_bytes?: number; reclaimable_human: string };
    low_quality: CleanupBucket;
    oversized: CleanupBucket;
    incomplete_ended: CleanupBucket;
    summary: {
        /** Attention : un même média peut être compté dans plusieurs catégories. */
        total_issues: number;
        total_reclaimable_bytes: number;
        total_reclaimable_human: string;
    };
}

export const CLEANUP_QUERY_KEY = ["cleanup", "scan"] as const;

// Drapeau consommé par la prochaine requête : « Rescanner » demande au
// backend d'ignorer son cache de 10 min (?refresh=1) au lieu de relire
// l'ancien résultat.
let forceCleanupRefresh = false;

export function useCleanupScan() {
    const query = useQuery<CleanupScan>({
        queryKey: CLEANUP_QUERY_KEY,
        queryFn: () => {
            const refresh = forceCleanupRefresh;
            forceCleanupRefresh = false;
            return apiFetch<CleanupScan>(`/api/cleanup${refresh ? "?refresh=1" : ""}`);
        },
        staleTime: 600_000,
    });
    const rescan = () => {
        forceCleanupRefresh = true;
        return query.refetch();
    };
    return Object.assign(query, { rescan });
}

/**
 * Espace réellement récupérable, sans double comptage.
 * Le backend additionne « non surveillés » + « séries terminées
 * incomplètes » : une série non surveillée ET incomplète est donc comptée
 * deux fois. Toute série incomplète non surveillée figure forcément dans la
 * liste « non surveillés » (mêmes critères) → on ne garde que les séries
 * incomplètes encore surveillées.
 * `exact` = false si la liste des séries incomplètes est tronquée (la
 * valeur est alors un minimum).
 */
export function reclaimableBytes(scan: CleanupScan): { bytes: number; exact: boolean } {
    const base = scan.unmonitored.reclaimable_bytes ?? scan.unmonitored.items.reduce((s, i) => s + (i.size_bytes || 0), 0);
    const extra = scan.incomplete_ended.items
        .filter((i) => i.monitored)
        .reduce((s, i) => s + (i.size_bytes || 0), 0);
    const exact =
        scan.incomplete_ended.items.length >= scan.incomplete_ended.total &&
        (scan.unmonitored.reclaimable_bytes !== undefined || scan.unmonitored.items.length >= scan.unmonitored.total);
    return { bytes: base + extra, exact };
}

/** Clé unique d'un média (un même ID peut exister côté Radarr ET Sonarr). */
export function cleanupItemKey(item: Pick<CleanupItem, "service_type" | "external_id" | "service">): string {
    return `${item.service}:${item.service_type}:${item.external_id}`;
}

/** Retire (ou modifie) un média dans toutes les listes du scan en cache. */
function patchCachedScan(qc: QueryClient, target: CleanupItem, mode: "remove" | "unmonitor") {
    const key = cleanupItemKey(target);
    // Applique la modification à une liste en conservant son type exact
    // (la liste « non surveillés » porte des champs en plus).
    const apply = <B extends CleanupBucket>(bucket: B): B => {
        if (!bucket.items.some((i) => cleanupItemKey(i) === key)) return bucket;
        if (mode === "remove") {
            return {
                ...bucket,
                items: bucket.items.filter((i) => cleanupItemKey(i) !== key),
                total: Math.max(0, bucket.total - 1),
            };
        }
        // « Ne plus surveiller » : le média reste sur disque, seul son état
        // change (il rejoindra « non surveillés » au prochain scan serveur).
        return {
            ...bucket,
            items: bucket.items.map((i) => (cleanupItemKey(i) === key ? { ...i, monitored: false } : i)),
        };
    };

    qc.setQueryData<CleanupScan>(CLEANUP_QUERY_KEY, (old) => {
        if (!old) return old;
        const unmonitored = { ...apply(old.unmonitored) }; // copie : on ne mute jamais le cache
        // Un média non surveillé supprimé libère sa place du compteur « récupérable ».
        if (mode === "remove" && !target.monitored && unmonitored.reclaimable_bytes !== undefined) {
            unmonitored.reclaimable_bytes = Math.max(0, unmonitored.reclaimable_bytes - (target.size_bytes || 0));
        }
        return {
            ...old,
            unmonitored,
            low_quality: apply(old.low_quality),
            oversized: apply(old.oversized),
            incomplete_ended: apply(old.incomplete_ended),
        };
    });
}

/** Invalide tout ce qui dépend du contenu de la médiathèque. */
function invalidateLibrary(qc: QueryClient) {
    qc.invalidateQueries({ queryKey: ["media"] });
    qc.invalidateQueries({ queryKey: ["quality"] });
    qc.invalidateQueries({ queryKey: ["duplicates"] });
    qc.invalidateQueries({ queryKey: ["analytics"] });
}

/** « Ne plus surveiller » : PATCH monitored=false sur Radarr/Sonarr. */
export function useUnmonitorMedia() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, CleanupItem>({
        mutationFn: (item) =>
            apiFetch(`/api/media/${item.type}/${item.external_id}`, {
                method: "PATCH",
                body: JSON.stringify({ monitored: false }),
            }),
        onSuccess: (_data, item) => {
            patchCachedScan(qc, item, "unmonitor");
            invalidateLibrary(qc);
        },
    });
}

/** Suppression du média dans Radarr/Sonarr (fichiers compris par défaut). */
export function useDeleteMedia() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, { item: CleanupItem; deleteFiles: boolean }>({
        mutationFn: ({ item, deleteFiles }) =>
            apiFetch(
                `/api/media/${item.type}/${item.external_id}?delete_files=${deleteFiles}&delete_downloads=true`,
                { method: "DELETE" },
            ),
        onSuccess: (_data, { item }) => {
            patchCachedScan(qc, item, "remove");
            invalidateLibrary(qc);
        },
    });
}
