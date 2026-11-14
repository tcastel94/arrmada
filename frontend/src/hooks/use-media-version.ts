"use client";

/**
 * Version audio & qualité voulues pour UN film / UNE série.
 * ----------------------------------------------------------------
 * Radarr et Sonarr n'ont pas de « langue par film » : ils choisissent une
 * release d'après le PROFIL QUALITÉ du titre. Le serveur traduit donc un
 * choix lisible (VF, MULTi, VOSTFR, VO + qualité + doublage) en profil,
 * le crée s'il manque, et bascule le titre dessus.
 *
 *   GET  /api/media-version/{type}/{id}  → version actuelle, état du fichier
 *   PUT  /api/media-version/{type}/{id}  → changer (et relancer une recherche)
 *   POST /api/media-version/bulk         → même version pour une sélection
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type VersionLanguage = "vf" | "multi" | "vostfr" | "vo";
export type VersionQuality = "1080p" | "2160p";
export type VersionDub = "any" | "france" | "quebec";
/** none = réglage seul · search = recherche auto · replace = supprime le fichier puis cherche (films). */
export type VersionAction = "none" | "search" | "replace";

export interface MediaVersion {
    language: VersionLanguage;
    quality: VersionQuality;
    dub: VersionDub;
}

/** Une version proposable (les données TRaSH la fournissent). */
export interface VersionChoice extends MediaVersion {
    /** Nom du profil dans Radarr/Sonarr s'il existe déjà. */
    profile_name: string | null;
    installed: boolean;
}

export interface VersionFileState {
    has_file: boolean;
    /** Film : 0 ou 1. Série : nombre de fichiers d'épisodes. */
    files_total: number;
    files_matching: number;
    files_mismatching: number;
    /** Langues audio, la plus fréquente d'abord (« French », « English »…). */
    audio_languages: string[];
    /** Étiquettes lues dans le nom de la release : MULTi, VFF, VFQ, VF2… */
    tags: string[];
    /** null = impossible à dire (langues inconnues, ou profil hors table). */
    matches: boolean | null;
    reason: string | null;
}

export interface MediaVersionState {
    media_type: "movie" | "series";
    id: number;
    title: string;
    monitored: boolean;
    original_language: string | null;
    profile: { id: number; name: string } | null;
    /** null = le profil actuel n'est pas une version connue (profil fait main, profil d'origine…). */
    version: MediaVersion | null;
    quality_guess: VersionQuality;
    choices: VersionChoice[];
    file: VersionFileState;
}

export interface SetVersionResult {
    status: string;
    version: MediaVersion;
    profile: { id: number; name: string; created: boolean };
    /** false = le titre était déjà sur ce profil. */
    changed: boolean;
    action: VersionAction;
    file_deleted: boolean;
    monitored: boolean;
    warnings: string[];
}

export interface BulkVersionResult {
    status: string;
    total: number;
    changed: number;
    searched: number;
    created_profiles: string[];
    warnings: string[];
}

export function useMediaVersion(type: "movie" | "series", id: number | string, enabled = true) {
    return useQuery<MediaVersionState>({
        queryKey: ["media", "version", type, String(id)],
        queryFn: () => apiFetch<MediaVersionState>(`/api/media-version/${type}/${id}`),
        enabled: enabled && !!id,
        staleTime: 30_000,
        retry: 1,
    });
}

export function useSetMediaVersion() {
    const qc = useQueryClient();
    return useMutation<
        SetVersionResult,
        Error,
        { type: "movie" | "series"; id: number | string; version: MediaVersion; action: VersionAction }
    >({
        mutationFn: ({ type, id, version, action }) =>
            apiFetch<SetVersionResult>(`/api/media-version/${type}/${id}`, {
                method: "PUT",
                body: JSON.stringify({ ...version, action }),
            }),
        onSuccess: (_data, v) => {
            // La fiche (profil, fichier supprimé…), la liste et les options d'édition changent.
            qc.invalidateQueries({ queryKey: ["media", "version", v.type, String(v.id)] });
            qc.invalidateQueries({ queryKey: ["media", "detail", v.type, String(v.id)] });
            qc.invalidateQueries({ queryKey: ["media", "options", v.type] });
            qc.invalidateQueries({ queryKey: ["media"] });
            if (v.type === "series") qc.invalidateQueries({ queryKey: ["media", "search-activity", String(v.id)] });
        },
    });
}

export function useSetMediaVersionBulk() {
    const qc = useQueryClient();
    return useMutation<
        BulkVersionResult,
        Error,
        {
            items: { type: "movie" | "series"; id: number }[];
            language: VersionLanguage;
            /** null = chaque titre garde sa qualité actuelle. */
            quality: VersionQuality | null;
            dub: VersionDub;
            action: "none" | "search";
        }
    >({
        mutationFn: (body) =>
            apiFetch<BulkVersionResult>("/api/media-version/bulk", {
                method: "POST",
                body: JSON.stringify(body),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["media"] });
        },
    });
}
