"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

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
    };
    cors: {
        origins: string[];
    };
    scheduler: {
        health_check_interval: string;
    };
}

export function useSettings() {
    return useQuery<AppSettings>({
        queryKey: ["settings"],
        queryFn: () => apiFetch("/api/settings"),
    });
}

export function useTestTelegram() {
    return useMutation({
        mutationFn: (message?: string) =>
            apiFetch("/api/settings/telegram/test", {
                method: "POST",
                body: JSON.stringify({ message: message || "🧪 Test de notification ArrMada" }),
            }),
    });
}
