"use client";

/**
 * Notifications in-app (alertes services, synchro TRaSH, imports…).
 * ----------------------------------------------------------------
 * Utilisé par la page /notifications ET par la cloche du header : les
 * signatures `useNotifications(limit, unreadOnly)`, `useUnreadCount()`,
 * `useMarkRead()`, `useMarkAllRead()` doivent rester stables.
 *
 * Nouveauté : « marquer lu » est optimiste — la pastille disparaît tout de
 * suite dans la page ET dans le header ; en cas d'erreur API on restaure
 * l'état précédent (l'appelant affiche le toast d'erreur).
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient, type QueryKey } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface NotificationItem {
    id: number;
    /** Type brut backend : service_down, service_recovered, trash_sync, new_import… */
    type: string;
    /** info | success | warning | error */
    severity: string;
    title: string;
    message: string;
    is_read: boolean;
    service_name: string | null;
    created_at: string;
}

interface NotificationListResponse {
    items: NotificationItem[];
    unread_count: number;
}

export function useNotifications(limit = 50, unreadOnly = false) {
    return useQuery<NotificationListResponse>({
        queryKey: ["notifications", { limit, unreadOnly }],
        queryFn: () => apiFetch(`/api/notifications?limit=${limit}&unread_only=${unreadOnly}`),
        refetchInterval: 30_000, // Poll every 30s
        // « Charger plus » (limit qui augmente) garde la liste affichée.
        placeholderData: keepPreviousData,
    });
}

export function useUnreadCount() {
    return useQuery<{ unread_count: number }>({
        queryKey: ["notifications", "count"],
        queryFn: () => apiFetch("/api/notifications/count"),
        refetchInterval: 15_000, // Poll every 15s
    });
}

// ── Mises à jour optimistes ──────────────────────────────────

type Snapshot = Array<[QueryKey, unknown]>;

/**
 * Applique `mark` à toutes les listes/compteurs de notifications en cache
 * et renvoie l'état précédent (pour annuler en cas d'erreur).
 */
async function optimisticallyMark(
    qc: QueryClient,
    isTarget: (n: NotificationItem) => boolean,
    all = false,
): Promise<Snapshot> {
    await qc.cancelQueries({ queryKey: ["notifications"] });
    const snapshot = qc.getQueriesData({ queryKey: ["notifications"] }) as Snapshot;

    // Combien de non-lues vont disparaître ? (déduit d'une liste en cache ;
    // pour « tout lire », le compteur tombe simplement à 0).
    let cleared = 0;
    for (const [, data] of snapshot) {
        const list = data as NotificationListResponse | undefined;
        if (list?.items) {
            cleared = Math.max(cleared, list.items.filter((n) => !n.is_read && isTarget(n)).length);
        }
    }

    for (const [key, data] of snapshot) {
        if (!data || typeof data !== "object") continue;
        if ("items" in (data as object)) {
            const list = data as NotificationListResponse;
            const items = list.items.map((n) => (isTarget(n) ? { ...n, is_read: true } : n));
            qc.setQueryData(key, {
                ...list,
                items,
                unread_count: all ? 0 : Math.max(0, list.unread_count - cleared),
            });
        } else if ("unread_count" in (data as object)) {
            const c = data as { unread_count: number };
            qc.setQueryData(key, { ...c, unread_count: all ? 0 : Math.max(0, c.unread_count - cleared) });
        }
    }
    return snapshot;
}

function restore(qc: QueryClient, snapshot: Snapshot | undefined) {
    snapshot?.forEach(([key, data]) => qc.setQueryData(key, data));
}

export function useMarkRead() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, number, { snapshot: Snapshot }>({
        mutationFn: (id: number) => apiFetch(`/api/notifications/${id}/read`, { method: "POST" }),
        onMutate: async (id) => ({ snapshot: await optimisticallyMark(qc, (n) => n.id === id) }),
        onError: (_err, _id, ctx) => restore(qc, ctx?.snapshot),
        onSettled: () => {
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}

export function useMarkAllRead() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, void, { snapshot: Snapshot }>({
        mutationFn: () => apiFetch("/api/notifications/read-all", { method: "POST" }),
        onMutate: async () => ({ snapshot: await optimisticallyMark(qc, () => true, true) }),
        onError: (_err, _v, ctx) => restore(qc, ctx?.snapshot),
        onSettled: () => {
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}
