/**
 * Mini « store » global de l'état de la connexion temps réel (SSE).
 * ----------------------------------------------------------------
 * Analogie infra : c'est un fichier d'état partagé que plusieurs
 * processus lisent. Le hook useSSE écrit dedans (connecté / reconnexion),
 * le header et la sidebar le lisent pour afficher le voyant « Live ».
 * useSyncExternalStore = l'API React officielle pour lire ce genre
 * d'état externe sans incohérence d'affichage.
 */
import { useSyncExternalStore } from "react";

export type LiveState = "connecting" | "online" | "offline";

let state: LiveState = "connecting";
const listeners = new Set<() => void>();

export function setLiveState(next: LiveState) {
    if (next === state) return;
    state = next;
    listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
    listeners.add(cb);
    return () => listeners.delete(cb);
}

export function useLiveState(): LiveState {
    return useSyncExternalStore(subscribe, () => state, () => "connecting");
}
