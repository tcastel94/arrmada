"use client";

/**
 * Lancement des recherches automatiques Radarr/Sonarr pour les manquants.
 * ----------------------------------------------------------------
 * Corrige plusieurs défauts de l'ancienne page :
 *  - recherche groupée = UN seul toast de progression (« 12/50 ») mis à
 *    jour, puis un récapitulatif — au lieu d'un toast par média ;
 *  - boucle annulable (bouton Stop) et arrêtée automatiquement quand on
 *    quitte la page (sinon elle continuait en arrière-plan) ;
 *  - état `running` dédié : l'ancien `triggerSearch.isPending` clignotait
 *    entre deux médias et réactivait les boutons au milieu de la boucle.
 * Les recherches partent une par une pour ne pas bombarder les indexers.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { MediaItem } from "@/hooks/use-media";
import { useTriggerMediaSearch } from "@/hooks/use-media-actions";
import { plural } from "@/lib/format";
import { mediaKey } from "./media-card";

/** État de la recherche d'une ligne (absent = jamais lancée). */
export type RowSearchState = "searching" | "launched" | "failed";

export interface BulkProgress {
    done: number;
    total: number;
    ok: number;
    failed: number;
    /** Titre en cours de traitement. */
    current: string;
}

export function useBulkSearch() {
    const { mutateAsync } = useTriggerMediaSearch();
    const [rowStates, setRowStates] = useState<Record<string, RowSearchState>>({});
    const [progress, setProgress] = useState<BulkProgress | null>(null);
    const cancelRef = useRef(false);
    const runningRef = useRef(false);
    const mountedRef = useRef(true);

    // Démontage (changement de page de l'app) → on stoppe la boucle.
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            cancelRef.current = true;
        };
    }, []);

    const setRow = useCallback((key: string, state: RowSearchState) => {
        if (mountedRef.current) setRowStates((prev) => ({ ...prev, [key]: state }));
    }, []);

    /** Une recherche ; `silent` = pas de toast (utilisé par la boucle groupée). */
    const searchOne = useCallback(
        async (item: MediaItem, silent = false): Promise<boolean> => {
            const key = mediaKey(item);
            setRow(key, "searching");
            try {
                await mutateAsync({ type: item.type, id: item.external_id });
                setRow(key, "launched");
                if (!silent) {
                    toast.success(`Recherche lancée : ${item.title}`, {
                        description: item.monitored
                            ? "Radarr / Sonarr interroge tes indexers."
                            : "Attention : ce média n'est pas surveillé, la recherche peut ne rien récupérer.",
                    });
                }
                return true;
            } catch (e) {
                setRow(key, "failed");
                if (!silent) {
                    toast.error(`Échec de la recherche : ${item.title}`, {
                        description: e instanceof Error ? e.message : "Erreur inconnue",
                    });
                }
                return false;
            }
        },
        [mutateAsync, setRow],
    );

    /** Recherche groupée séquentielle, annulable. */
    const runBulk = useCallback(
        async (items: MediaItem[]) => {
            if (runningRef.current || items.length === 0) return;
            runningRef.current = true;
            cancelRef.current = false;
            const total = items.length;
            const toastId = toast.loading(`Recherche 0/${total}…`, { description: "Préparation" });
            let ok = 0;
            let failed = 0;
            let done = 0;
            setProgress({ done, total, ok, failed, current: items[0].title });

            for (const item of items) {
                if (cancelRef.current) break;
                if (mountedRef.current) setProgress({ done, total, ok, failed, current: item.title });
                toast.loading(`Recherche ${done + 1}/${total}…`, { id: toastId, description: item.title });
                // Séquentiel volontaire : une recherche à la fois pour ménager les indexers.
                const success = await searchOne(item, true);
                done += 1;
                if (success) ok += 1;
                else failed += 1;
            }

            runningRef.current = false;
            if (mountedRef.current) setProgress(null);

            const interrupted = done < total;
            if (interrupted) {
                toast.warning(`Recherche interrompue — ${ok}/${total} lancées`, {
                    id: toastId,
                    description: failed ? `${failed} en échec` : undefined,
                });
            } else if (failed === 0) {
                toast.success(`${plural(ok, "recherche lancée", "recherches lancées")}`, {
                    id: toastId,
                    description: "Radarr et Sonarr interrogent les indexers en arrière-plan.",
                });
            } else {
                toast.warning(`${ok} lancées, ${failed} en échec`, {
                    id: toastId,
                    description: "Les lignes en échec sont marquées en rouge : tu peux les relancer une par une.",
                });
            }
            return { ok, failed, interrupted };
        },
        [searchOne],
    );

    const stop = useCallback(() => {
        cancelRef.current = true;
    }, []);

    return { rowStates, progress, running: progress !== null, searchOne, runBulk, stop };
}
