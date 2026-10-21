"use client";

/**
 * Dossiers vidéo : l'écran « Vidéos » de l'appli Android.
 * ----------------------------------------------------------------
 * Dossiers du NAS parcourus comme un explorateur de fichiers depuis les TV
 * et les téléphones : vidéos sans fiche officielle (mangas « Kai »,
 * montages, vidéos perso) que Radarr, Sonarr et Jellyfin ne rangent pas.
 * Le serveur refuse un dossier hors de VIDEO_ALLOWED_BASE (/mnt/user).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface VideoRoot {
    id: number;
    /** Libellé affiché sur la TV (« Mangas Kai »). */
    name: string;
    /** Chemin vu par le serveur (« /mnt/user/medias/mangas-kai »). */
    path: string;
    /** Le dossier existe (montage du NAS présent). */
    available: boolean;
}

export interface VideoRootInput {
    name?: string;
    path?: string;
}

export const MAX_VIDEO_ROOTS = 30;

const VIDEO_ROOTS_KEY = ["video-roots"] as const;

export function useVideoRoots() {
    return useQuery<VideoRoot[]>({
        queryKey: VIDEO_ROOTS_KEY,
        queryFn: async () => (await apiFetch<{ items: VideoRoot[] }>("/api/videos/roots")).items,
    });
}

export function useCreateVideoRoot() {
    const qc = useQueryClient();
    return useMutation<VideoRoot, Error, VideoRootInput>({
        mutationFn: (body) => apiFetch("/api/videos/roots", { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: VIDEO_ROOTS_KEY }),
    });
}

export function useUpdateVideoRoot() {
    const qc = useQueryClient();
    return useMutation<VideoRoot, Error, { id: number } & VideoRootInput>({
        mutationFn: ({ id, ...body }) => apiFetch(`/api/videos/roots/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: VIDEO_ROOTS_KEY }),
    });
}

export function useDeleteVideoRoot() {
    const qc = useQueryClient();
    return useMutation<{ status: string }, Error, number>({
        mutationFn: (id) => apiFetch(`/api/videos/roots/${id}`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: VIDEO_ROOTS_KEY }),
    });
}
