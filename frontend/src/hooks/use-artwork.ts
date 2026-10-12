"use client";

/**
 * Artworks (logos, disques, clearart, bannières) récupérés par le serveur sur
 * fanart.tv et TMDB — backend/app/services/artwork.py.
 * ----------------------------------------------------------------
 * - `useArtworkStatus` : progression de la récupération + sources configurées.
 *   Relu toutes les 1,5 s tant que le serveur travaille, sinon au besoin.
 * - `useArtworkRefresh` : bouton « Récupérer les artworks » (toute la
 *   médiathèque, en arrière-plan côté serveur).
 * - `useArtworkRefreshOne` : bouton d'une fiche (un seul titre, immédiat).
 * Quand une récupération se termine, la médiathèque et les fiches sont
 * relues : les nouveaux logos et disques apparaissent sans recharger la page.
 */
import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ArtworkStatus {
    running: boolean;
    total: number;
    done: number;
    found: number;
    errors: number;
    skipped: number;
    force: boolean;
    started_at: string | null;
    finished_at: string | null;
    message: string;
    sources: { fanart: boolean; tmdb: boolean };
    stored: { titles: number; logos: number; discs: number; clearart: number };
}

export interface ArtworkImages {
    clearlogo?: string;
    discart?: string;
    disc_type?: string;
    clearart?: string;
    banner?: string;
    landscape?: string;
    poster?: string;
    fanart?: string;
}

const STATUS_KEY = ["artwork", "status"];

export function useArtworkStatus() {
    const qc = useQueryClient();
    const query = useQuery<ArtworkStatus>({
        queryKey: STATUS_KEY,
        queryFn: () => apiFetch<ArtworkStatus>("/api/artwork/status"),
        refetchInterval: (q) => (q.state.data?.running ? 1500 : false),
        staleTime: 10_000,
    });

    // Fin de récupération (running : vrai → faux) : on relit la médiathèque.
    const wasRunning = useRef(false);
    const running = !!query.data?.running;
    useEffect(() => {
        if (wasRunning.current && !running) {
            qc.invalidateQueries({ queryKey: ["media"] });
            qc.invalidateQueries({ queryKey: ["downloads"] });
        }
        wasRunning.current = running;
    }, [running, qc]);

    return query;
}

export function useArtworkRefresh() {
    const qc = useQueryClient();
    return useMutation<ArtworkStatus, Error, { force?: boolean }>({
        mutationFn: ({ force }) =>
            apiFetch<ArtworkStatus>(`/api/artwork/refresh${force ? "?force=true" : ""}`, { method: "POST" }),
        onSuccess: (status) => qc.setQueryData(STATUS_KEY, status),
    });
}

export function useArtworkRefreshOne() {
    const qc = useQueryClient();
    return useMutation<
        { status: "ok" | "empty" | "error"; images: ArtworkImages },
        Error,
        { type: "movie" | "series"; id: string | number }
    >({
        mutationFn: ({ type, id }) => apiFetch(`/api/artwork/${type}/${id}/refresh`, { method: "POST" }),
        onSuccess: (_res, { type, id }) => {
            qc.invalidateQueries({ queryKey: ["media", "detail", type, String(id)] });
            qc.invalidateQueries({ queryKey: ["media"] });
            qc.invalidateQueries({ queryKey: STATUS_KEY });
        },
    });
}
