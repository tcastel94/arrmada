"use client";

/**
 * Serveur : disques (via Sonarr/Radarr), ressources de l'hôte (/proc)
 * et sessions Kodi.
 * `useSystemOverview` et `DiskInfo` sont aussi consommés par le Dashboard :
 * signatures conservées (ajouts uniquement).
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

/* ── Types ─────────────────────────────────────────────────── */

export interface DiskInfo {
    path: string;
    label: string;
    total_bytes: number;
    free_bytes: number;
    used_bytes: number;
    total_human: string;
    free_human: string;
    used_human: string;
    usage_percent: number;
    source_service: string;
}

export interface KodiSession {
    instance: string;
    title: string;
    type: string;
    year?: number;
    progress_percent: number;
    is_paused: boolean;
    elapsed_seconds: number;
    total_seconds: number;
    thumbnail: string;
}

export interface MemoryInfo {
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    total_human: string;
    used_human: string;
    free_human: string;
    usage_percent: number;
}

/**
 * Compteurs CPU bruts lus dans /proc/stat (cumulés depuis le démarrage).
 * Un seul relevé ne permet PAS de calculer une charge : il faut comparer
 * deux relevés successifs (voir `cpuPercentBetween`).
 */
export interface CpuTicks {
    idle_ticks: number;
    total_ticks: number;
    cores: number;
}

export interface SystemResources {
    /** false si /proc n'est pas lisible (backend hors Linux…). */
    available: boolean;
    memory?: MemoryInfo;
    cpu?: CpuTicks;
    uptime?: { seconds: number; human: string };
    load_average?: { "1min": number; "5min": number; "15min": number };
}

export interface SystemOverview {
    disks: DiskInfo[];
    resources: SystemResources;
    kodi_sessions: KodiSession[];
    kodi_active: number;
}

/* ── Requêtes ──────────────────────────────────────────────── */

/** Vue combinée (Dashboard) : disques + ressources + sessions Kodi. */
export function useSystemOverview() {
    return useQuery<SystemOverview>({
        queryKey: ["system", "overview"],
        queryFn: () => apiFetch<SystemOverview>("/api/system/overview"),
        staleTime: 120_000,
    });
}

/**
 * Ressources de l'hôte, rafraîchies toutes les 15 s (l'ancienne page ne
 * les relisait jamais : la RAM affichée restait figée).
 */
export function useSystemResources() {
    return useQuery<SystemResources>({
        queryKey: ["system", "resources"],
        queryFn: () => apiFetch<SystemResources>("/api/system/resources"),
        refetchInterval: 15_000,
        refetchIntervalInBackground: false,
        staleTime: 10_000,
    });
}

export interface DiskSpaceResponse {
    disks: DiskInfo[];
    total_used?: number;
    total_free?: number;
    total_capacity?: number;
}

/** Espace disque (le backend le garde 2 min en cache ; relu chaque minute). */
export function useDiskSpace() {
    return useQuery<DiskSpaceResponse>({
        queryKey: ["system", "disk"],
        queryFn: () => apiFetch<DiskSpaceResponse>("/api/system/disk"),
        staleTime: 60_000,
        refetchInterval: 60_000,
    });
}

export function useKodiSessions() {
    return useQuery<{ sessions: KodiSession[]; active: number }>({
        queryKey: ["system", "kodi"],
        queryFn: () => apiFetch("/api/system/kodi/sessions"),
        refetchInterval: 15_000, // lecture en direct
    });
}

/* ── Calculs ───────────────────────────────────────────────── */

/**
 * Charge CPU (%) entre deux relevés /proc/stat : part du temps non-idle
 * écoulé entre les deux. `null` si non calculable (premier relevé,
 * compteurs identiques car réponse en cache, ou remise à zéro).
 */
export function cpuPercentBetween(prev: CpuTicks | undefined, next: CpuTicks | undefined): number | null {
    if (!prev || !next) return null;
    const dTotal = next.total_ticks - prev.total_ticks;
    const dIdle = next.idle_ticks - prev.idle_ticks;
    if (dTotal <= 0 || dIdle < 0) return null;
    return Math.max(0, Math.min(100, ((dTotal - dIdle) / dTotal) * 100));
}

/** Un disque physique, éventuellement vu sous plusieurs chemins. */
export interface DiskGroup {
    key: string;
    label: string;
    paths: string[];
    services: string[];
    total_bytes: number;
    free_bytes: number;
    used_bytes: number;
    usage_percent: number;
}

/**
 * Regroupe les disques identiques. Sonarr et Radarr voient souvent le même
 * volume sous deux chemins (/tv, /movies sur la même baie) : le backend
 * ne dédoublonne que par chemin, d'où des « disques » en double. Deux
 * entrées ayant exactement la même capacité ET le même espace libre
 * (à 0,1 % près, les relevés n'étant pas simultanés) sont le même volume.
 */
export function groupDisks(disks: DiskInfo[]): DiskGroup[] {
    const groups: DiskGroup[] = [];
    for (const d of disks) {
        if (!d.total_bytes) continue;
        const match = groups.find(
            (g) =>
                g.total_bytes === d.total_bytes &&
                Math.abs(g.free_bytes - d.free_bytes) <= d.total_bytes * 0.001,
        );
        if (match) {
            if (!match.paths.includes(d.path)) match.paths.push(d.path);
            if (!match.services.includes(d.source_service)) match.services.push(d.source_service);
            continue;
        }
        groups.push({
            key: `${d.total_bytes}:${d.path}`,
            label: d.label || d.path,
            paths: [d.path],
            services: [d.source_service],
            total_bytes: d.total_bytes,
            free_bytes: d.free_bytes,
            used_bytes: d.used_bytes,
            usage_percent: d.usage_percent,
        });
    }
    return groups.sort((a, b) => b.usage_percent - a.usage_percent);
}
