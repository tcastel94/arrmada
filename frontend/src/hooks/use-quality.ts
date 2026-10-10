"use client";

/**
 * Suivi qualité de la médiathèque (onglet « Qualité » de /health).
 * ----------------------------------------------------------------
 * Le backend (`GET /api/quality`) analyse les fichiers Radarr/Sonarr et
 * renvoie : la répartition des qualités des films, quelques stats séries
 * et la liste des films « améliorables » (qualité < 1080p Bluray).
 * Attention : la liste `upgradeable.items` est plafonnée à 50 côté
 * serveur, alors que `upgradeable.count` est le vrai total → l'UI doit
 * afficher « 50 affichés sur 132 » et non laisser croire que tout est là.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Nombre maximum d'éléments renvoyés par le backend dans `upgradeable.items`. */
export const QUALITY_UPGRADE_LIMIT = 50;

/** Un film dont la qualité actuelle est sous le seuil 1080p Bluray. */
export interface UpgradeableItem {
    title: string;
    year?: number | null;
    type: "movie" | "series" | string;
    /** Nom de qualité *arr (ex: "WEBDL-720p", "Bluray-1080p"). */
    quality: string;
    /** Rang de qualité calculé par le backend (1 = SDTV … 10 = Remux 2160p, 0 = inconnu). */
    quality_tier: number;
    size_bytes: number;
    size_human: string;
    /** Nom du profil qualité Radarr/Sonarr. */
    profile: string;
    /** Nom de l'instance ArrMada (ex: "Radarr 4K"). */
    service: string;
    /** ID Radarr/Sonarr — sert au lien vers la fiche et à la recherche d'upgrade. */
    external_id?: number | string | null;
}

/** Part d'une qualité ou d'une résolution dans la médiathèque films. */
export interface QualityShare {
    count: number;
    percent: number;
}

export interface QualityOverview {
    movies: {
        total: number;
        /** Clé = nom de qualité *arr (ex: "Bluray-1080p"). */
        quality_distribution: Record<string, QualityShare>;
        /** Clé = "2160p" | "1080p" | "720p" | "SD" | "Other". */
        resolution_distribution: Record<string, QualityShare>;
    };
    series: {
        /** Nombre de séries ayant au moins un épisode sur disque. */
        total: number;
        total_episodes: number;
    };
    upgradeable: {
        /** Vrai total (la liste ci-dessous peut être tronquée). */
        count: number;
        items: UpgradeableItem[];
        total_current_size: string;
        /**
         * ESTIMATION grossière du backend : 10 Go par film en 1080p Bluray,
         * moins la taille actuelle. À afficher comme telle.
         */
        estimated_space_needed: string;
    };
}

// Voir use-cleanup.ts : « Rescanner » force le backend à ignorer son cache.
let forceQualityRefresh = false;

export function useQualityOverview() {
    const query = useQuery<QualityOverview>({
        queryKey: ["quality", "overview"],
        queryFn: () => {
            const refresh = forceQualityRefresh;
            forceQualityRefresh = false;
            return apiFetch<QualityOverview>(`/api/quality${refresh ? "?refresh=1" : ""}`);
        },
        // Analyse coûteuse (parcourt toute la bibliothèque) : le backend la
        // garde 10 min en cache, inutile de la redemander plus souvent.
        staleTime: 600_000,
    });
    const rescan = () => {
        forceQualityRefresh = true;
        return query.refetch();
    };
    return Object.assign(query, { rescan });
}
