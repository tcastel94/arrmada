"use client";

/**
 * Conteneurs Docker (Unraid) liés aux services enregistrés, leurs
 * journaux agrégés et l'analyse IA de ces journaux.
 * Affichés dans l'onglet « Docker » de /system.
 */
import { useMutation, useMutationState, useQuery, useQueryClient, type MutationState } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export const DOCKER_QUERY_KEY = ["docker-containers"] as const;

/**
 * État normalisé par le backend. `paused` et `restarting` sont distincts
 * de `stopped` depuis le correctif backend ; les anciennes réponses ne
 * connaissaient que running/stopped.
 */
export type DockerStatus = "running" | "paused" | "restarting" | "stopped";

export type DockerActionName = "start" | "stop" | "restart";

export interface DockerContainer {
    name: string;
    status: DockerStatus | string;
    image: string;
    id: string;
    /** Rarement renseigné (l'API Unraid actuelle ne renvoie pas les ports). */
    ports?: string[];
    service_name?: string;
    service_type?: string;
    /** URL de l'interface web du service associé (ex: http://nas:7878). */
    service_url?: string;
    /** Texte Docker brut, ex: "Up 3 days", "Exited (0) 2 hours ago". */
    status_text?: string;
    /** État Unraid brut (RUNNING, PAUSED, EXITED…). */
    state_raw?: string;
}

export interface DockerResponse {
    containers: DockerContainer[];
    total: number;
    running: number;
}

/**
 * @param poll rafraîchissement toutes les 15 s (true par défaut). Le
 *   héros de /system lit la liste une fois sans interroger Unraid en
 *   boucle tant que l'onglet Docker n'est pas ouvert.
 */
export function useDockerContainers({ poll = true }: { poll?: boolean } = {}) {
    return useQuery<DockerResponse>({
        queryKey: DOCKER_QUERY_KEY,
        queryFn: () => apiFetch<DockerResponse>("/api/files/docker"),
        refetchInterval: poll ? 15_000 : false,
        // Si Unraid n'est pas configuré, inutile de réessayer en boucle.
        retry: 1,
    });
}

export interface DockerActionResult {
    result: string;
    container_id: string;
    action: DockerActionName;
}

/**
 * Démarrer / arrêter / redémarrer. Depuis le correctif backend, un échec
 * renvoie une vraie erreur HTTP (avant : 200 « Failed: … » → l'UI
 * croyait que tout allait bien).
 */
export function useDockerAction() {
    const qc = useQueryClient();
    return useMutation<DockerActionResult, Error, { container_id: string; action: DockerActionName }>({
        mutationFn: (payload) =>
            apiFetch<DockerActionResult>("/api/files/docker/action", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        onSettled: () => {
            qc.invalidateQueries({ queryKey: DOCKER_QUERY_KEY });
        },
    });
}

/* ── Journaux agrégés + analyse IA ──────────────────────────────
 * Le backend lit les logs directement sur /var/run/docker.sock (l'API
 * Unraid ne les expose pas), ne garde que les conteneurs des services
 * enregistrés, classe chaque ligne par niveau et renvoie les plus
 * récentes en premier (200 max, toutes sources confondues).
 */

export type DockerLogLevel = "error" | "warning" | "info" | "other";

export interface DockerLogEntry {
    /** Horodatage Docker RFC 3339 en UTC, précision nanoseconde. */
    ts: string;
    /** « HH:MM:SS » extrait tel quel de `ts` → heure UTC, pas locale. */
    time: string;
    container: string;
    /** Nom du service ArrMada associé (à défaut : nom du conteneur). */
    service: string;
    level: DockerLogLevel;
    message: string;
}

export interface DockerLogsResponse {
    logs: DockerLogEntry[];
    count: number;
}

export const DOCKER_LOGS_QUERY_KEY = ["docker-logs"] as const;

/**
 * Flux de logs rafraîchi toutes les 10 s.
 * @param tail  lignes lues PAR conteneur (10-300 côté backend).
 * @param live  false = pause : plus de rafraîchissement automatique, ni au
 *              retour sur l'onglet du navigateur (sinon la « pause »
 *              ferait quand même défiler les lignes).
 */
export function useDockerLogs({ tail = 60, live = true }: { tail?: number; live?: boolean } = {}) {
    return useQuery<DockerLogsResponse>({
        queryKey: [...DOCKER_LOGS_QUERY_KEY, tail],
        queryFn: () => apiFetch<DockerLogsResponse>(`/api/files/docker/logs?tail=${tail}`),
        refetchInterval: live ? 10_000 : false,
        refetchOnWindowFocus: live,
        // Si le socket Docker n'est pas monté, inutile d'insister.
        retry: 1,
    });
}

export type LogSeverity = "error" | "warning" | "info";

export interface LogProblem {
    title: string;
    severity: LogSeverity;
    services: string[];
    cause: string;
    solution: string;
    occurrences?: number;
}

export interface LogAnalysis {
    summary?: string;
    problems?: LogProblem[];
    /** Moteur réellement utilisé : « ollama » (local) ou « openrouter ». */
    engine?: string;
    /** Nombre de lignes erreur/avertissement envoyées à l'IA. */
    analyzed_lines?: number;
    /** Répartition des lignes analysées par niveau. */
    level_counts?: Partial<Record<DockerLogLevel, number>>;
    /** Présent quand l'analyse a échoué (IA injoignable, réponse illisible…). */
    error?: string;
    ai_available?: boolean;
}

const asText = (v: unknown): string => (typeof v === "string" ? v.trim() : typeof v === "number" ? String(v) : "");

/**
 * La réponse vient d'un LLM : même avec un format JSON imposé, un petit
 * modèle local peut renvoyer une sévérité inventée, un service en texte
 * au lieu d'une liste, un nombre en chaîne… On normalise ici pour que
 * l'affichage n'ait jamais à se méfier des données.
 */
function normalizeAnalysis(raw: unknown): LogAnalysis {
    const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
    const problems = Array.isArray(r.problems)
        ? r.problems
              .filter((p): p is Record<string, unknown> => !!p && typeof p === "object")
              .map((p): LogProblem => {
                  const sev = asText(p.severity).toLowerCase();
                  const services = Array.isArray(p.services) ? p.services.map(asText) : [asText(p.services)];
                  const occ = Number(p.occurrences);
                  return {
                      title: asText(p.title) || "Problème sans titre",
                      severity: sev.startsWith("err") || sev === "critical" ? "error" : sev.startsWith("warn") ? "warning" : "info",
                      services: Array.from(new Set(services.filter(Boolean))),
                      cause: asText(p.cause),
                      solution: asText(p.solution),
                      occurrences: Number.isFinite(occ) && occ > 0 ? Math.round(occ) : undefined,
                  };
              })
        : undefined;
    return {
        summary: asText(r.summary) || undefined,
        problems,
        engine: asText(r.engine) || undefined,
        analyzed_lines: typeof r.analyzed_lines === "number" ? r.analyzed_lines : undefined,
        level_counts: r.level_counts && typeof r.level_counts === "object" ? (r.level_counts as LogAnalysis["level_counts"]) : undefined,
        error: asText(r.error) || undefined,
        ai_available: typeof r.ai_available === "boolean" ? r.ai_available : undefined,
    };
}

export const ANALYZE_LOGS_MUTATION_KEY = ["docker-logs-analyze"] as const;

/**
 * Requête d'analyse en cours, gardée hors du composant : l'analyse dure
 * ~30 s et doit pouvoir être annulée même si l'utilisateur a changé
 * d'onglet puis est revenu (le composant a été recréé entre-temps).
 */
let analyzeController: AbortController | null = null;

/** Annule l'analyse en cours côté navigateur (le backend finit seul, sans conséquence). */
export function cancelLogAnalysis() {
    analyzeController?.abort();
}

/** Vrai si l'erreur provient d'une annulation volontaire. */
export function isAbortError(error: unknown): boolean {
    return error instanceof DOMException ? error.name === "AbortError" : error instanceof Error && error.name === "AbortError";
}

/**
 * Lance l'analyse IA (Ollama local, OpenRouter en secours).
 * `gcTime` long + `mutationKey` : le résultat reste consultable via
 * `useLastLogAnalysis` pendant 30 min, même après un changement d'onglet.
 */
export function useAnalyzeLogs() {
    return useMutation<LogAnalysis, Error, number | void>({
        mutationKey: ANALYZE_LOGS_MUTATION_KEY,
        gcTime: 30 * 60_000,
        mutationFn: async (tail) => {
            analyzeController?.abort();
            const controller = new AbortController();
            analyzeController = controller;
            try {
                const raw = await apiFetch<unknown>(`/api/files/docker/logs/analyze?tail=${tail ?? 150}`, {
                    method: "POST",
                    signal: controller.signal,
                });
                return normalizeAnalysis(raw);
            } finally {
                if (analyzeController === controller) analyzeController = null;
            }
        },
    });
}

/** Dernière analyse lancée (en cours, réussie ou en échec), ou undefined. */
export function useLastLogAnalysis() {
    const states = useMutationState<MutationState<LogAnalysis, Error, number | void>>({
        filters: { mutationKey: ANALYZE_LOGS_MUTATION_KEY },
        select: (m) => m.state as MutationState<LogAnalysis, Error, number | void>,
    });
    return states.length > 0 ? states[states.length - 1] : undefined;
}
