"use client";

/**
 * Actions sur un média : recherche automatique (*arr), recherche d'épisodes,
 * activité de recherche en direct, recherche interactive de releases et
 * envoi d'une release au client de téléchargement.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Recherche automatique (commande native *arr) ──────────── */

export function useTriggerMediaSearch() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; command: unknown },
        Error,
        { type: "movie" | "series"; id: number | string; season?: number }
    >({
        mutationFn: ({ type, id, season }) => {
            const qs = season !== undefined ? `?season=${season}` : "";
            return apiFetch(`/api/media/${type}/${id}/search${qs}`, { method: "POST" });
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ["media", "detail", variables.type, String(variables.id)],
            });
            // Série : l'indicateur « Recherche en cours » doit s'allumer tout de suite.
            if (variables.type === "series") {
                queryClient.invalidateQueries({ queryKey: ["media", "search-activity", String(variables.id)] });
            }
        },
    });
}

/* ── Recherche automatique d'épisodes précis (manquants) ───── */

export function useSearchEpisodes() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; command: unknown; count: number },
        Error,
        { id: number | string; episodeIds: number[] }
    >({
        mutationFn: ({ id, episodeIds }) =>
            apiFetch(`/api/media/series/${id}/search-episodes`, {
                method: "POST",
                body: JSON.stringify({ episode_ids: episodeIds }),
            }),
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({
                queryKey: ["media", "detail", "series", String(variables.id)],
            });
            queryClient.invalidateQueries({ queryKey: ["media", "search-activity", String(variables.id)] });
        },
    });
}

/* ── Activité de recherche en direct (file de commandes Sonarr) ── */

export interface SearchActivity {
    episode_ids: number[];
    seasons: number[];
    series_search: boolean;
    active: boolean;
}

/**
 * Quels épisodes / saisons d'une série sont en cours de recherche dans Sonarr
 * (pour afficher « Recherche… » au lieu d'un bouton qui semble figé).
 *
 * Avant : interrogation toutes les 4 s en permanence, même sans aucune
 * recherche. Désormais :
 *  - 1 lecture à l'ouverture de la page (et au retour sur l'onglet) ;
 *  - toutes les 4 s uniquement tant qu'une recherche est active ;
 *  - `opts.boost` force l'interrogation pendant quelques secondes juste après
 *    un lancement (le temps que Sonarr inscrive la commande dans sa file).
 */
export function useSeriesSearchActivity(
    id: number | string,
    enabled = true,
    opts: { boost?: boolean } = {},
) {
    const boost = !!opts.boost;
    return useQuery<SearchActivity>({
        queryKey: ["media", "search-activity", String(id)],
        queryFn: () => apiFetch(`/api/media/series/${id}/search-activity`),
        enabled: enabled && !!id,
        refetchInterval: (query) => (query.state.data?.active || boost ? 4000 : false),
        refetchOnWindowFocus: true,
        staleTime: 0,
    });
}

/* ── Recherche interactive de releases ─────────────────────── */

export interface Release {
    guid: string;
    indexer_id: number;
    indexer: string;
    title: string;
    size_bytes: number;
    seeders: number | null;
    leechers: number | null;
    age_days: number;
    quality: string;
    custom_format_score: number;
    custom_formats: string[];
    protocol: string;
    rejected: boolean;
    rejections: string[];
    download_url: string | null;
    info_url: string | null;
}

export interface ReleasesResponse {
    items: Release[];
    total: number;
}

/**
 * Releases candidates pour un média (recherche interactive).
 * Désactivé par défaut — passe `enabled` pour lancer la recherche (lente)
 * sur les indexeurs.
 */
export function useMediaReleases(
    type: "movie" | "series",
    id: number | string,
    enabled: boolean,
    season?: number,
    episode?: number,
) {
    // La recherche d'épisode (rapide : 1 requête par indexeur) prime sur la
    // recherche de pack saison (lente : éventail sur tous les épisodes).
    // Un seul des deux paramètres est envoyé au backend.
    const qs =
        type === "series"
            ? episode !== undefined
                ? `?episode=${episode}`
                : season !== undefined
                    ? `?season=${season}`
                    : ""
            : "";
    // Pour une série, il faut choisir une saison ou un épisode avant de chercher.
    const canQuery =
        enabled && !!id && (type === "movie" || season !== undefined || episode !== undefined);
    return useQuery<ReleasesResponse>({
        queryKey: ["media", "releases", type, String(id), season ?? null, episode ?? null],
        queryFn: () => apiFetch(`/api/media/${type}/${id}/releases${qs}`),
        enabled: canQuery,
        staleTime: 60_000,
        retry: false,
    });
}

/* ── Envoi d'une release au client de téléchargement ───────── */

export function useGrabRelease() {
    const queryClient = useQueryClient();
    return useMutation<
        { status: string; release: unknown },
        Error,
        {
            type: "movie" | "series";
            id: number | string;
            guid: string;
            indexer_id: number;
            /** Facultatifs : alimentent le journal d'activité côté backend. */
            title?: string;
            release_title?: string;
        }
    >({
        mutationFn: ({ type, id, guid, indexer_id, title, release_title }) =>
            apiFetch(`/api/media/${type}/${id}/grab`, {
                method: "POST",
                body: JSON.stringify({ guid, indexer_id, title, release_title }),
            }),
        onSuccess: (_data, variables) => {
            // La release part dans la file : la fiche (statut) et la page
            // Téléchargements doivent se rafraîchir.
            queryClient.invalidateQueries({
                queryKey: ["media", "detail", variables.type, String(variables.id)],
            });
            queryClient.invalidateQueries({ queryKey: ["downloads"] });
        },
    });
}
