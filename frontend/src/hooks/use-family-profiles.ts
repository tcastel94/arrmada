"use client";

/**
 * Profils famille (ADR-008) : qui regarde sur les TV de la maison.
 * ----------------------------------------------------------------
 * Chaque profil a sa rangée « Reprendre », ses épisodes vus, son « Pour
 * toi » et ses demandes « Pour ce soir » dans l'appli Android TV (écran
 * « Qui regarde ? »). Le profil « Famille » est celui des TV sous Kodi et
 * de la web app : il ne se supprime pas.
 *
 * Nom « family profiles » : « profiles » est déjà pris (profils audio
 * Yamaha, profils de qualité *arr).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface FamilyProfile {
    id: number;
    name: string;
    /** « #4A9EFF » : couleur de l'avatar sur la TV. */
    color: string;
    /** Emoji de l'avatar ; vide = initiale du nom. */
    emoji: string;
    is_default: boolean;
}

export interface FamilyProfileInput {
    name?: string;
    color?: string;
    emoji?: string;
}

/** Couleurs proposées (charte de l'appli TV). */
export const PROFILE_COLORS = ["#4A9EFF", "#22E0EE", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#F472B6", "#FB923C"];
export const MAX_PROFILES = 8;

const FAMILY_PROFILES_KEY = ["family-profiles"] as const;

export function useFamilyProfiles() {
    return useQuery<FamilyProfile[]>({
        queryKey: FAMILY_PROFILES_KEY,
        queryFn: async () => (await apiFetch<{ items: FamilyProfile[] }>("/api/profiles")).items,
    });
}

export function useCreateFamilyProfile() {
    const qc = useQueryClient();
    return useMutation<FamilyProfile, Error, FamilyProfileInput>({
        mutationFn: (body) => apiFetch("/api/profiles", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: FAMILY_PROFILES_KEY }),
    });
}

export function useUpdateFamilyProfile() {
    const qc = useQueryClient();
    return useMutation<FamilyProfile, Error, { id: number } & FamilyProfileInput>({
        mutationFn: ({ id, ...body }) => apiFetch(`/api/profiles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: FAMILY_PROFILES_KEY }),
    });
}

export function useDeleteFamilyProfile() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/profiles/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: FAMILY_PROFILES_KEY }),
    });
}
