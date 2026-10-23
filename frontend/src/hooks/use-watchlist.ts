"use client";

/**
 * Liste « À voir » par profil famille.
 * ----------------------------------------------------------------
 * La web app n'a pas de « profil connecté » : on choisit de quelle liste
 * on parle (« Famille », « Tom »…). Ce choix est mémorisé dans le
 * navigateur et partagé par toute l'app (bouton « Ma liste », rangée de
 * l'Accueil, page Ma liste) : un petit état global, comme une variable
 * d'environnement de session.
 * Les TV, elles, envoient leur profil d'elles-mêmes (en-tête X-Profile-Id).
 */
import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface WatchlistItem {
    key: string;
    media_type: "movie" | "series";
    id_type: "tmdb" | "tvdb";
    external_id: string;
    tmdb_id: number | null;
    tvdb_id: number | null;
    title: string;
    year: number | null;
    poster_url: string | null;
    fanart_url: string | null;
    overview: string;
    /** Dans Radarr / Sonarr. */
    in_library: boolean;
    /** Téléchargé (série : au moins un épisode). */
    has_file: boolean;
    /** Identifiant Radarr / Sonarr : fiche /media/<type>/<id>. */
    media_id: string | null;
    added_at: string | null;
}

/** Titre à ajouter (fiche, recherche, recommandation). */
export interface WatchlistTarget {
    media_type: "movie" | "series";
    tmdb_id?: number | null;
    tvdb_id?: number | null;
    title: string;
    year?: number | null;
    poster_url?: string | null;
}

export function watchlistKey(t: Pick<WatchlistTarget, "media_type" | "tmdb_id" | "tvdb_id">): string | null {
    const id = t.media_type === "movie" ? t.tmdb_id : t.tvdb_id;
    return id ? `${t.media_type}:${t.media_type === "movie" ? "tmdb" : "tvdb"}:${id}` : null;
}

/* ── Profil dont on affiche la liste (mémorisé, partagé entre composants) ── */

const STORAGE_KEY = "arrmada.watchlist.profile";
const listeners = new Set<(id: number | null) => void>();
let current: number | null | undefined;

function readStored(): number | null {
    try {
        const v = Number(localStorage.getItem(STORAGE_KEY));
        return Number.isFinite(v) && v > 0 ? v : null;
    } catch {
        return null; // stockage bloqué (navigation privée) : « Famille »
    }
}

/** [profil, changer] — null = « Famille ». */
export function useWatchlistProfile(): [number | null, (id: number | null) => void] {
    const [profile, setProfile] = useState<number | null>(null);
    useEffect(() => {
        if (current === undefined) current = readStored();
        setProfile(current);
        listeners.add(setProfile);
        return () => {
            listeners.delete(setProfile);
        };
    }, []);
    const change = useCallback((id: number | null) => {
        current = id;
        try {
            if (id) localStorage.setItem(STORAGE_KEY, String(id));
            else localStorage.removeItem(STORAGE_KEY);
        } catch {
            /* non mémorisé, sans gravité */
        }
        listeners.forEach((l) => l(id));
    }, []);
    return [profile, change];
}

const qs = (profile: number | null) => (profile ? `?profile=${profile}` : "");
const listKey = (profile: number | null) => ["watchlist", profile ?? 0] as const;

export function useWatchlist(profile: number | null) {
    return useQuery<WatchlistItem[]>({
        queryKey: listKey(profile),
        queryFn: async () => (await apiFetch<{ items: WatchlistItem[] }>(`/api/watchlist${qs(profile)}`)).items,
        staleTime: 30_000,
    });
}

export interface AddResult {
    item: WatchlistItem;
    download: { status: string; message?: string } | null;
}

export function useAddToWatchlist(profile: number | null) {
    const qc = useQueryClient();
    return useMutation<AddResult, Error, WatchlistTarget & { request?: boolean }>({
        mutationFn: (body) => apiFetch(`/api/watchlist${qs(profile)}`, { method: "POST", body: JSON.stringify(body) }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
    });
}

export function useRemoveFromWatchlist(profile: number | null) {
    const qc = useQueryClient();
    return useMutation<unknown, Error, Pick<WatchlistTarget, "media_type" | "tmdb_id" | "tvdb_id">>({
        mutationFn: (t) =>
            apiFetch(`/api/watchlist/${t.media_type}/${t.media_type === "movie" ? t.tmdb_id : t.tvdb_id}${qs(profile)}`, {
                method: "DELETE",
            }),
        // Retrait immédiat à l'écran (la requête suit)
        onMutate: async (t) => {
            const key = watchlistKey(t);
            await qc.cancelQueries({ queryKey: listKey(profile) });
            qc.setQueryData<WatchlistItem[]>(listKey(profile), (old) => old?.filter((i) => i.key !== key));
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
    });
}
