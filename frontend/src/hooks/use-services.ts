"use client";

/**
 * Hooks React Query des services *arr (Sonarr, Radarr, Prowlarr…).
 * ----------------------------------------------------------------
 * Analogie infra : React Query est un cache local des réponses API avec
 * expiration/rafraîchissement automatique. Les « mutations » (créer,
 * modifier, supprimer, tester) mettent ce cache à jour pour que tous les
 * écrans (dashboard, réglages, TRaSH…) restent cohérents sans recharger.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
    isArrService,
    type ArrService,
    type CreateServicePayload,
    type UpdateServicePayload,
    type TestConnectionResult,
    type TestServiceDraftPayload,
    type ServiceHealthResult,
    type HealthEvent,
} from "@/types/service";

const SERVICES_KEY = ["services"] as const;

/** Filtres `select` définis une fois (référence stable → pas de recalcul inutile). */
const selectArrServices = (list: ArrService[]) => (list ?? []).filter(isArrService);
const selectArrHealth = (list: ServiceHealthResult[]) =>
    (list ?? []).filter((h) => isArrService({ type: h.service_type }));

/**
 * Liste des services *arr.
 * Le backend exclut désormais les appareils (Kodi/Yamaha) de /api/services ;
 * on filtre aussi côté client (`select`) pour rester correct face à un
 * backend plus ancien : aucun écran ne doit afficher Kodi comme un *arr.
 */
export function useServices() {
    return useQuery<ArrService[], Error, ArrService[]>({
        queryKey: SERVICES_KEY,
        queryFn: () => apiFetch("/api/services"),
        select: selectArrServices,
    });
}

/** Fetch a single service */
export function useService(id: number) {
    return useQuery<ArrService>({
        queryKey: ["services", id],
        queryFn: () => apiFetch(`/api/services/${id}`),
        enabled: !!id,
    });
}

/** Create a new service */
export function useCreateService() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: CreateServicePayload) =>
            apiFetch<ArrService>("/api/services", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
        },
    });
}

/**
 * Modifier un service.
 * Mise à jour « optimiste » : le cache est modifié immédiatement (le switch
 * Activé/Désactivé bascule sans attendre le réseau), puis restauré si
 * l'API refuse.
 */
export function useUpdateService() {
    const queryClient = useQueryClient();
    return useMutation<
        ArrService,
        Error,
        { id: number; data: UpdateServicePayload },
        { previous?: ArrService[] }
    >({
        mutationFn: ({ id, data }) =>
            apiFetch<ArrService>(`/api/services/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            }),
        onMutate: async ({ id, data }) => {
            await queryClient.cancelQueries({ queryKey: SERVICES_KEY, exact: true });
            const previous = queryClient.getQueryData<ArrService[]>(SERVICES_KEY);
            // Seuls les champs visibles vont dans le cache (jamais la clé API).
            const visible: Partial<ArrService> = {};
            if (data.name !== undefined) visible.name = data.name;
            if (data.url !== undefined) visible.url = data.url;
            if (data.is_enabled !== undefined) visible.is_enabled = data.is_enabled;
            queryClient.setQueryData<ArrService[]>(SERVICES_KEY, (old) =>
                old?.map((s) => (s.id === id ? { ...s, ...visible } : s)),
            );
            return { previous };
        },
        onError: (_err, _vars, ctx) => {
            if (ctx?.previous) queryClient.setQueryData(SERVICES_KEY, ctx.previous);
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
        },
    });
}

/** Supprimer un service (retrait immédiat de la liste, restauré en cas d'échec). */
export function useDeleteService() {
    const queryClient = useQueryClient();
    return useMutation<void, Error, number, { previous?: ArrService[] }>({
        mutationFn: (id) => apiFetch<void>(`/api/services/${id}`, { method: "DELETE" }),
        onMutate: async (id) => {
            await queryClient.cancelQueries({ queryKey: SERVICES_KEY, exact: true });
            const previous = queryClient.getQueryData<ArrService[]>(SERVICES_KEY);
            queryClient.setQueryData<ArrService[]>(SERVICES_KEY, (old) => old?.filter((s) => s.id !== id));
            return { previous };
        },
        onError: (_err, _id, ctx) => {
            if (ctx?.previous) queryClient.setQueryData(SERVICES_KEY, ctx.previous);
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
        },
    });
}

/**
 * Tester un service enregistré.
 * Chaque carte appelle ce hook pour elle-même → l'état « en cours » est
 * propre à la carte (avant : un seul isPending partagé grisait toutes
 * les cartes). Le résultat est reporté dans le cache (statut, latence,
 * version, date du dernier contrôle).
 */
export function useTestConnection() {
    const queryClient = useQueryClient();
    return useMutation<TestConnectionResult, Error, number>({
        mutationFn: (id) =>
            apiFetch<TestConnectionResult>(`/api/services/${id}/test`, {
                method: "POST",
            }),
        onSuccess: (result, id) => {
            queryClient.setQueryData<ArrService[]>(SERVICES_KEY, (old) =>
                old?.map((s) =>
                    s.id === id
                        ? {
                              ...s,
                              last_status: result.status,
                              last_latency_ms: result.latency_ms,
                              version: result.version ?? s.version,
                              last_health_check: new Date().toISOString(),
                          }
                        : s,
                ),
            );
        },
    });
}

/**
 * Tester une configuration AVANT de l'enregistrer (formulaire d'ajout /
 * modification). Évite d'enregistrer une URL ou une clé erronée.
 */
export function useTestServiceDraft() {
    return useMutation<TestConnectionResult, Error, TestServiceDraftPayload>({
        mutationFn: (body) =>
            apiFetch<TestConnectionResult>("/api/services/test", {
                method: "POST",
                body: JSON.stringify(body),
            }),
    });
}

/** Contrôle de santé global (toutes les 60 s), appareils exclus. */
export function useGlobalHealth() {
    return useQuery<ServiceHealthResult[], Error, ServiceHealthResult[]>({
        queryKey: ["services", "health"],
        queryFn: () => apiFetch("/api/services/health/all"),
        select: selectArrHealth,
        refetchInterval: 60_000, // Every 60 seconds
    });
}

/** Fetch health history for a service */
export function useServiceHealthHistory(id: number, limit = 50) {
    return useQuery<HealthEvent[]>({
        queryKey: ["services", id, "health"],
        queryFn: () => apiFetch(`/api/services/${id}/health?limit=${limit}`),
        enabled: !!id,
    });
}
