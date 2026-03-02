"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface NotificationItem {
    id: number;
    type: string;
    severity: string;
    title: string;
    message: string;
    is_read: boolean;
    service_name: string | null;
    created_at: string;
}

interface NotificationListResponse {
    items: NotificationItem[];
    unread_count: number;
}

export function useNotifications(limit = 50, unreadOnly = false) {
    return useQuery<NotificationListResponse>({
        queryKey: ["notifications", { limit, unreadOnly }],
        queryFn: () =>
            apiFetch(
                `/api/notifications?limit=${limit}&unread_only=${unreadOnly}`
            ),
        refetchInterval: 30_000, // Poll every 30s
    });
}

export function useUnreadCount() {
    return useQuery<{ unread_count: number }>({
        queryKey: ["notifications", "count"],
        queryFn: () => apiFetch("/api/notifications/count"),
        refetchInterval: 15_000, // Poll every 15s
    });
}

export function useMarkRead() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id: number) =>
            apiFetch(`/api/notifications/${id}/read`, { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}

export function useMarkAllRead() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: () =>
            apiFetch("/api/notifications/read-all", { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}
