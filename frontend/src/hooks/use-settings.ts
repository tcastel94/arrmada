"use client";

/**
 * Réglages généraux d'ArrMada (lecture seule : ils viennent du fichier
 * .env du backend) + version de l'application.
 */
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_URL } from "@/lib/constants";

export interface AppSettings {
    telegram: {
        configured: boolean;
        bot_token_set: boolean;
        chat_id_set: boolean;
    };
    tmdb: {
        configured: boolean;
    };
    auth: {
        jwt_expiration_hours: number;
        /** Vrai tant qu'aucun mot de passe admin n'existe. */
        default_secret?: boolean;
        /**
         * Origine du mot de passe : "file" (haché, modifiable dans l'UI),
         * "env" (ancien ARRMADA_AUTH_SECRET du .env) ou "none".
         */
        password_source?: "file" | "env" | "none";
    };
    cors: {
        origins: string[];
    };
    scheduler: {
        health_check_interval: string;
    };
    /** Version du backend, si l'API la fournit ici. */
    version?: string;
}

export function useSettings() {
    return useQuery<AppSettings>({
        queryKey: ["settings"],
        queryFn: () => apiFetch("/api/settings"),
    });
}

/**
 * Version du backend via /api/health (route publique, sans jeton).
 * Échec silencieux : on affichera simplement la version de l'interface.
 */
export function useBackendVersion() {
    return useQuery<string | null>({
        queryKey: ["backend-version"],
        queryFn: async () => {
            const res = await fetch(`${API_URL}/api/health`);
            if (!res.ok) return null;
            const body = (await res.json().catch(() => null)) as { version?: string } | null;
            return body?.version ?? null;
        },
        staleTime: 10 * 60_000,
        retry: false,
    });
}

export function useTestTelegram() {
    return useMutation<{ success: boolean }, Error, string | undefined>({
        mutationFn: (message) =>
            apiFetch("/api/settings/telegram/test", {
                method: "POST",
                body: JSON.stringify({ message: message || "🧪 Test de notification ArrMada : tout fonctionne !" }),
            }),
    });
}
