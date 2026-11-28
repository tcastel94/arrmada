"use client";

/**
 * Trakt : comptes reliés aux profils famille (ADR-022).
 * ----------------------------------------------------------------
 * Liaison par « code d'appareil », comme l'appairage d'une TV : le serveur
 * demande un code à Trakt, tu le tapes sur trakt.tv/activate, puis la page
 * interroge le serveur toutes les `interval` secondes jusqu'à « relié ».
 * Les notes elles-mêmes se donnent sur la TV, en fin de lecture.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface TraktProfile {
    id: number;
    name: string;
    color: string;
    emoji: string;
    is_default: boolean;
    /** 0 = profil « Famille » */
    profile_key: number;
    linked: boolean;
    username: string;
    linked_at: string | null;
}

export interface TraktAccounts {
    configured: boolean;
    profiles: TraktProfile[];
}

export interface TraktCode {
    device_code: string;
    user_code: string;
    verification_url: string;
    expires_in: number;
    interval: number;
}

export type TraktPollStatus = "pending" | "linked" | "expired" | "denied" | "invalid" | "used" | "error";

const KEY = ["trakt", "accounts"];

export function useTraktAccounts() {
    return useQuery({ queryKey: KEY, queryFn: () => apiFetch<TraktAccounts>("/api/trakt/accounts"), staleTime: 30_000 });
}

export function useTraktStartLink() {
    return useMutation({
        mutationFn: (profileKey: number) =>
            apiFetch<TraktCode>("/api/trakt/link", { method: "POST", body: JSON.stringify({ profile_key: profileKey }) }),
    });
}

export async function pollTraktLink(profileKey: number, deviceCode: string) {
    return apiFetch<{ status: TraktPollStatus; username?: string }>("/api/trakt/link/poll", {
        method: "POST",
        body: JSON.stringify({ profile_key: profileKey, device_code: deviceCode }),
    });
}

export function useTraktUnlink() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (profileKey: number) => apiFetch(`/api/trakt/link/${profileKey}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    });
}

export function useRefreshTrakt() {
    const qc = useQueryClient();
    return () => qc.invalidateQueries({ queryKey: KEY });
}
