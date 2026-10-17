"use client";

/**
 * Ampli Yamaha (API « YamahaExtendedControl » / MusicCast).
 * ----------------------------------------------------------------
 * - useYamahaState : état en direct (marche, volume, entrée…) interrogé
 *   toutes les 4 s tant que la télécommande est affichée.
 * - useYamahaControl : envoie une commande avec mise à jour OPTIMISTE :
 *   le bouton change d'état tout de suite (sensation « télécommande
 *   physique »), puis l'état réel est relu ; en cas de refus, on revient
 *   en arrière et on affiche une erreur.
 * - Profils audio par pièce (Salon / Salle de cinéma) : lecture,
 *   enregistrement (fichier JSON côté backend) et application d'un
 *   préréglage sur l'ampli.
 */
import { useQuery, useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
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

export type YamahaAction =
    | "volume"
    | "volume_step"
    | "mute"
    | "power"
    | "input"
    /** Programme DSP (id YXC : "straight", "sci-fi", "7ch_stereo"…). */
    | "sound_program"
    /** Rehaussement des dialogues (0-5) : remonte les voix vers l'écran. */
    | "dialog_lift"
    /** Niveau des dialogues (0-3) : renforce leur intelligibilité. */
    | "dialog_level"
    | "enhancer"
    | "extra_bass"
    /** DRC adaptatif = « mode nuit » (compression de la dynamique). */
    | "adaptive_drc";

export interface YamahaControlVars {
    action: YamahaAction;
    value?: number | string | boolean;
    service_id?: number;
    zone?: string;
}

/** Applique localement l'effet attendu d'une commande sur un appareil. */
function applyOptimistic(device: YamahaDevice, vars: YamahaControlVars): YamahaDevice {
    const max = device.max_volume ?? 161;
    const pct = (v: number) => Math.round((v / max) * 100);
    switch (vars.action) {
        case "power":
            return { ...device, power: vars.value === "on" ? "on" : "standby" };
        case "mute":
            return { ...device, mute: Boolean(vars.value) };
        case "input":
            return { ...device, input: String(vars.value) };
        case "sound_program":
            return { ...device, sound_program: String(vars.value) };
        case "volume": {
            const v = Math.max(0, Math.min(max, Number(vars.value) || 0));
            return { ...device, volume: v, volume_pct: pct(v) };
        }
        case "volume_step": {
            const v = Math.max(0, Math.min(max, (device.volume ?? 0) + (Number(vars.value) || 0)));
            return { ...device, volume: v, volume_pct: pct(v) };
        }
        // Voix, enhancer, extra bass, DRC : l'état de l'ampli ne les remonte
        // pas (cf. backend _zone_status), rien à prédire localement.
        default:
            return device;
    }
}

export function useYamahaControl() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; detail?: string },
        Error,
        YamahaControlVars,
        { snapshots: [QueryKey, YamahaState | undefined][] }
    >({
        mutationFn: async (body) => {
            const res = await apiFetch<{ status: string; detail?: string }>("/api/yamaha/control", {
                method: "POST",
                body: JSON.stringify(body),
            });
            // Le backend répond 200 + {status:"error"} quand l'ampli refuse.
            if (res?.status === "error") throw new Error(res.detail || "L'ampli n'a pas accepté la commande");
            return res;
        },
        onMutate: async (vars) => {
            // On fige les requêtes en vol (sinon un vieux résultat écraserait l'état optimiste).
            await qc.cancelQueries({ queryKey: ["yamaha", "state"] });
            const snapshots = qc.getQueriesData<YamahaState>({ queryKey: ["yamaha", "state"] });
            qc.setQueriesData<YamahaState>({ queryKey: ["yamaha", "state"] }, (old) =>
                old
                    ? {
                          devices: old.devices.map((d) =>
                              vars.service_id === undefined || d.id === vars.service_id ? applyOptimistic(d, vars) : d,
                          ),
                      }
                    : old,
            );
            return { snapshots };
        },
        onError: (_err, _vars, ctx) => {
            ctx?.snapshots.forEach(([key, data]) => qc.setQueryData(key, data));
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ["yamaha", "state"] }),
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

/* ── Profils audio par pièce ────────────────────────────────── */

/** Pièces connues du backend (clés du fichier de profils). */
export type YamahaRoom = "salon" | "cinema";

/**
 * Réglages appliqués d'un clic par « Préréglage Salon / Cinéma ».
 * Le programme sonore dépend du type de média en cours (film, série,
 * musique) ; le volume est plafonné à 140 (sur 161) par le backend.
 */
export interface RoomProfile {
    name: string;
    /** Indicatif (affichage) : seul `volume_raw` est envoyé à l'ampli. */
    volume_pct: number;
    /** Volume brut YXC (0..max_volume, 161 sur la plupart des amplis). */
    volume_raw: number;
    dialog_lift: number;
    dialog_level: number;
    movie_sound_program: string;
    series_sound_program: string;
    music_sound_program: string;
    adaptive_drc: boolean;
    enhancer: boolean;
    extra_bass: boolean;
    /** Entrée à sélectionner ; null = ne pas changer de source. */
    input?: string | null;
}

export type RoomProfiles = Record<YamahaRoom, RoomProfile>;

const PROFILES_KEY = ["yamaha", "profiles"] as const;

export function useYamahaProfiles() {
    return useQuery<RoomProfiles>({
        queryKey: PROFILES_KEY,
        queryFn: () => apiFetch("/api/yamaha/profiles"),
        staleTime: 5 * 60_000, // ne change que quand tu l'enregistres
    });
}

export function useSaveYamahaProfile() {
    const qc = useQueryClient();
    return useMutation<
        { status: string; room: string; profile: RoomProfile },
        Error,
        { room: YamahaRoom; profile: Partial<RoomProfile> }
    >({
        mutationFn: (body) => apiFetch("/api/yamaha/profiles", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: (res, { room }) => {
            // Le backend renvoie le profil fusionné : on l'écrit directement
            // dans le cache (le formulaire voit la version enregistrée sans
            // attendre une relecture).
            if (res?.profile) qc.setQueryData<RoomProfiles>(PROFILES_KEY, (old) => (old ? { ...old, [room]: res.profile } : old));
            qc.invalidateQueries({ queryKey: PROFILES_KEY });
        },
    });
}

/** Contexte de lecture : choisit le programme films / séries / musique. */
export interface YamahaPresetVars {
    room: YamahaRoom;
    /** "movie" (défaut) | "episode"/"series"/"tv" | "music"/"audio"/"track". */
    media_type?: string;
    audio_codec?: string;
    /** ≤ 2 canaux au Salon → décodeur surround forcé par le backend. */
    audio_channels?: number;
    service_id?: number;
}

/** Ce que le backend a réellement appliqué (clés absentes = ignorées). */
export interface YamahaPresetApplied {
    room: string;
    power?: "on";
    input?: string;
    sound_program?: string;
    volume?: number;
    dialog_lift?: number;
    dialog_level?: number;
    enhancer?: boolean;
    extra_bass?: boolean;
    adaptive_drc?: boolean;
}

export interface YamahaPresetResult {
    status: string;
    device?: string;
    applied?: YamahaPresetApplied;
    detail?: string;
}

export function useApplyYamahaPreset() {
    const qc = useQueryClient();
    return useMutation<YamahaPresetResult, Error, YamahaPresetVars>({
        mutationFn: async (body) => {
            const res = await apiFetch<YamahaPresetResult>("/api/yamaha/preset/apply", {
                method: "POST",
                body: JSON.stringify(body),
            });
            // Même convention que /control : 200 + {status:"error"} si l'ampli refuse.
            if (res?.status === "error") throw new Error(res.detail || "L'ampli n'a pas accepté le préréglage");
            return res;
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ["yamaha", "state"] }),
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

/** Le backend renvoie parfois 200 + {status:"error"} (ex: URL vide). */
async function checkedYamahaWrite(path: string, method: string, body: unknown) {
    const res = await apiFetch<{ id?: number; message?: string; status?: string; detail?: string }>(path, {
        method,
        body: JSON.stringify(body),
    });
    if (res?.status === "error") throw new Error(res.detail || "Enregistrement refusé");
    return res as { id: number; message: string };
}

export function useAddYamaha() {
    const qc = useQueryClient();
    return useMutation<{ id: number; message: string }, Error, { name: string; url: string; is_enabled?: boolean }>({
        mutationFn: (body) => checkedYamahaWrite("/api/yamaha/settings", "POST", body),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["yamaha"] }),
    });
}

/** Modifier un ampli (nom, URL) sans créer de doublon. */
export function useUpdateYamaha() {
    const qc = useQueryClient();
    return useMutation<
        { id: number; message: string },
        Error,
        { id: number; name: string; url: string; is_enabled?: boolean }
    >({
        mutationFn: ({ id, ...body }) => checkedYamahaWrite(`/api/yamaha/settings/${id}`, "PUT", body),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["yamaha"] }),
    });
}

export function useDeleteYamaha() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/yamaha/settings/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["yamaha"] }),
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
