"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
    ArrService,
    CreateServicePayload,
    UpdateServicePayload,
    TestConnectionResult,
    ServiceHealthResult,
    HealthEvent,
} from "@/types/service";

/** Fetch all services */
export function useServices() {
    return useQuery<ArrService[]>({
        queryKey: ["services"],
        queryFn: () => apiFetch("/api/services"),
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
            queryClient.invalidateQueries({ queryKey: ["services"] });
        },
    });
}

/** Update a service */
export function useUpdateService() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({
            id,
            data,
        }: {
            id: number;
            data: UpdateServicePayload;
        }) =>
            apiFetch<ArrService>(`/api/services/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["services"] });
        },
    });
}

/** Delete a service */
export function useDeleteService() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (id: number) =>
            apiFetch<void>(`/api/services/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["services"] });
        },
    });
}

/** Test a service connection */
export function useTestConnection() {
    return useMutation({
        mutationFn: (id: number) =>
            apiFetch<TestConnectionResult>(`/api/services/${id}/test`, {
                method: "POST",
            }),
    });
}

/** Fetch global health */
export function useGlobalHealth() {
    return useQuery<ServiceHealthResult[]>({
        queryKey: ["services", "health"],
        queryFn: () => apiFetch("/api/services/health/all"),
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
