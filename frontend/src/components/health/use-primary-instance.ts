"use client";

/**
 * Garde-fou « instance principale ».
 * ----------------------------------------------------------------
 * L'API médias d'ArrMada (`/api/media/{type}/{id}`, recherche, PATCH,
 * DELETE) parle toujours à la PREMIÈRE instance Radarr/Sonarr activée.
 * Avec deux instances (ex: « Radarr » + « Radarr 4K »), l'ID 42 d'un film
 * de la 2ᵉ instance désignerait un AUTRE film dans la 1ʳᵉ : supprimer ou
 * rechercher « au hasard » serait dangereux. On n'autorise donc les
 * actions que pour les médias de l'instance principale.
 * (Limite backend signalée : il faudrait passer l'ID du service.)
 */
import { useCallback, useMemo } from "react";
import { useServices } from "@/hooks/use-services";

export function usePrimaryInstance() {
    const { data: services, isLoading } = useServices();

    // Instance principale = instance activée de plus petit ID (ordre
    // d'insertion, celui que renvoie la base sans tri explicite).
    const primary = useMemo(() => {
        const pick = (type: string) =>
            (services ?? [])
                .filter((s) => s.is_enabled && s.type.toLowerCase() === type)
                .sort((a, b) => a.id - b.id);
        return { radarr: pick("radarr"), sonarr: pick("sonarr") };
    }, [services]);

    /**
     * true si les actions sont sûres pour un média de ce service.
     * Tant que la liste des services n'est pas chargée, ou s'il n'y a
     * qu'une instance du type, on autorise (cas de loin le plus courant).
     */
    const isActionable = useCallback(
        (serviceName: string | undefined, mediaType: "movie" | "series" | string) => {
            const list = mediaType === "series" ? primary.sonarr : primary.radarr;
            if (isLoading || list.length <= 1 || !serviceName) return true;
            return list[0].name === serviceName;
        },
        [primary, isLoading],
    );

    const primaryName = useCallback(
        (mediaType: "movie" | "series" | string) =>
            (mediaType === "series" ? primary.sonarr : primary.radarr)[0]?.name,
        [primary],
    );

    return { isActionable, primaryName };
}
