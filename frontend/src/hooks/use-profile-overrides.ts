"use client";

/**
 * Profils TRaSH « par média » (overrides).
 * ----------------------------------------------------------------
 * Un override dit : « pour CE film / CETTE série, utilise tel profil TRaSH
 * au lieu du profil par défaut ». Il est enregistré dans ArrMada puis doit
 * être APPLIQUÉ (POST /{id}/apply) pour que Sonarr/Radarr changent
 * réellement de profil — d'où les actions « Appliquer » dans l'UI.
 * Utilisé par l'onglet « Profils par média » de /trash-guides ET par la
 * fiche média (signatures conservées).
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ProfileOverride {
    id: number;
    media_type: "movie" | "series" | string;
    /** ID Sonarr (série) ou Radarr (film). */
    external_id: number;
    title: string;
    /** Nom de fichier du profil TRaSH (ex: "french-multi-vo-bluray-web-2160p"). */
    profile_name: string;
    service_id: number;
    note: string | null;
    created_at: string;
}

export interface AvailableProfile {
    /** Identifiant technique (= `profile_name` d'un override). */
    filename: string;
    /** Nom lisible du profil. */
    display_name: string;
    service_type: string;
}

export interface CreateOverridePayload {
    media_type: string;
    external_id: number;
    title: string;
    profile_name: string;
    service_id: number;
    note?: string;
}

export function useProfileOverrides(serviceId?: number) {
    return useQuery<ProfileOverride[]>({
        queryKey: ["profile-overrides", serviceId],
        queryFn: () =>
            apiFetch<ProfileOverride[]>(`/api/profile-overrides${serviceId ? `?service_id=${serviceId}` : ""}`),
    });
}

export function useAvailableProfiles(serviceType: string) {
    return useQuery<AvailableProfile[]>({
        queryKey: ["profile-overrides", "profiles", serviceType],
        queryFn: () =>
            apiFetch<AvailableProfile[]>(
                `/api/profile-overrides/profiles?service_type=${encodeURIComponent(serviceType)}`,
            ),
        enabled: !!serviceType,
        staleTime: 300_000,
    });
}

export function useCreateOverride() {
    const qc = useQueryClient();
    return useMutation<ProfileOverride, Error, CreateOverridePayload>({
        mutationFn: (body) =>
            apiFetch<ProfileOverride>("/api/profile-overrides", {
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
    return useMutation<unknown, Error, number>({
        mutationFn: (id) => apiFetch(`/api/profile-overrides/${id}`, { method: "DELETE" }),
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
    /** true si le média a bien été basculé sur le profil dans Sonarr/Radarr. */
    media_updated: boolean;
    errors: string[];
}

export function useApplyOverride() {
    const qc = useQueryClient();
    return useMutation<ApplyOverrideResult, Error, number>({
        mutationFn: (id) =>
            apiFetch<ApplyOverrideResult>(`/api/profile-overrides/${id}/apply`, { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["profile-overrides"] });
            qc.invalidateQueries({ queryKey: ["notifications"] });
            qc.invalidateQueries({ queryKey: ["trash-guides", "compliance"] });
        },
    });
}
