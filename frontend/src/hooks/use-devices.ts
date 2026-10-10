"use client";

/**
 * Appareils appairés (TV Kodi, écrans d'appoint) — ADR-003 § 4 et § 6.
 * ----------------------------------------------------------------
 * La TV affiche un code à 6 caractères ; on le valide ici en choisissant
 * le nom, la pièce et l'ampli de l'appareil. La TV reçoit alors son propre
 * jeton (plus besoin du mot de passe admin dans Kodi). Révoquer = le jeton
 * cesse de fonctionner immédiatement.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { YamahaRoom } from "@/hooks/use-yamaha";

export interface PairedDevice {
    id: number;
    name: string;
    room: YamahaRoom;
    /** Ampli Yamaha de la pièce ; null = le premier ampli actif. */
    avr_service_id: number | null;
    avr_name: string | null;
    /**
     * « tv » : Kodi (jeton « TV »). « screen » : écran d'appoint, la tablette
     * de la page /ecran (jeton en lecture seule, une seule route).
     */
    kind: "tv" | "screen";
    /** Ex. « Kodi 21.1 · Android » (envoyé par l'add-on). */
    platform: string | null;
    last_ip: string | null;
    created_at: string | null;
    last_seen_at: string | null;
}

export interface DeviceSettings {
    name: string;
    room: YamahaRoom;
    avr_service_id: number | null;
}

const DEVICES_KEY = ["devices"] as const;

export function useDevices() {
    return useQuery<PairedDevice[]>({
        queryKey: DEVICES_KEY,
        queryFn: () => apiFetch("/api/devices"),
        // « Vu il y a… » : se rafraîchit seul, sans marteler le serveur
        refetchInterval: 60_000,
    });
}

/** Valide le code affiché par la TV. */
export function usePairDevice() {
    const qc = useQueryClient();
    return useMutation<{ status: string; device: PairedDevice }, Error, DeviceSettings & { user_code: string }>({
        mutationFn: (body) =>
            apiFetch("/api/devices/pair/confirm", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: DEVICES_KEY }),
    });
}

export function useUpdateDevice() {
    const qc = useQueryClient();
    return useMutation<PairedDevice, Error, DeviceSettings & { id: number }>({
        mutationFn: ({ id, avr_service_id, ...rest }) =>
            apiFetch(`/api/devices/${id}`, {
                method: "PATCH",
                // « Premier ampli actif » = on efface l'ampli choisi
                body: JSON.stringify(
                    avr_service_id === null ? { ...rest, clear_avr: true } : { ...rest, avr_service_id }
                ),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: DEVICES_KEY }),
    });
}

export function useRevokeDevice() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/devices/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: DEVICES_KEY }),
    });
}

/** « k7p-4qx » → « K7P4QX » (même règle que le backend). */
export function normalizePairCode(value: string): string {
    return value.toUpperCase().replace(/[^A-Z0-9]/g, "");
}
