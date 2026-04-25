"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/lib/api-client";
import { API_URL } from "@/lib/constants";

/**
 * SSE event types from the backend.
 */
export type SSEEventType =
  | "connected"
  | "service_status"
  | "download_grab"
  | "download_update"
  | "new_import"
  | "media_renamed"
  | "media_deleted"
  | "health_alert"
  | "health_restored"
  | "subtitle_update"
  | "cache_invalidated"
  | "notification"
  | "webhook_test";

type SSEEventHandler = (data: Record<string, unknown>) => void;

/**
 * Hook to connect to the SSE event stream and auto-invalidate React Query caches.
 *
 * Usage:
 *   useSSE(); // In your app layout — handles everything automatically
 *
 *   useSSE({
 *     onEvent: (type, data) => { console.log(type, data); },
 *   });
 */
export function useSSE(options?: {
  onEvent?: (type: SSEEventType, data: Record<string, unknown>) => void;
  enabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const { onEvent, enabled = true } = options ?? {};

  const connect = useCallback(() => {
    const token = getToken();
    if (!token || !enabled) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_URL}/api/events/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);

    // Define which query keys to invalidate per event type
    const invalidationMap: Record<string, string[][]> = {
      new_import: [["media"], ["dashboard"], ["search"], ["recommendations"], ["analytics"], ["calendar"]],
      media_deleted: [["media"], ["dashboard"], ["search"], ["duplicates"], ["analytics"]],
      media_renamed: [["media"]],
      download_grab: [["downloads"], ["dashboard"]],
      download_update: [["downloads"]],
      service_status: [["services"], ["dashboard"]],
      health_alert: [["services"], ["notifications"]],
      health_restored: [["services"], ["notifications"]],
      subtitle_update: [["media"]],
      cache_invalidated: [["media"], ["dashboard"], ["search"]],
      notification: [["notifications"]],
    };

    // Listen for all event types
    const eventTypes: SSEEventType[] = [
      "connected", "service_status", "download_grab", "download_update",
      "new_import", "media_renamed", "media_deleted", "health_alert",
      "health_restored", "subtitle_update", "cache_invalidated",
      "notification", "webhook_test",
    ];

    for (const eventType of eventTypes) {
      es.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);

          // Auto-invalidate relevant queries
          const keysToInvalidate = invalidationMap[eventType];
          if (keysToInvalidate) {
            for (const key of keysToInvalidate) {
              queryClient.invalidateQueries({ queryKey: key });
            }
          }

          // Call custom handler
          onEvent?.(eventType, data);
        } catch {
          // Ignore parse errors
        }
      });
    }

    es.onerror = () => {
      es.close();
      // Reconnect after 5 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 5000);
    };

    eventSourceRef.current = es;
  }, [enabled, onEvent, queryClient]);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);
}
