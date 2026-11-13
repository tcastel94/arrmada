"use client";

/**
 * Copilote : conversation avec l'IA qui lit la stack (ADR-017).
 * ----------------------------------------------------------------
 * `POST /api/copilot/chat` répond en flux SSE (texte au fil de l'eau +
 * outils consultés). EventSource ne sait pas faire de POST : le flux est lu
 * avec fetch + ReadableStream.
 *
 * La conversation vit dans un petit magasin HORS de React : elle survit à un
 * changement de page (on peut aller vérifier un réglage et revenir), et une
 * réponse en cours continue d'arriver pendant ce temps. Côté serveur,
 * l'historique complet est gardé en mémoire ; le navigateur n'envoie que le
 * nouveau message et l'identifiant de la conversation.
 */
import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, clearToken, getToken } from "@/lib/api-client";
import { API_URL } from "@/lib/constants";

export interface CopilotStatus {
    configured: boolean;
    model: string;
    effort: string;
    web_search: boolean;
    documents: number;
}

/** Un outil consulté par le modèle (lecture de la stack, recherche web…). */
export interface CopilotTool {
    id: string;
    name: string;
    label: string;
    /** Arguments résumés (« radarr · naming »). */
    detail: string;
    state: "running" | "ok" | "error";
    durationMs?: number;
}

/** Une réponse est une suite de morceaux, dans l'ordre : texte, outils, texte… */
export type CopilotPart = { kind: "text"; text: string } | { kind: "tools"; tools: CopilotTool[] };

export interface CopilotUsage {
    /** Coût estimé du tour en dollars (null : modèle au tarif inconnu). */
    costUsd: number | null;
    inputTokens: number;
    outputTokens: number;
    cacheReadTokens: number;
    webSearches: number;
    modelCalls: number;
    model: string;
}

export interface CopilotMessage {
    id: string;
    role: "user" | "assistant";
    parts: CopilotPart[];
    /** Résumé de la réflexion en cours (affiché tant que la réponse arrive). */
    thinking: string;
    state: "streaming" | "done" | "error" | "stopped";
    error?: string;
    notices: string[];
    usage?: CopilotUsage;
}

interface CopilotState {
    conversationId: string | null;
    messages: CopilotMessage[];
    busy: boolean;
}

/* ── Magasin ─────────────────────────────────────────────────── */

const EMPTY: CopilotState = { conversationId: null, messages: [], busy: false };

let state: CopilotState = EMPTY;
const listeners = new Set<() => void>();
let controller: AbortController | null = null;
/** Réponse en cours d'écriture : modifiée sur place, recopiée dans `state` une fois par image. */
let draft: CopilotMessage | null = null;
let frame = 0;
let sequence = 0;

function publish(next: CopilotState) {
    state = next;
    listeners.forEach((listener) => listener());
}

function cloneMessage(message: CopilotMessage): CopilotMessage {
    return {
        ...message,
        notices: [...message.notices],
        parts: message.parts.map((part) =>
            part.kind === "text" ? { ...part } : { kind: "tools", tools: part.tools.map((tool) => ({ ...tool })) },
        ),
    };
}

/** Recopie le brouillon dans l'état publié (dernier message de la liste). */
function flush() {
    frame = 0;
    if (!draft) return;
    publish({ ...state, messages: [...state.messages.slice(0, -1), cloneMessage(draft)] });
}

/**
 * Le texte arrive mot par mot : sans regroupement, chaque mot relancerait le
 * rendu Markdown de toute la réponse. Une mise à jour par image suffit.
 */
function touch() {
    if (frame || typeof window === "undefined") return;
    frame = window.requestAnimationFrame(flush);
}

function nextId(prefix: string): string {
    // Pas crypto.randomUUID : absent en HTTP simple (accès par l'IP du NAS).
    sequence += 1;
    return `${prefix}-${Date.now().toString(36)}-${sequence}`;
}

/* ── Événements du flux ──────────────────────────────────────── */

/** « {service: "radarr", section: "naming"} » → « radarr · naming ». */
function describeInput(input: unknown): string {
    if (!input || typeof input !== "object") return "";
    const values = Object.values(input as Record<string, unknown>)
        .filter((value) => (typeof value === "string" && value !== "") || typeof value === "number")
        .map(String);
    const text = values.join(" · ");
    return text.length > 90 ? `${text.slice(0, 90)}…` : text;
}

function findTool(message: CopilotMessage, id: string): CopilotTool | undefined {
    for (const part of message.parts) {
        if (part.kind !== "tools") continue;
        const tool = part.tools.find((candidate) => candidate.id === id);
        if (tool) return tool;
    }
    return undefined;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- charge utile JSON du serveur, forme vérifiée champ par champ
type Payload = Record<string, any>;

function applyEvent(message: CopilotMessage, event: string, data: Payload) {
    const last = message.parts[message.parts.length - 1];
    switch (event) {
        case "conversation":
            state = { ...state, conversationId: String(data.id) };
            if (data.restarted) {
                message.notices.push(
                    "Le serveur a redémarré depuis ta dernière question : le copilote repart d'une conversation neuve, sans le contexte précédent.",
                );
            }
            break;
        case "text":
            if (last?.kind === "text") last.text += String(data.delta ?? "");
            else message.parts.push({ kind: "text", text: String(data.delta ?? "").replace(/^\n+/, "") });
            message.thinking = "";
            break;
        case "thinking":
            message.thinking = data.start ? "" : message.thinking + String(data.delta ?? "");
            break;
        case "tool_start": {
            const tool: CopilotTool = {
                id: String(data.id),
                name: String(data.name),
                label: String(data.label || data.name),
                detail: describeInput(data.input),
                state: "running",
            };
            if (last?.kind === "tools") last.tools.push(tool);
            else message.parts.push({ kind: "tools", tools: [tool] });
            break;
        }
        case "tool_end": {
            const tool = findTool(message, String(data.id));
            if (tool) {
                tool.state = data.ok ? "ok" : "error";
                if (typeof data.duration_ms === "number") tool.durationMs = data.duration_ms;
            }
            break;
        }
        case "notice":
            message.notices.push(String(data.message));
            break;
        case "error":
            message.error = String(data.message);
            message.state = "error";
            break;
        case "usage":
            message.usage = {
                costUsd: typeof data.turn?.cost_usd === "number" ? data.turn.cost_usd : null,
                inputTokens: Number(data.turn?.input_tokens ?? 0),
                outputTokens: Number(data.turn?.output_tokens ?? 0),
                cacheReadTokens: Number(data.turn?.cache_read_tokens ?? 0),
                webSearches: Number(data.turn?.web_searches ?? 0),
                modelCalls: Number(data.model_calls ?? 0),
                model: String(data.model ?? ""),
            };
            break;
        case "done":
            if (message.state === "streaming") {
                message.state = data.ok ? "done" : "error";
                if (!data.ok && !message.error) message.error = "Le copilote n'a pas pu terminer sa réponse.";
            }
            break;
    }
}

/** Fin de flux, quelle qu'en soit la cause : plus aucun outil ne « tourne ». */
function settle(message: CopilotMessage) {
    message.thinking = "";
    for (const part of message.parts) {
        if (part.kind !== "tools") continue;
        for (const tool of part.tools) if (tool.state === "running") tool.state = "error";
    }
}

/** Lit un flux SSE : blocs séparés par une ligne vide, lignes `event:` et `data:`. */
async function readStream(body: ReadableStream<Uint8Array>, onEvent: (event: string, data: Payload) => void) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
            const block = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            boundary = buffer.indexOf("\n\n");
            let event = "";
            let data = "";
            for (const line of block.split("\n")) {
                if (line.startsWith("event: ")) event = line.slice(7).trim();
                else if (line.startsWith("data: ")) data += line.slice(6);
                // Les lignes « : ping » (battement) sont ignorées
            }
            if (!event || !data) continue;
            try {
                onEvent(event, JSON.parse(data) as Payload);
            } catch {
                // Bloc illisible : on l'ignore plutôt que de couper la réponse
            }
        }
    }
}

/* ── Actions ─────────────────────────────────────────────────── */

async function failureMessage(response: Response): Promise<string> {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : "";
    return detail || `Le serveur a répondu HTTP ${response.status}.`;
}

export async function sendCopilotMessage(text: string): Promise<void> {
    const question = text.trim();
    if (!question || state.busy) return;

    const user: CopilotMessage = {
        id: nextId("u"),
        role: "user",
        parts: [{ kind: "text", text: question }],
        thinking: "",
        state: "done",
        notices: [],
    };
    const answer: CopilotMessage = { id: nextId("a"), role: "assistant", parts: [], thinking: "", state: "streaming", notices: [] };
    draft = answer;
    // Référence locale : une nouvelle conversation lancée pendant que celle-ci
    // se termine ne doit pas se faire écraser son propre contrôleur.
    const abort = new AbortController();
    controller = abort;
    publish({ ...state, busy: true, messages: [...state.messages, user, cloneMessage(answer)] });

    try {
        const token = getToken();
        const response = await fetch(`${API_URL}/api/copilot/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
            body: JSON.stringify({ message: question, conversation_id: state.conversationId }),
            signal: abort.signal,
        });
        if (response.status === 401) {
            clearToken();
            window.location.href = "/login";
            return;
        }
        if (!response.ok || !response.body) {
            answer.state = "error";
            answer.error = await failureMessage(response);
        } else {
            await readStream(response.body, (event, data) => {
                applyEvent(answer, event, data);
                touch();
            });
            if (answer.state === "streaming") {
                // Flux fermé sans événement de fin : connexion coupée en route
                answer.state = "error";
                answer.error = "Connexion interrompue avant la fin de la réponse.";
            }
        }
    } catch (error) {
        if (abort.signal.aborted) {
            answer.state = "stopped";
        } else {
            answer.state = "error";
            answer.error = error instanceof Error && error.message ? `Serveur injoignable : ${error.message}` : "Serveur injoignable.";
        }
    } finally {
        settle(answer);
        if (controller === abort) controller = null;
        // Le brouillon est publié une dernière fois ; s'il a été retiré entre-temps
        // (nouvelle conversation pendant la réponse), il n'y a plus rien à publier.
        if (draft === answer) {
            if (frame) window.cancelAnimationFrame(frame);
            frame = 0;
            draft = null;
            publish({ ...state, busy: false, messages: [...state.messages.slice(0, -1), cloneMessage(answer)] });
        }
    }
}

/** Interrompt la réponse en cours (le serveur coupe l'appel au modèle et oublie ce tour). */
export function stopCopilot() {
    controller?.abort();
}

/** Repart d'une conversation vide ; le serveur oublie l'ancienne. */
export function resetCopilot() {
    const previous = state.conversationId;
    draft = null;
    controller?.abort();
    publish(EMPTY);
    if (previous) {
        void apiFetch(`/api/copilot/conversations/${previous}`, { method: "DELETE" }).catch(() => undefined);
    }
}

/* ── Hooks ───────────────────────────────────────────────────── */

function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

/** Conversation en cours (partagée par toute l'application, conservée d'une page à l'autre). */
export function useCopilot(): CopilotState {
    return useSyncExternalStore(
        subscribe,
        () => state,
        () => EMPTY,
    );
}

/** Le copilote est-il configuré côté serveur (clé d'API présente) ? */
export function useCopilotStatus() {
    return useQuery<CopilotStatus>({
        queryKey: ["copilot", "status"],
        queryFn: () => apiFetch<CopilotStatus>("/api/copilot/status"),
        staleTime: 60_000,
    });
}
