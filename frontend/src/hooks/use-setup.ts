import { useQuery } from "@tanstack/react-query";
import { API_URL } from "@/lib/constants";

export interface SetupStatus {
    is_configured: boolean;
    has_services: boolean;
    services_count: number;
    database_type: string;
}

export interface DiscoveredService {
    type: string;
    name: string;
    url: string;
    port: number;
    host: string;
    version: string | null;
    needs_api_key: boolean;
    status: string;
}

export function useSetupStatus() {
    return useQuery<SetupStatus>({
        queryKey: ["setup-status"],
        queryFn: async () => {
            const res = await fetch(`${API_URL}/api/setup/status`);
            if (!res.ok) throw new Error("Failed to fetch setup status");
            return res.json();
        },
        retry: 1,
        staleTime: 30_000,
    });
}

export async function discoverServices(): Promise<DiscoveredService[]> {
    const res = await fetch(`${API_URL}/api/setup/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(null),
    });
    if (!res.ok) throw new Error("Discovery failed");
    return res.json();
}

export interface ServiceSetupItem {
    name: string;
    type: string;
    url: string;
    api_key: string;
    is_enabled: boolean;
}

export async function completeSetup(services: ServiceSetupItem[]) {
    const res = await fetch(`${API_URL}/api/setup/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ services }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Setup failed");
    }
    return res.json();
}
