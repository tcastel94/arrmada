"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ConfigCheck {
    key: string;
    label: string;
    current_value: any;
    recommended_value: any;
    is_compliant: boolean;
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
        queryFn: () => apiFetch("/api/sabnzbd-config/audit"),
    });
}

export function useSabnzbdApply() {
    const qc = useQueryClient();
    return useMutation<ApplyResult, Error>({
        mutationFn: () =>
            apiFetch("/api/sabnzbd-config/apply", { method: "POST" }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["sabnzbd-config"] });
            qc.invalidateQueries({ queryKey: ["notifications"] });
        },
    });
}
