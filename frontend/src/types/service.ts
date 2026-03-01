import { HealthStatusType, ServiceType } from ".";

/** A connected *arr service */
export interface ArrService {
    id: number;
    name: string;
    type: ServiceType;
    url: string;
    is_enabled: boolean;
    last_health_check: string | null;
    last_status: HealthStatusType;
    last_latency_ms: number | null;
    version: string | null;
    created_at: string;
    updated_at: string;
}

/** Health event for a service */
export interface HealthEvent {
    id: number;
    service_id: number;
    status: HealthStatusType;
    latency_ms: number | null;
    error_message: string | null;
    checked_at: string;
}

/** Service health check result */
export interface ServiceHealthResult {
    service_id: number;
    service_name: string;
    service_type: ServiceType;
    status: HealthStatusType;
    latency_ms: number | null;
    error: string | null;
    version: string | null;
}

/** Test connection result */
export interface TestConnectionResult {
    success: boolean;
    status: HealthStatusType;
    latency_ms: number | null;
    version: string | null;
    error: string | null;
}

/** Create service payload */
export interface CreateServicePayload {
    name: string;
    type: ServiceType;
    url: string;
    api_key: string;
    is_enabled?: boolean;
}

/** Update service payload */
export interface UpdateServicePayload {
    name?: string;
    url?: string;
    api_key?: string;
    is_enabled?: boolean;
}
