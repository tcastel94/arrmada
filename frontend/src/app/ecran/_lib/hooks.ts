"use client";

// Rôle : petits outils du navigateur pour l'écran : horloge, rétroéclairage
// (Fully Kiosk), écran toujours allumé et anti-marquage (décalage des pixels).

import { useEffect, useRef, useState } from "react";
import { hasFully, setBrightness } from "@/lib/ambient";
import { SHIFT_MS } from "./api";

/* ══════════════════════════════════════════════════════════════
   Petits outils
   ══════════════════════════════════════════════════════════════ */

/** L'heure, rafraîchie chaque seconde (horloge et position de lecture). */
export function useNow(): Date {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const timer = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);
    return now;
}

/** Rétroéclairage (Fully Kiosk) : seulement quand la valeur voulue change (null : ne rien toucher). */
export function useBrightness(value: number | null) {
    const last = useRef<number | null>(null);
    useEffect(() => {
        if (value === null || last.current === value || !hasFully()) return;
        if (setBrightness(value)) last.current = value;
    }, [value]);
}

/**
 * Garder l'écran allumé hors de Fully (Chrome) : l'API « Wake Lock » ne
 * marche qu'en HTTPS ; sur le réseau local en http, elle est absente et
 * c'est Fully (« Keep Screen On ») ou Android qu'il faut régler.
 */
export function useWakeLock() {
    useEffect(() => {
        type WakeLockSentinel = { release: () => Promise<void> };
        const nav = navigator as Navigator & { wakeLock?: { request: (type: "screen") => Promise<WakeLockSentinel> } };
        if (!nav.wakeLock || !window.isSecureContext) return;
        let sentinel: WakeLockSentinel | null = null;
        const acquire = () => {
            nav.wakeLock
                ?.request("screen")
                .then((s) => (sentinel = s))
                .catch(() => undefined);
        };
        acquire();
        // Le verrou saute quand la page passe en arrière-plan : on le reprend au retour
        const onVisible = () => document.visibilityState === "visible" && acquire();
        document.addEventListener("visibilitychange", onVisible);
        return () => {
            document.removeEventListener("visibilitychange", onVisible);
            sentinel?.release().catch(() => undefined);
        };
    }, []);
}

/** Petit décalage périodique de tout l'affichage (même image affichée des heures). */
export function usePixelShift(): { x: number; y: number } {
    const [shift, setShift] = useState({ x: 0, y: 0 });
    useEffect(() => {
        const timer = setInterval(() => {
            setShift({ x: Math.round(Math.random() * 12 - 6), y: Math.round(Math.random() * 12 - 6) });
        }, SHIFT_MS);
        return () => clearInterval(timer);
    }, []);
    return shift;
}
