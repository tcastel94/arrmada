"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Live state ─────────────────────────────────────────────── */

export interface YamahaDevice {
    id: number;
    name: string;
    url: string;
    online: boolean;
    power?: "on" | "standby";
    volume?: number;
    max_volume?: number;
    volume_pct?: number;
    mute?: boolean;
    input?: string;
    actual_db?: number | null;
    sound_program?: string;
    error?: string;
}

export interface YamahaState {
    devices: YamahaDevice[];
}

/** Poll the live AVR state. Poll only while `enabled`. */
export function useYamahaState(enabled = true, serviceId?: number) {
    return useQuery<YamahaState>({
        queryKey: ["yamaha", "state", serviceId ?? null],
        queryFn: () =>
            apiFetch(`/api/yamaha/state${serviceId ? `?service_id=${serviceId}` : ""}`),
        enabled,
        refetchInterval: enabled ? 4000 : false,
        staleTime: 0,
    });
}

export function useYamahaControl() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; detail?: string },
        Error,
        {
            action: "volume" | "volume_step" | "mute" | "power" | "input" | "sound_program" | "dialog_lift" | "dialog_level" | "enhancer" | "extra_bass" | "adaptive_drc";
            value?: number | string | boolean;
            service_id?: number;
            zone?: string;
        }
    >({
        mutationFn: (body) =>
            apiFetch("/api/yamaha/control", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["yamaha", "state"] }),
    });
}

export function useYamahaInputs(serviceId?: number, enabled = true) {
    return useQuery<string[]>({
        queryKey: ["yamaha", "inputs", serviceId ?? null],
        queryFn: () =>
            apiFetch(`/api/yamaha/inputs${serviceId ? `?service_id=${serviceId}` : ""}`),
        enabled,
        staleTime: 5 * 60_000,
    });
}

export interface RoomProfile {
    name: string;
    volume_pct: number;
    volume_raw: number;
    dialog_lift: number;
    dialog_level: number;
    movie_sound_program: string;
    series_sound_program: string;
    music_sound_program: string;
    adaptive_drc: boolean;
    enhancer: boolean;
    extra_bass: boolean;
    input?: string | null;
}

export function useYamahaProfiles() {
    return useQuery<Record<string, RoomProfile>>({
        queryKey: ["yamaha", "profiles"],
        queryFn: () => apiFetch("/api/yamaha/profiles"),
    });
}

export function useSaveYamahaProfile() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; room: string; profile: RoomProfile },
        Error,
        { room: string; profile: Partial<RoomProfile> }
    >({
        mutationFn: (body) =>
            apiFetch("/api/yamaha/profiles", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["yamaha", "profiles"] });
            qc.invalidateQueries({ queryKey: ["yamaha", "state"] });
        },
    });
}

export function useApplyYamahaPreset() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; device?: string; applied?: Record<string, any>; detail?: string },
        Error,
        { room: "salon" | "cinema" | string; media_type?: string; audio_codec?: string; audio_channels?: number; service_id?: number }
    >({
        mutationFn: (body) =>
            apiFetch("/api/yamaha/preset/apply", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["yamaha", "state"] }),
    });
}

/* ── Settings (instances) ───────────────────────────────────── */

export interface YamahaInstance {
    id: number;
    name: string;
    url: string;
    is_enabled: boolean;
}

export function useYamahaSettings() {
    return useQuery<YamahaInstance[]>({
        queryKey: ["yamaha", "settings"],
        queryFn: () => apiFetch("/api/yamaha/settings"),
    });
}

export function useAddYamaha() {
    const qc = useQueryClient();
    return useMutation<
        { id: number; message: string },
        Error,
        { name: string; url: string; is_enabled?: boolean }
    >({
        mutationFn: (body) =>
            apiFetch("/api/yamaha/settings", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["yamaha", "settings"] });
            qc.invalidateQueries({ queryKey: ["yamaha", "state"] });
        },
    });
}

export function useDeleteYamaha() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/yamaha/settings/${id}`, { method: "DELETE" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["yamaha", "settings"] });
            qc.invalidateQueries({ queryKey: ["yamaha", "state"] });
        },
    });
}

export function useTestYamaha() {
    return useMutation<
        { ok: boolean; model?: string; api_version?: number; power?: string; volume_pct?: number; detail?: string },
        Error,
        number
    >({
        mutationFn: (id) => apiFetch(`/api/yamaha/test/${id}`, { method: "POST" }),
    });
}

export function useYamahaDiscover() {
    return useMutation<{ url: string; model_name: string; device_id?: string }[], Error, void>({
        mutationFn: () => apiFetch("/api/yamaha/discover"),
    });
}
