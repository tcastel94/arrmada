"use client";

/**
 * Conteneurs Docker (Unraid) liés aux services enregistrés.
 * Affichés dans l'onglet « Docker » de /system.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export const DOCKER_QUERY_KEY = ["docker-containers"] as const;

/**
 * État normalisé par le backend. `paused` et `restarting` sont distincts
 * de `stopped` depuis le correctif backend ; les anciennes réponses ne
 * connaissaient que running/stopped.
 */
export type DockerStatus = "running" | "paused" | "restarting" | "stopped";

export type DockerActionName = "start" | "stop" | "restart";

export interface DockerContainer {
    name: string;
    status: DockerStatus | string;
    image: string;
    id: string;
    /** Rarement renseigné (l'API Unraid actuelle ne renvoie pas les ports). */
    ports?: string[];
    service_name?: string;
    service_type?: string;
    /** URL de l'interface web du service associé (ex: http://nas:7878). */
    service_url?: string;
    /** Texte Docker brut, ex: "Up 3 days", "Exited (0) 2 hours ago". */
    status_text?: string;
    /** État Unraid brut (RUNNING, PAUSED, EXITED…). */
    state_raw?: string;
}

export interface DockerResponse {
    containers: DockerContainer[];
    total: number;
    running: number;
}

/**
 * @param poll rafraîchissement toutes les 15 s (true par défaut). Le
 *   héros de /system lit la liste une fois sans interroger Unraid en
 *   boucle tant que l'onglet Docker n'est pas ouvert.
 */
export function useDockerContainers({ poll = true }: { poll?: boolean } = {}) {
    return useQuery<DockerResponse>({
        queryKey: DOCKER_QUERY_KEY,
        queryFn: () => apiFetch<DockerResponse>("/api/files/docker"),
        refetchInterval: poll ? 15_000 : false,
        // Si Unraid n'est pas configuré, inutile de réessayer en boucle.
        retry: 1,
    });
}

export interface DockerActionResult {
    result: string;
    container_id: string;
    action: DockerActionName;
}

/**
 * Démarrer / arrêter / redémarrer. Depuis le correctif backend, un échec
 * renvoie une vraie erreur HTTP (avant : 200 « Failed: … » → l'UI
 * croyait que tout allait bien).
 */
export function useDockerAction() {
    const qc = useQueryClient();
    return useMutation<DockerActionResult, Error, { container_id: string; action: DockerActionName }>({
        mutationFn: (payload) =>
            apiFetch<DockerActionResult>("/api/files/docker/action", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSettled: () => {
            qc.invalidateQueries({ queryKey: DOCKER_QUERY_KEY });
        },
    });
}
