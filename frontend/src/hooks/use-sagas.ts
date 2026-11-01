"use client";

/**
 * Sagas de films (collections Radarr / TMDB), voir docs/adr/016-sagas.md.
 * ----------------------------------------------------------------
 * Radarr connaît déjà les sagas : ArrMada croise leur liste de films avec
 * la bibliothèque pour dire ce qui est sur le NAS, ce qui manque, ce qui
 * est annoncé. Mêmes routes /api/sagas pour la web app et l'appli TV.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/**
 * État d'un film dans une saga :
 * available (sur le NAS), wanted (dans Radarr, recherché), missing (sorti,
 * pas dans Radarr), upcoming (annoncé), excluded (écarté dans Radarr).
 */
export type SagaFilmState = "available" | "wanted" | "missing" | "upcoming" | "excluded";

export interface SagaFilm {
    tmdb_id: number;
    /** Identifiant Radarr si le film est dans la bibliothèque (lien vers sa fiche). */
    movie_id: number | null;
    title: string;
    year: number | null;
    overview: string | null;
    runtime: number | null;
    poster: string | null;
    state: SagaFilmState;
    /** Vu par le profil (vu partagé des TV). */
    watched: boolean;
    /** Film commencé : % (1-99), sinon null. */
    progress: number | null;
}

export interface Saga {
    id: number;
    tmdb_id: number;
    title: string;
    overview: string | null;
    poster: string | null;
    fanart: string | null;
    /** Trois affiches pour l'éventail. */
    posters: string[];
    monitored: boolean;
    total: number;
    available: number;
    wanted: number;
    missing: number;
    upcoming: number;
    /** Aucun film sorti ne manque. */
    complete: boolean;
    /** [première année, dernière année]. */
    years: number[];
    /** Films vus par le profil. */
    seen: number;
    /** Prochain film à voir (le premier sur le NAS pas encore vu), ou null. */
    next: SagaFilm | null;
    /** Films rangés dans l'ordre choisi à la main (sinon : ordre de sortie). */
    custom_order: boolean;
}

export interface SagaDetail extends Saga {
    films: SagaFilm[];
}

export interface SagaList {
    sagas: Saga[];
    total: number;
    incomplete: number;
    upcoming: number;
}

export function useSagas() {
    return useQuery({
        queryKey: ["sagas"],
        queryFn: () => apiFetch<SagaList>("/api/sagas"),
        staleTime: 60_000,
    });
}

export function useSaga(id: number) {
    return useQuery({
        queryKey: ["sagas", id],
        queryFn: () => apiFetch<SagaDetail>(`/api/sagas/${id}`),
        enabled: Number.isFinite(id) && id > 0,
    });
}

/** Saga d'un film de Radarr et sa place dedans (bloc de la fiche film). */
export function useMovieSaga(movieId: number, enabled = true) {
    return useQuery({
        queryKey: ["sagas", "movie", movieId],
        queryFn: () => apiFetch<{ saga: SagaDetail | null; position: number | null }>(`/api/sagas/movie/${movieId}`),
        enabled: enabled && movieId > 0,
        staleTime: 5 * 60_000,
        retry: false,
    });
}

/** « Compléter la saga » : tous les films sortis manquants, ou ceux choisis. */
export function useCompleteSaga() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, tmdbIds }: { id: number; tmdbIds?: number[] }) =>
            apiFetch<{ status: string; added: string[]; message: string }>(`/api/sagas/${id}/complete`, {
                method: "POST",
                body: JSON.stringify(tmdbIds ? { tmdb_ids: tmdbIds } : {}),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["sagas"] });
            qc.invalidateQueries({ queryKey: ["media"] });
        },
    });
}

/** « 6/8 films », « Complète », « 1 film annoncé »… : le badge d'une saga. */
export function sagaBadge(s: Pick<Saga, "missing" | "upcoming" | "wanted">): { label: string; tone: "ok" | "missing" | "soon" | "wanted" } {
    if (s.missing > 0) return { label: `${s.missing} film${s.missing > 1 ? "s" : ""} manquant${s.missing > 1 ? "s" : ""}`, tone: "missing" };
    if (s.wanted > 0) return { label: `${s.wanted} en recherche`, tone: "wanted" };
    if (s.upcoming > 0) return { label: `${s.upcoming} film${s.upcoming > 1 ? "s" : ""} annoncé${s.upcoming > 1 ? "s" : ""}`, tone: "soon" };
    return { label: "Complète", tone: "ok" };
}

interface ActionResult {
    status: string;
    message: string;
}

/** Suivre une saga : Radarr ajoute seul ses nouveaux films, ArrMada prévient. */
export function useFollowSaga() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, follow }: { id: number; follow: boolean }) =>
            apiFetch<ActionResult & { monitored: boolean }>(`/api/sagas/${id}/follow`, {
                method: "POST",
                body: JSON.stringify({ follow }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["sagas"] }),
    });
}

/** Ordre choisi à la main (identifiants TMDB des films), ou null : retour à l'ordre de sortie. */
export function useSagaOrder() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, tmdbIds }: { id: number; tmdbIds: number[] | null }) =>
            tmdbIds
                ? apiFetch<ActionResult>(`/api/sagas/${id}/order`, { method: "PUT", body: JSON.stringify({ tmdb_ids: tmdbIds }) })
                : apiFetch<ActionResult>(`/api/sagas/${id}/order`, { method: "DELETE" }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["sagas"] }),
    });
}

/** Collection Jellyfin d'une saga (id), ou de toutes les sagas (id absent). */
export function useJellyfinCollection() {
    return useMutation({
        mutationFn: (id?: number) =>
            apiFetch<ActionResult & { count: number }>(id ? `/api/sagas/${id}/jellyfin` : "/api/sagas/jellyfin", { method: "POST" }),
    });
}
