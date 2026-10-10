"use client";

/**
 * Indicateurs dérivés de la file de téléchargement.
 * ----------------------------------------------------------------
 * L'API ne renvoie ni débit ni affiche : on les reconstitue côté navigateur.
 *
 * - Débit ESTIMÉ : la file est relue toutes les 10 s ; entre deux lectures,
 *   la baisse de « taille restante » d'un élément divisée par le temps écoulé
 *   donne sa vitesse. Lissé (moyenne mobile) pour éviter les sauts. Rien
 *   n'est affiché tant qu'on n'a pas deux mesures.
 * - Affiches : si la médiathèque a déjà été chargée pendant la session, ses
 *   affiches sont dans le cache React Query ; on s'en sert gratuitement
 *   (aucune requête supplémentaire).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { queueItemKey, type DownloadItem } from "@/hooks/use-downloads";

interface Snapshot {
    at: number;
    left: Map<string, number>;
}

export interface Throughput {
    /** Octets/seconde estimés, toutes lignes confondues (0 = inconnu). */
    total: number;
    /** Octets/seconde estimés par ligne (clé `type-id`). */
    byKey: Record<string, number>;
}

/** Poids de la nouvelle mesure dans la moyenne mobile (0 → 1). */
const SMOOTHING = 0.55;

export function useThroughput(items: DownloadItem[] | undefined, updatedAt: number): Throughput {
    const prev = useRef<Snapshot | null>(null);
    const [state, setState] = useState<Throughput>({ total: 0, byKey: {} });

    useEffect(() => {
        if (!items || !updatedAt) return;
        const left = new Map(items.map((it) => [queueItemKey(it), it.size_left_bytes]));
        const before = prev.current;
        prev.current = { at: updatedAt, left };
        if (!before) return;
        const dt = (updatedAt - before.at) / 1000;
        if (dt < 2) return; // deux lectures trop rapprochées : mesure non fiable

        setState((old) => {
            const byKey: Record<string, number> = {};
            let total = 0;
            left.forEach((nowLeft, key) => {
                const was = before.left.get(key);
                if (was === undefined) return;
                const instant = Math.max(0, (was - nowLeft) / dt);
                const smoothed = old.byKey[key] !== undefined ? old.byKey[key] * (1 - SMOOTHING) + instant * SMOOTHING : instant;
                // Sous ~1 Ko/s, on considère que ça ne bouge pas.
                if (smoothed > 1024) {
                    byKey[key] = smoothed;
                    total += smoothed;
                }
            });
            return { total, byKey };
        });
    }, [items, updatedAt]);

    return state;
}

interface CachedMedia {
    type?: string;
    external_id?: string | number;
    poster_url?: string | null;
}

/**
 * Table « movie-12 » / « series-7 » → URL d'affiche, construite à partir des
 * listes de médias déjà présentes dans le cache.
 */
export function useCachedPosters(items: DownloadItem[] | undefined): Record<string, string> {
    const qc = useQueryClient();
    // La table ne dépend que des ids présents dans la file.
    const signature = (items ?? []).map((it) => `${it.movie_id ?? ""}:${it.series_id ?? ""}`).join("|");

    return useMemo(() => {
        const map: Record<string, string> = {};
        if (!signature) return map;
        for (const [, data] of qc.getQueriesData<unknown>({ queryKey: ["media"] })) {
            const list = (data as { items?: unknown } | undefined)?.items;
            if (!Array.isArray(list)) continue;
            for (const raw of list as CachedMedia[]) {
                if (raw && raw.poster_url && raw.type && raw.external_id !== undefined) {
                    map[`${raw.type}-${raw.external_id}`] = raw.poster_url;
                }
            }
        }
        return map;
    }, [signature, qc]);
}

/** Affiche connue pour un élément (fournie par l'API ou trouvée dans le cache). */
export function posterFor(item: DownloadItem, cached: Record<string, string>): string | null {
    if (item.poster_url) return item.poster_url;
    if (item.movie_id) return cached[`movie-${item.movie_id}`] ?? null;
    if (item.series_id) return cached[`series-${item.series_id}`] ?? null;
    return null;
}
