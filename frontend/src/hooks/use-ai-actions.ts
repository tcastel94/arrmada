"use client";

/**
 * Assistant IA qui agit (ADR-018).
 * ----------------------------------------------------------------
 * On écrit une demande en clair ; l'IA propose des actions prises dans un
 * catalogue fermé (demander un film, compléter une saga, débloquer les
 * téléchargements…), le serveur vérifie la cible, puis on confirme chaque
 * action (mode « confirm ») ou elle part toute seule (mode « auto »).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type AiMode = "confirm" | "auto";

/** pending : attend un clic ; unresolved : cible introuvable ou rien à faire. */
export type ProposalStatus = "pending" | "done" | "error" | "cancelled" | "unresolved";

export interface AiProposal {
    id: string;
    type: string;
    /** « Ajouter le film Dune (2021) à Radarr et le chercher » */
    summary: string;
    status: ProposalStatus;
    /** Résultat, ou raison d'une proposition non résolue. */
    message: string;
}

export interface AiAnswer {
    reply: string;
    engine: string;
    mode: AiMode;
    proposals: AiProposal[];
}

export function useAiSettings() {
    return useQuery({
        queryKey: ["ai", "settings"],
        queryFn: () => apiFetch<{ mode: AiMode; configured: boolean }>("/api/ai/settings"),
        staleTime: 60_000,
    });
}

export function useSetAiMode() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (mode: AiMode) =>
            apiFetch<{ mode: AiMode; configured: boolean }>("/api/ai/settings", { method: "PUT", body: JSON.stringify({ mode }) }),
        onSuccess: (data) => qc.setQueryData(["ai", "settings"], data),
    });
}

/** Une demande en clair → réponse de l'IA et propositions vérifiées. */
export function useAiAct() {
    return useMutation({
        mutationFn: (message: string) => apiFetch<AiAnswer>("/api/ai/act", { method: "POST", body: JSON.stringify({ message }) }),
    });
}

/** Valider ou écarter une proposition. */
export function useAiDecide() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, accept }: { id: string; accept: boolean }) =>
            apiFetch<AiProposal>(`/api/ai/act/${id}/${accept ? "confirm" : "cancel"}`, { method: "POST" }),
        // Une action a pu changer la médiathèque, la file, les sagas…
        onSuccess: () => qc.invalidateQueries(),
    });
}
