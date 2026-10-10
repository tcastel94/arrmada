"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { YamahaPresetResult } from "@/hooks/use-yamaha";

/* ── Watched / resume status (library badges) ──────────────── */

export interface KodiWatchedEntry {
    playcount: number;
    resume_position: number; // seconds
    resume_total: number; // seconds
    lastplayed: string | null;
    title: string;
    year: number | null;
}

/** Map keyed by TMDB id → watched/resume state from Kodi. */
export function useKodiWatchedStatus(enabled = true) {
    return useQuery<Record<string, KodiWatchedEntry>>({
        queryKey: ["kodi", "watched"],
        queryFn: () => apiFetch("/api/kodi/watched-status"),
        enabled,
        staleTime: 60_000,
    });
}

/* ── Play on Kodi ──────────────────────────────────────────── */

/**
 * Pièce où l'on regarde. Le backend lance la lecture sur Kodi PUIS applique
 * à l'ampli Yamaha le préréglage de cette pièce (volume, programme sonore,
 * dialogues…). Sans précision, il choisit « salon ».
 */
export type KodiRoom = "salon" | "cinema";

/** Réponse de POST /api/kodi/play. */
export interface KodiPlayResult {
    /** "ok", "not_found" (film absent de la bibliothèque Kodi) ou "error". */
    status: string;
    detail?: string;
    /** Nom de l'instance Kodi qui a lancé la lecture. */
    kodi?: string;
    movieid?: number;
    /** Pièce effectivement utilisée pour le préréglage de l'ampli. */
    room?: string;
    /**
     * Résultat du réglage de l'ampli (null si l'appel a échoué en interne,
     * absent sur un backend plus ancien). `status: "error"` + `detail` quand
     * aucun ampli n'est configuré ou qu'il n'a pas répondu.
     */
    avr?: YamahaPresetResult | null;
}

export function useKodiPlay() {
    return useMutation<KodiPlayResult, Error, { tmdb_id: number; service_id?: number; room?: KodiRoom }>({
        mutationFn: (body) =>
            apiFetch("/api/kodi/play", { method: "POST", body: JSON.stringify(body) }),
    });
}

/* ── Now playing + remote control ──────────────────────────── */

export interface KodiNowPlaying {
    playing: boolean;
    playerid?: number;
    title?: string;
    subtitle?: string;
    type?: string;
    tmdb?: string | null;
    year?: number | null;
    overview?: string;
    genres?: string[];
    rating?: number | null;
    runtime?: number | null; // minutes
    position?: number; // seconds
    total?: number; // seconds
    percentage?: number;
    paused?: boolean;
    volume?: number;
    muted?: boolean;
    kodi?: string;
    poster?: string | null;
    media_id?: string | null;
    media_type?: string | null;
    // stream technical details
    resolution?: string | null;
    video_codec?: string | null;
    hdr?: string | null;
    audio_codec?: string | null;
    audio_channels?: number | null;
    audio_language?: string | null;
    subtitle_count?: number;
}

/**
 * État de lecture Kodi.
 * Interrogation adaptative : toutes les 3 s pendant une lecture (barre de
 * progression fluide), toutes les 20 s au repos, 60 s si Kodi ne répond pas
 * (avant : 3 s en permanence ≈ 1 200 requêtes/heure pour rien).
 */
export function useKodiNowPlaying(enabled = true) {
    return useQuery<KodiNowPlaying>({
        queryKey: ["kodi", "now-playing"],
        queryFn: () => apiFetch("/api/kodi/now-playing"),
        enabled,
        refetchInterval: enabled
            ? (query) => {
                  if (query.state.status === "error") return 60_000;
                  return query.state.data?.playing ? 3_000 : 20_000;
              }
            : false,
        retry: 1,
        staleTime: 0,
    });
}

export function useKodiControl() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; detail?: string },
        Error,
        { action: "playpause" | "stop" | "seek" | "volume" | "mute"; value?: number }
    >({
        mutationFn: async (body) => {
            const res = await apiFetch<{ status: string; detail?: string }>("/api/kodi/control", {
                method: "POST",
                body: JSON.stringify(body),
            });
            // Le backend répond 200 avec {status:"error"} quand Kodi refuse :
            // on le remonte comme une vraie erreur pour afficher un toast.
            if (res?.status === "error") throw new Error(res.detail || "Kodi n'a pas accepté la commande");
            return res;
        },
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi", "now-playing"] }),
    });
}

/* ── Maintenance ───────────────────────────────────────────── */

export interface KodiDrift {
    radarr_total: number;
    kodi_total: number;
    missing_count: number;
    missing_in_kodi: { tmdb_id: string; title: string; year: number | null }[];
}

export function useKodiDrift(enabled = true) {
    return useQuery<KodiDrift>({
        queryKey: ["kodi", "drift"],
        queryFn: () => apiFetch("/api/kodi/drift"),
        enabled,
        staleTime: 60_000,
    });
}

/**
 * Nettoyage de la bibliothèque Kodi (VideoLibrary.Clean : retire les
 * entrées dont le fichier n'existe plus). Le backend répond 200 même en
 * cas d'échec ({status:"error"}) : on le convertit en vraie erreur.
 */
export function useKodiClean() {
    const qc = useQueryClient();
    return useMutation<{ status: string; detail?: string; kodi?: string }, Error, { service_id?: number } | void>({
        mutationFn: async (body) => {
            const res = await apiFetch<{ status: string; detail?: string; kodi?: string }>("/api/kodi/clean", {
                method: "POST",
                body: JSON.stringify(body || {}),
            });
            if (res?.status === "error") throw new Error(res.detail || "Kodi a refusé le nettoyage");
            return res;
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["kodi", "drift"] });
            qc.invalidateQueries({ queryKey: ["kodi", "watched"] });
        },
    });
}

/** Scan de bibliothèque sur tous les Kodi : renvoie le nombre de succès / échecs. */
export function useKodiSync() {
    const qc = useQueryClient();
    return useMutation<{ success: number; failed: number }, Error, void>({
        mutationFn: () => apiFetch("/api/kodi/sync", { method: "POST" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi"] }),
    });
}

/* ── Settings (instances) ──────────────────────────────────── */

/**
 * Instance Kodi telle que renvoyée par GET /api/kodi/settings.
 * SÉCURITÉ : le backend ne renvoie plus le mot de passe (avant : en clair),
 * seulement l'utilisateur et un booléen `has_password`.
 * `api_key` n'existe plus que pour un backend ancien (non utilisé).
 */
export interface KodiInstance {
    id: number;
    name: string;
    url: string;
    is_enabled: boolean;
    username?: string;
    has_password?: boolean;
    /** @deprecated ancien format "user:pass" — n'est plus exposé. */
    api_key?: string;
}

/** Utilisateur Kodi, quel que soit le format renvoyé par le backend. */
export function kodiUsername(k: KodiInstance): string {
    if (k.username !== undefined) return k.username;
    return k.api_key?.split(":")[0] ?? "";
}

/** Corps envoyé pour créer / modifier un Kodi. */
export interface KodiSettingsPayload {
    name: string;
    url: string;
    username: string;
    /** Vide = conserver le mot de passe déjà enregistré. */
    password: string;
    is_enabled?: boolean;
}

/**
 * Convertit le formulaire en corps d'API. `api_key` ("user:pass") n'est
 * envoyé que si un nouveau mot de passe est saisi, pour qu'un backend
 * ancien n'écrase jamais le mot de passe existant par un mot de passe vide.
 */
function kodiBody(p: KodiSettingsPayload) {
    return {
        name: p.name,
        url: p.url,
        username: p.username,
        password: p.password,
        is_enabled: p.is_enabled ?? true,
        ...(p.password ? { api_key: `${p.username}:${p.password}` } : {}),
    };
}

export function useKodiSettings() {
    return useQuery<KodiInstance[]>({
        queryKey: ["kodi", "settings"],
        queryFn: () => apiFetch("/api/kodi/settings"),
    });
}

export function useAddKodi() {
    const qc = useQueryClient();
    return useMutation<{ id: number; message: string }, Error, KodiSettingsPayload>({
        mutationFn: (body) =>
            apiFetch("/api/kodi/settings", { method: "POST", body: JSON.stringify(kodiBody(body)) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi"] }),
    });
}

/** Modifier un Kodi existant (y compris son URL) sans créer de doublon. */
export function useUpdateKodi() {
    const qc = useQueryClient();
    return useMutation<{ id: number; message: string }, Error, { id: number } & KodiSettingsPayload>({
        mutationFn: ({ id, ...body }) =>
            apiFetch(`/api/kodi/settings/${id}`, { method: "PUT", body: JSON.stringify(kodiBody(body)) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi"] }),
    });
}

export function useDeleteKodi() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/kodi/settings/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["kodi"] }),
    });
}

export function useTestKodi() {
    return useMutation<
        { ok: boolean; version?: string; name?: string; detail?: string },
        Error,
        number
    >({
        mutationFn: (id) => apiFetch(`/api/kodi/test/${id}`, { method: "POST" }),
    });
}

/** Découverte mDNS : peut renvoyer plusieurs Kodi (salon, chambre…). */
export function useKodiDiscover() {
    return useMutation<{ name: string; url: string }[], Error, void>({
        mutationFn: () => apiFetch("/api/kodi/discover"),
    });
}
