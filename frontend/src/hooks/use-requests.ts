"use client";

/**
 * Demandes d'ajout (« requests ») : un titre envoyé à Radarr/Sonarr, puis
 * suivi jusqu'à sa disponibilité. Le backend resynchronise les statuts à
 * chaque lecture de la liste (tâche de fond), d'où le rafraîchissement
 * automatique toutes les 15 s.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Cycle de vie d'une demande côté backend. */
export type RequestStatus = "requested" | "searching" | "downloading" | "available" | "failed";

export interface MediaRequestItem {
    id: number;
    title: string;
    type: string;
    /**
     * Film : ID TMDB. Série : ID **TVDB** (convention historique du backend,
     * Sonarr étant indexé sur TVDB).
     */
    tmdb_id: number | null;
    year: number | null;
    poster_url: string | null;
    quality_profile: string | null;
    status: RequestStatus | string;
    target_service: string;
    arr_id: number | null;
    requested_at: string | null;
    completed_at: string | null;
}

export interface RequestsResponse {
    items: MediaRequestItem[];
    total: number;
}

export interface CreateRequestPayload {
    title: string;
    type: string;
    /** Vrai ID TMDB (film ou série). */
    tmdb_id?: number | null;
    /**
     * ID TVDB d'une série. À renseigner à la place de `tmdb_id` quand on le
     * connaît (résultats du lookup Sonarr) : avant, un ID TMDB de série était
     * pris pour un ID TVDB et Sonarr ajoutait la mauvaise série.
     */
    tvdb_id?: number | null;
    year?: number | null;
    poster_url?: string | null;
    quality_profile?: string | null;
}

/** Réponse du POST : `status === "failed"` = le service n'a pas pu ajouter le titre. */
export interface CreateRequestResponse {
    id: number;
    title: string;
    type: string;
    status: RequestStatus | string;
    target_service: string;
    arr_id: number | null;
}

export function useRequests() {
    return useQuery<RequestsResponse>({
        queryKey: ["requests"],
        queryFn: () => apiFetch("/api/requests"),
        refetchInterval: 15000,
    });
}

export function useCreateRequest() {
    const queryClient = useQueryClient();
    return useMutation<CreateRequestResponse, Error, CreateRequestPayload>({
        mutationFn: (payload) =>
            apiFetch<CreateRequestResponse>("/api/requests", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["requests"] });
            // Le titre est maintenant dans Radarr/Sonarr : les résultats de
            // lookup (« déjà dans ta bibliothèque ») doivent être recalculés.
            queryClient.invalidateQueries({ queryKey: ["lookup"] });
        },
    });
}

export function useDeleteRequest() {
    const queryClient = useQueryClient();
    return useMutation<void, Error, number>({
        mutationFn: (id) => apiFetch(`/api/requests/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["requests"] });
        },
    });
}
