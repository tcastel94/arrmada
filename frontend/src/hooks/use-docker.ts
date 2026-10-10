"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

// ── Docker ───────────────────────────────────────────────────

export interface DockerContainer {
    name: string;
    status: string;
    image: string;
    id: string;
    ports?: string[];
    service_name?: string;
    service_type?: string;
    service_url?: string;
    status_text?: string;
    state_raw?: string;
}

export interface DockerResponse {
    containers: DockerContainer[];
    total: number;
    running: number;
}

export function useDockerContainers() {
    return useQuery<DockerResponse>({
        queryKey: ["docker-containers"],
        queryFn: () => apiFetch("/api/files/docker"),
        refetchInterval: 15_000,
    });
}

export function useDockerAction() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: { container_id: string; action: string }) =>
            apiFetch("/api/files/docker/action", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["docker-containers"] });
        },
    });
}
