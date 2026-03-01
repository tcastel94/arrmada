"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface DuplicateItem {
    source: string;
    quality: string;
    size_human: string;
    has_file: boolean;
}

export interface DuplicateGroup {
    title: string;
    type: string;
    year: number | null;
    copies: number;
    services: string[];
    total_size_bytes: number;
    total_size_human: string;
    items: DuplicateItem[];
    reason: string;
}

export interface UpgradeOpportunity {
    title: string;
    type: string;
    year: number | null;
    service: string;
    qualities: string[];
    reason: string;
}

export interface DuplicatesData {
    duplicates: DuplicateGroup[];
    upgrade_opportunities: UpgradeOpportunity[];
    stats: {
        total_duplicates: number;
        total_upgrades: number;
        wasted_space_bytes: number;
        wasted_space_human: string;
    };
}

export function useDuplicates() {
    return useQuery<DuplicatesData>({
        queryKey: ["duplicates"],
        queryFn: () => apiFetch("/api/duplicates"),
        staleTime: 300_000,
    });
}
