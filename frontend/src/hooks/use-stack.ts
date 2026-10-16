"use client";

/**
 * Auto-configuration de la stack (backend : /api/stack/*).
 * ----------------------------------------------------------------
 * Fonctionnement en 2 temps, comme `terraform plan` puis `apply` :
 *  1. plan  : ArrMada lit les fichiers de config des applis (dossier
 *             appdata monté en lecture seule), trouve leur adresse et
 *             liste ce qui manque — rien n'est modifié ;
 *  2. apply : exécute les actions cochées, une par une, et renvoie le
 *             résultat de chacune + le plan mis à jour.
 * Les clés API et mots de passe ne quittent JAMAIS le serveur : le
 * navigateur ne reçoit que « clé trouvée : oui/non ».
 */
import { apiFetch } from "@/lib/api-client";

export type StackAppType =
    | "sonarr"
    | "radarr"
    | "lidarr"
    | "readarr"
    | "prowlarr"
    | "bazarr"
    | "jellyfin"
    | "sabnzbd"
    | "deluge"
    | "qbittorrent";

export interface StackApp {
    type: StackAppType;
    name: string;
    url: string | null;
    urls: string[];
    username: string | null;
    version: string | null;
    service_id: number | null;
    /** arrmada = déjà enregistré · appdata = lu dans un fichier de config · manual = saisi */
    source: "arrmada" | "appdata" | "manual";
    config_path: string | null;
    error: string | null;
    notes: string[];
    needs_password: boolean;
    has_api_key: boolean;
    registered: boolean;
}

export type StackActionKind = "register" | "prowlarr_app" | "download_client" | "bazarr_link";

export interface StackAction {
    id: string;
    kind: StackActionKind;
    target: string;
    subject: string;
    title: string;
    status: "todo" | "done" | "blocked";
    reason: string | null;
}

export interface StackPlan {
    appdata_dir: string;
    appdata_mounted: boolean;
    apps: StackApp[];
    actions: StackAction[];
}

export interface StackActionResult {
    id: string;
    ok: boolean;
    message: string;
}

/** Mot de passe (et adresse si l'appli n'a pas été trouvée) d'un client torrent. */
export interface DownloaderCredentials {
    url?: string;
    username?: string;
    password?: string;
}

export interface StackRequest {
    hosts?: string[];
    credentials?: Partial<Record<"deluge" | "qbittorrent", DownloaderCredentials>>;
}

/** Retire les champs vides : l'API ignore alors simplement l'entrée. */
function clean(req: StackRequest): StackRequest {
    const credentials: StackRequest["credentials"] = {};
    for (const [k, v] of Object.entries(req.credentials ?? {})) {
        const entry = Object.fromEntries(Object.entries(v ?? {}).filter(([, val]) => !!val?.trim()));
        if (Object.keys(entry).length) credentials[k as "deluge" | "qbittorrent"] = entry;
    }
    return { hosts: (req.hosts ?? []).map((h) => h.trim()).filter(Boolean), credentials };
}

export function planStack(req: StackRequest = {}): Promise<StackPlan> {
    return apiFetch<StackPlan>("/api/stack/plan", { method: "POST", body: JSON.stringify(clean(req)) });
}

export function applyStack(
    actionIds: string[],
    req: StackRequest = {},
): Promise<{ results: StackActionResult[]; plan: StackPlan }> {
    return apiFetch("/api/stack/apply", {
        method: "POST",
        body: JSON.stringify({ ...clean(req), action_ids: actionIds }),
    });
}
