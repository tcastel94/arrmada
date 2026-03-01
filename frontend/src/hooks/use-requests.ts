"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface MediaRequestItem {
    id: number;
    title: string;
    type: string;
    tmdb_id: number | null;
    year: number | null;
    poster_url: string | null;
    quality_profile: string | null;
    status: string;
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
    tmdb_id?: number | null;
    year?: number | null;
    poster_url?: string | null;
    quality_profile?: string | null;
}

export function useRequests() {
    return useQuery<RequestsResponse>({
        queryKey: ["requests"],
        queryFn: () => apiFetch("/api/requests"),
    });
}

export function useCreateRequest() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: CreateRequestPayload) =>
            apiFetch("/api/requests", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["requests"] });
        },
    });
}

export function useDeleteRequest() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (id: number) =>
            apiFetch(`/api/requests/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["requests"] });
        },
    });
}
