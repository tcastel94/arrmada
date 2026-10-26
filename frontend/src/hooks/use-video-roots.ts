"use client";

/**
 * Dossiers vidéo : l'écran « Vidéos » de l'appli Android.
 * ----------------------------------------------------------------
 * Dossiers du NAS parcourus comme un explorateur de fichiers depuis les TV
 * et les téléphones : vidéos sans fiche officielle (mangas « Kai »,
 * montages, vidéos perso) que Radarr, Sonarr et Jellyfin ne rangent pas.
 * Le serveur refuse un dossier hors de VIDEO_ALLOWED_BASE (/mnt/user par
 * défaut, plusieurs bases possibles séparées par des virgules) ou absent du
 * conteneur : son erreur porte alors la ligne de volume à ajouter.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiRequestError, apiFetch } from "@/lib/api-client";

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

interface VideoRootsResponse {
    items: VideoRoot[];
    /** Bases où les dossiers sont acceptés (absent sur un serveur plus ancien). */
    bases?: string[];
}

/** Aide jointe à un refus : ligne de volume pour le docker-compose.yml et chemin à saisir. */
export interface VideoRootHint {
    message: string;
    volume_line: string | null;
    container_path: string | null;
}

/** Aide structurée d'une erreur d'ajout / modification, ou null (simple message). */
export function videoRootHint(error: unknown): VideoRootHint | null {
    if (!(error instanceof ApiRequestError)) return null;
    const d = error.detail;
    if (!d || typeof d !== "object" || !("message" in d)) return null;
    const hint = d as VideoRootHint;
    return hint.volume_line || hint.container_path ? hint : null;
}

const fetchRoots = () => apiFetch<VideoRootsResponse>("/api/videos/roots");

export function useVideoRoots() {
    return useQuery<VideoRootsResponse, Error, VideoRoot[]>({
        queryKey: VIDEO_ROOTS_KEY,
        queryFn: fetchRoots,
        select: (d) => d.items,
    });
}

/** Bases autorisées (même requête que la liste : un seul appel réseau). */
export function useVideoRootBases() {
    return useQuery<VideoRootsResponse, Error, string[]>({
        queryKey: VIDEO_ROOTS_KEY,
        queryFn: fetchRoots,
        select: (d) => d.bases ?? ["/mnt/user"],
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
