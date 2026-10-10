"use client";

/**
 * Audit de la configuration SABnzbd selon les recommandations TRaSH
 * (onglet « SABnzbd » de /trash-guides) et application automatique.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/** Valeur brute d'un réglage SABnzbd (booléen, nombre, texte, liste…). */
export type ConfigValue = string | number | boolean | null | undefined | ConfigValue[] | { [key: string]: ConfigValue };

export interface ConfigCheck {
    key: string;
    label: string;
    current_value: ConfigValue;
    recommended_value: ConfigValue;
    is_compliant: boolean;
    /** categories | switches | sorting | general */
    category: string;
}

export interface AuditResult {
    service_name: string;
    total_checks: number;
    passed: number;
    failed: number;
    compliance_pct: number;
    checks: ConfigCheck[];
}

export interface ApplyResult {
    success: boolean;
    categories_created: number;
    settings_updated: number;
    errors: string[];
}

export function useSabnzbdAudit() {
    return useQuery<AuditResult>({
        queryKey: ["sabnzbd-config", "audit"],
        queryFn: () => apiFetch<AuditResult>("/api/sabnzbd-config/audit"),
        // Pas d'acharnement si SABnzbd n'est pas configuré : l'erreur
        // est affichée tout de suite avec un bouton « Réessayer ».
        retry: 1,
    });
}

/**
 * Applique la config TRaSH. Une seule relecture de l'audit après succès
 * (l'ancienne page en déclenchait deux : invalidation + setTimeout).
 */
export function useSabnzbdApply() {
    const qc = useQueryClient();
    return useMutation<ApplyResult, Error, void>({
        mutationFn: () => apiFetch<ApplyResult>("/api/sabnzbd-config/apply", { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["sabnzbd-config"] });
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}
