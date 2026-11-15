// Rôle : échanges avec le serveur ArrMada pour l'écran (relevé de l'état,
// télécommande, lancement d'un titre) et réglages de temps (relevés, veille).

import { API_URL } from "@/lib/constants";
import type { Ambient, AmbientPlay, RemoteAction } from "@/lib/ambient";

/** Relevé du serveur (s). La position avance toute seule entre deux relevés. */
export const POLL_MS = 10_000;
/** Pendant une lecture : relevé plus serré (pistes, « Passer l'intro »). */
export const POLL_PLAYING_MS = 5_000;
/**
 * Relevé qui ne répond pas : abandonné au bout de 8 s (sinon il reste
 * pendu et le suivant attend derrière), puis un nouvel essai 2 s plus tard
 * avant d'afficher « Hors ligne ». Un hoquet du réseau ou du serveur (Wi-Fi
 * de la tablette, redémarrage d'ArrMada) ne fait plus clignoter le bandeau.
 */
export const AMBIENT_TIMEOUT_MS = 8_000;
export const AMBIENT_RETRY_DELAY_MS = 2_000;
/** Après une commande : le temps que la TV l'applique et renvoie son état. */
export const AFTER_COMMAND_MS = 1_200;
/** Toucher l'écran pendant un film : luminosité de repos pendant ce temps. */
export const WAKE_MS = 20_000;
/** Décalage de quelques pixels toutes les 5 min (écran allumé en permanence). */
export const SHIFT_MS = 5 * 60_000;

export type Auth = { kind: "screen"; token: string } | { kind: "admin"; token: string };

export class HttpError extends Error {
    constructor(public status: number, message: string) {
        super(message);
    }
}

function authHeaders(auth: Auth): HeadersInit {
    return auth.kind === "screen" ? { "X-Device-Token": auth.token } : { Authorization: `Bearer ${auth.token}` };
}

/** GET d'une route de l'écran (filmographie d'un acteur…) avec le jeton de la tablette. */
export async function fetchJson<T>(auth: Auth, path: string): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, { headers: authHeaders(auth), cache: "no-store" });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
    return response.json();
}

export async function fetchAmbient(auth: Auth, room: string): Promise<Ambient> {
    const query = auth.kind === "admin" ? `?room=${room}` : "";
    // AbortController plutôt qu'AbortSignal.timeout : la WebView de Fully Kiosk peut être ancienne
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), AMBIENT_TIMEOUT_MS);
    try {
        const response = await fetch(`${API_URL}/api/ambient${query}`, {
            headers: authHeaders(auth),
            cache: "no-store",
            signal: controller.signal,
        });
        if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
        return await response.json();
    } finally {
        clearTimeout(timer);
    }
}

/** Télécommande tactile : la TV de la pièce reçoit la commande en moins d'une seconde. */
export async function sendCommand(auth: Auth, room: string, command: RemoteAction): Promise<void> {
    const response = await fetch(`${API_URL}/api/ambient/command`, {
        method: "POST",
        headers: { ...authHeaders(auth), "Content-Type": "application/json" },
        body: JSON.stringify(auth.kind === "admin" ? { ...command, room } : command),
    });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
}

/** « Ce soir » : lance un titre proposé sur la TV de la pièce (le serveur vérifie qu'il est proposé). */
export async function sendPlay(auth: Auth, room: string, play: AmbientPlay): Promise<{ device: string; online: boolean }> {
    const response = await fetch(`${API_URL}/api/ambient/play`, {
        method: "POST",
        headers: { ...authHeaders(auth), "Content-Type": "application/json" },
        body: JSON.stringify(auth.kind === "admin" ? { ...play, room } : play),
    });
    if (!response.ok) {
        // Le serveur explique le refus (« Aucune TV appairée dans cette pièce »…)
        const detail = await response
            .json()
            .then((body: { detail?: unknown }) => (typeof body.detail === "string" ? body.detail : ""))
            .catch(() => "");
        throw new HttpError(response.status, detail || `HTTP ${response.status}`);
    }
    return response.json();
}
