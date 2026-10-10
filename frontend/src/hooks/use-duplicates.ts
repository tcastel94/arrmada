"use client";

/**
 * Doublons (onglet « Doublons » de /health).
 * ----------------------------------------------------------------
 * `GET /api/duplicates` regroupe les médias par titre normalisé + année :
 *  - `duplicates` : même titre présent dans PLUSIEURS services
 *    (ex: Radarr ET Radarr 4K) → vrais doublons qui coûtent de la place.
 *  - `upgrade_opportunities` : même titre plusieurs fois dans le MÊME
 *    service avec des qualités différentes (raison `quality_variants`).
 *    Ce ne sont PAS des upgrades : l'UI les présente comme « Même service ».
 *    Cette liste est plafonnée à 20 côté serveur (`stats.total_upgrades`
 *    donne le vrai total).
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Taille max de `upgrade_opportunities` renvoyée par le backend. */
export const SAME_SERVICE_LIMIT = 20;

/** Une copie d'un titre dupliqué. */
export interface DuplicateItem {
    /** Nom de l'instance ArrMada qui détient cette copie. */
    source: string;
    /** Nom de qualité (films) — pour les séries, le backend renvoie l'ID de profil. */
    quality: string;
    size_human: string;
    /** false = l'entrée existe dans le service mais sans fichier sur disque. */
    has_file: boolean;
}

export interface DuplicateGroup {
    title: string;
    type: "movie" | "series" | string;
    year: number | null;
    copies: number;
    services: string[];
    total_size_bytes: number;
    total_size_human: string;
    items: DuplicateItem[];
    reason: "cross_service" | string;
}

/** Même titre présent plusieurs fois dans un même service. */
export interface SameServiceVariant {
    title: string;
    type: "movie" | "series" | string;
    year: number | null;
    service: string;
    qualities: string[];
    reason: "quality_variants" | string;
}

/** @deprecated ancien nom trompeur — conservé pour compatibilité. */
export type UpgradeOpportunity = SameServiceVariant;

export interface DuplicatesData {
    duplicates: DuplicateGroup[];
    upgrade_opportunities: SameServiceVariant[];
    stats: {
        total_duplicates: number;
        /** Vrai total des variantes « même service » (liste tronquée à 20). */
        total_upgrades: number;
        wasted_space_bytes: number;
        wasted_space_human: string;
    };
}

export function useDuplicates() {
    return useQuery<DuplicatesData>({
        queryKey: ["duplicates"],
        queryFn: () => apiFetch<DuplicatesData>("/api/duplicates"),
        staleTime: 300_000,
    });
}
