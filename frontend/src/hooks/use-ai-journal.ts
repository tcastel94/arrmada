"use client";

/**
 * Journal de l'agent IA (page /copilot/journal).
 * ----------------------------------------------------------------
 * Ce que l'agent a fait, quand, pourquoi (la demande d'origine), et le
 * bouton « Annuler » pour les actions qui ont un contraire sûr (ne plus
 * suivre un titre ajouté, remettre la file SABnzbd dans l'état d'avant).
 * Côté serveur : `backend/app/services/ai_journal.py`.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface AiJournalEntry {
    id: number;
    /** Secondes depuis 1970 (UTC). */
    ts: number;
    /** Outil ou action : « replace_download », « request_movie », « undo »… */
    action: string;
    status: "ok" | "ko" | "error" | "info" | string;
    /** copilot (agent), ai-web / ai-tv (assistant), web (annulation)… */
    source: string;
    /** « Ajouter le film Dune (2021) à Radarr et le chercher » */
    title: string;
    /** Résultat rendu par le service. */
    detail: string;
    /** Demande de l'utilisateur qui a provoqué l'action (vide si inconnue). */
    why: string;
    /** Libellé du bouton d'annulation ; null : ne s'annule pas (ou déjà annulée). */
    undo_label: string | null;
    undone: { at: number; message: string } | null;
}

const KEY = ["ai", "journal"] as const;

export function useAiJournal() {
    return useQuery({
        queryKey: KEY,
        queryFn: () => apiFetch<{ entries: AiJournalEntry[] }>("/api/copilot/journal?limit=100"),
        select: (data) => data.entries,
        refetchInterval: 30_000,
    });
}

export function useUndoAiAction() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id: number) => apiFetch<AiJournalEntry>(`/api/copilot/journal/${id}/undo`, { method: "POST" }),
        // La ligne change, et une ligne « Annulé : … » s'ajoute en tête
        onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    });
}
