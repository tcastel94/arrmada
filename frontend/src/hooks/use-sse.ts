"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/lib/api-client";
import { API_URL } from "@/lib/constants";
import { setLiveState } from "@/lib/live-status";
import { toast } from "sonner";

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
  // onEvent est stocké dans une ref : passer une fonction inline ne doit pas
  // provoquer une reconnexion SSE à chaque rendu.
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

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
      new_import: [["media"], ["dashboard"], ["search"], ["recommendations"], ["analytics"], ["calendar"], ["notifications"], ["activity"], ["downloads"]],
      media_deleted: [["media"], ["dashboard"], ["search"], ["duplicates"], ["analytics"]],
      media_renamed: [["media"]],
      download_grab: [["downloads"], ["dashboard"], ["activity"]],
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

          // Toast « live » pour les évènements marquants
          notify(eventType, data);

          // Call custom handler
          onEventRef.current?.(eventType, data);
        } catch {
          // Ignore parse errors
        }
      });
    }

    es.onopen = () => setLiveState("online");

    es.onerror = () => {
      setLiveState("offline");
      es.close();
      // Reconnect after 5 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 5000);
    };

    eventSourceRef.current = es;
  }, [enabled, queryClient]);

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

/**
 * Traduit certains évènements temps réel en notifications « toast ».
 * Uniquement les évènements utiles (import terminé, téléchargement lancé,
 * service tombé / revenu) pour ne pas noyer l'écran.
 */
function notify(type: SSEEventType, data: Record<string, unknown>) {
  const title = typeof data.title === "string" ? data.title : "";
  const service = typeof data.service === "string" ? data.service : "";
  const event = typeof data.event === "string" ? data.event : "";
  switch (type) {
    case "new_import":
      if (event === "Download") {
        toast.success(`Importé : ${title}`, {
          description: [service && `via ${service}`, typeof data.quality === "string" && data.quality].filter(Boolean).join(" · "),
        });
      } else if (title) {
        toast(`Ajouté à la bibliothèque : ${title}`);
      }
      break;
    case "download_grab":
      if (title) toast(`Téléchargement lancé : ${title}`, { description: typeof data.quality === "string" ? data.quality : undefined });
      break;
    case "service_status":
      if (data.status === "offline") {
        toast.error(`${service} est hors ligne`, { description: typeof data.error === "string" ? data.error : undefined });
      } else if (data.status === "online") {
        toast.success(`${service} est de retour en ligne`);
      }
      break;
    case "health_alert":
      toast.warning(`Alerte santé ${service}`, { description: title });
      break;
    case "webhook_test":
      toast.success("Webhook reçu — le temps réel fonctionne");
      break;
  }
}
