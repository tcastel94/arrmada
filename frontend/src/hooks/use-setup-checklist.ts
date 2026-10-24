"use client";

/**
 * « Ce qu'il te reste à faire » après l'installation.
 * ----------------------------------------------------------------
 * Chaque ligne est VÉRIFIÉE par le backend auprès de l'appli concernée
 * (Prowlarr a-t-il des sources ? SABnzbd un fournisseur ? Sonarr un
 * dossier de rangement ?), comme une sonde de supervision : on ne coche
 * rien à la main, l'état affiché est l'état réel.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type ChecklistStatus = "done" | "todo" | "error";

export interface ChecklistItem {
    id: string;
    title: string;
    /** Pourquoi c'est nécessaire, en une phrase simple. */
    why: string;
    /** Quoi faire concrètement (vide quand c'est fait). */
    how: string;
    status: ChecklistStatus;
    /** État constaté (« 3 sources configurées », « Aucun serveur Usenet »…). */
    detail: string;
    service_type: string | null;
    /** Page de l'appli où agir : adresse http(s) ou chemin interne (/search). */
    link: { url: string; label: string } | null;
}

/** Mot de passe généré par l'installeur, à recopier dans l'appli. */
export interface InstallerCredential {
    app: string;
    username: string;
    password: string;
}

export interface SetupChecklist {
    items: ChecklistItem[];
    todo: number;
    done: number;
    credentials: InstallerCredential[];
}

export function useSetupChecklist(enabled = true) {
    return useQuery<SetupChecklist>({
        queryKey: ["setup-checklist"],
        queryFn: () => apiFetch("/api/setup/checklist"),
        enabled,
        // Vérifie de nouveau quand on revient sur l'onglet (après être allé
        // ajouter une source dans Prowlarr par exemple).
        refetchOnWindowFocus: true,
        staleTime: 10_000,
    });
}
