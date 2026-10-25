"use client";

/**
 * Équipement facultatif : TV, tablette, ampli, caméras.
 * ----------------------------------------------------------------
 * Tout le monde n'a pas une TV avec l'appli ArrMada, une tablette posée
 * près de la TV, un ampli Yamaha ou des caméras Eufy. Un module désactivé
 * masque ses menus, ses réglages et coupe ses interrogations en tâche de
 * fond (comme un service systemd qu'on « disable » : il ne démarre plus et
 * n'encombre plus la liste).
 *
 * Le backend renvoie pour chaque module :
 *  - `explicit` : le choix fait dans l'assistant ou Paramètres › Équipement ;
 *  - `detected` : ce que la configuration existante utilise déjà (une TV
 *    appairée, un ampli enregistré…) ;
 *  - `enabled`  : le choix s'il existe, sinon la détection.
 *
 * Tant que la réponse n'est pas arrivée, on affiche TOUT (`enabled` vrai) :
 * mieux vaut un menu en trop une demi-seconde qu'un menu qui « clignote »
 * à chaque chargement chez quelqu'un qui a tout l'équipement.
 */
import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type ModuleKey = "tv" | "tablet" | "amplifier" | "cameras";
export const MODULE_KEYS: ModuleKey[] = ["tv", "tablet", "amplifier", "cameras"];

export interface ModuleState {
    label: string;
    description: string;
    enabled: boolean;
    explicit: boolean | null;
    detected: boolean;
}

export type ModulesMap = Record<ModuleKey, ModuleState>;

export function useModules() {
    return useQuery<ModulesMap>({
        queryKey: ["modules"],
        queryFn: async () => (await apiFetch<{ modules: ModulesMap }>("/api/settings/modules")).modules,
        staleTime: 5 * 60_000,
    });
}

/**
 * Fonction « ce module est-il actif ? ». Accepte une clé ou une liste
 * (actif si AU MOINS un des modules l'est : la page Salon sert à la TV
 * comme à l'ampli). Sans clé : toujours vrai.
 */
export function useModuleEnabled(): (module?: ModuleKey | ModuleKey[]) => boolean {
    const { data } = useModules();
    // useCallback : la même fonction tant que les modules ne changent pas
    // (utilisable comme dépendance d'un useMemo / useEffect).
    return useCallback(
        (module?: ModuleKey | ModuleKey[]) => {
            if (!module) return true;
            if (!data) return true;
            const keys = Array.isArray(module) ? module : [module];
            return keys.some((k) => data[k]?.enabled);
        },
        [data],
    );
}

/** Enregistre un ou plusieurs choix (les autres restent inchangés). */
export function useSaveModules() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (choices: Partial<Record<ModuleKey, boolean>>) =>
            (
                await apiFetch<{ modules: ModulesMap }>("/api/settings/modules", {
                    method: "PUT",
                    body: JSON.stringify(choices),
                })
            ).modules,
        onSuccess: (modules) => qc.setQueryData(["modules"], modules),
    });
}
