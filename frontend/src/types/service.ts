import { HealthStatusType, ServiceType } from ".";

/**
 * Types des « services » ArrMada.
 * ----------------------------------------------------------------
 * En base, la table `services` contient À LA FOIS les services *arr
 * (Sonarr, Radarr…) et des appareils du salon (Kodi, ampli Yamaha) qui
 * réutilisent la même table pour stocker URL + identifiants chiffrés.
 * Côté interface on les sépare : les appareils ont leurs propres pages
 * (/settings/kodi, /settings/yamaha) et ne doivent jamais apparaître dans
 * la liste des services *arr (avant : carte grise avec icône inconnue).
 */

/** Types d'appareils stockés dans la table services mais gérés à part. */
export const DEVICE_TYPES = ["kodi", "yamaha"] as const;
export type DeviceType = (typeof DEVICE_TYPES)[number];

/** Liste ordonnée des services *arr gérables depuis /settings/services. */
export const ARR_SERVICE_TYPES: ServiceType[] = [
    "sonarr",
    "radarr",
    "lidarr",
    "readarr",
    "prowlarr",
    "bazarr",
    "jellyfin",
    "sabnzbd",
];

/** Vrai si l'entrée est un service *arr (et pas un appareil Kodi/Yamaha). */
export function isArrService(service: { type: string }): boolean {
    return (ARR_SERVICE_TYPES as string[]).includes(service.type?.toLowerCase());
}

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

/**
 * Test d'une configuration AVANT enregistrement (POST /api/services/test).
 * En modification, `api_key` peut rester vide : le backend réutilise alors
 * la clé déjà stockée pour `service_id`.
 */
export interface TestServiceDraftPayload {
    type: ServiceType;
    url: string;
    api_key?: string;
    service_id?: number;
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
