"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ProfileOverride {
    id: number;
    media_type: string;
    external_id: number;
    title: string;
    profile_name: string;
    service_id: number;
    note: string | null;
    created_at: string;
}

export interface AvailableProfile {
    filename: string;
    display_name: string;
    service_type: string;
}

export function useProfileOverrides(serviceId?: number) {
    return useQuery<ProfileOverride[]>({
        queryKey: ["profile-overrides", serviceId],
        queryFn: () =>
            apiFetch(
                `/api/profile-overrides${serviceId ? `?service_id=${serviceId}` : ""}`
            ),
    });
}

export function useAvailableProfiles(serviceType: string) {
    return useQuery<AvailableProfile[]>({
        queryKey: ["profile-overrides", "profiles", serviceType],
        queryFn: () =>
            apiFetch(`/api/profile-overrides/profiles?service_type=${serviceType}`),
        staleTime: 300_000,
    });
}

export function useCreateOverride() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: {
            media_type: string;
            external_id: number;
            title: string;
            profile_name: string;
            service_id: number;
            note?: string;
        }) =>
            apiFetch("/api/profile-overrides", {
                method: "POST",
                body: JSON.stringify(body),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["profile-overrides"] });
        },
    });
}

export function useDeleteOverride() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id: number) =>
            apiFetch(`/api/profile-overrides/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["profile-overrides"] });
        },
    });
}

export interface ApplyOverrideResult {
    success: boolean;
    cfs_created: number;
    cfs_updated: number;
    profile_name: string;
    profile_id: number | null;
    media_updated: boolean;
    errors: string[];
}

export function useApplyOverride() {
    const qc = useQueryClient();
    return useMutation<ApplyOverrideResult, Error, number>({
        mutationFn: (id: number) =>
            apiFetch(`/api/profile-overrides/${id}/apply`, { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["profile-overrides"] });
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}
