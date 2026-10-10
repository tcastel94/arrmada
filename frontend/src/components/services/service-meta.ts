/**
 * Métadonnées d'affichage des services *arr, partagées par la page
 * Services, le formulaire d'ajout et l'assistant d'installation.
 * ----------------------------------------------------------------
 * Avant : l'assistant (setup) avait sa propre liste SERVICE_TYPES qui
 * dupliquait SERVICE_META (libellés, ports) → risque de divergence.
 * Ici on complète SERVICE_META (lib/constants, non modifiable) avec ce
 * qui manquait : port par défaut, icône React, chemin de la clé API.
 */
import {
    BookOpen,
    Download,
    Film,
    Music,
    PlayCircle,
    Search,
    Subtitles,
    Tv,
    type LucideIcon,
} from "lucide-react";
import { SERVICE_META } from "@/lib/constants";
import type { HealthStatusType, ServiceType } from "@/types";
import { ARR_SERVICE_TYPES } from "@/types/service";

/** Icône lucide correspondant au nom stocké dans SERVICE_META.icon. */
const ICONS: Record<string, LucideIcon> = {
    tv: Tv,
    film: Film,
    music: Music,
    "book-open": BookOpen,
    search: Search,
    subtitles: Subtitles,
    "play-circle": PlayCircle,
    download: Download,
};

/** Port d'écoute par défaut de chaque application (pré-remplissage de l'URL). */
export const DEFAULT_PORTS: Record<ServiceType, number> = {
    sonarr: 8989,
    radarr: 7878,
    lidarr: 8686,
    readarr: 8787,
    prowlarr: 9696,
    bazarr: 6767,
    jellyfin: 8096,
    sabnzbd: 8080,
};

/** Où trouver la clé API dans chaque application (aide sous le champ). */
export const API_KEY_HINTS: Record<ServiceType, string> = {
    sonarr: "Sonarr → Settings → General → Security → API Key",
    radarr: "Radarr → Settings → General → Security → API Key",
    lidarr: "Lidarr → Settings → General → Security → API Key",
    readarr: "Readarr → Settings → General → Security → API Key",
    prowlarr: "Prowlarr → Settings → General → Security → API Key",
    bazarr: "Bazarr → Settings → General → Security → API Key",
    jellyfin: "Jellyfin → Tableau de bord → Clés API → +",
    sabnzbd: "SABnzbd → Config → General → Security → API Key",
};

/** Rôle de chaque application, affiché sous le nom (« Radarr » → « Films »). */
export const SERVICE_ROLES: Record<ServiceType, string> = {
    sonarr: "Séries",
    radarr: "Films",
    lidarr: "Musique",
    readarr: "Livres",
    prowlarr: "Indexeurs",
    bazarr: "Sous-titres",
    jellyfin: "Serveur multimédia",
    sabnzbd: "Téléchargements Usenet",
};

export interface ServiceVisual {
    label: string;
    color: string;
    icon: LucideIcon;
    port: number;
    role: string;
}

/** Visuel d'un type de service (repli neutre si type inconnu). */
export function serviceVisual(type: string): ServiceVisual {
    const meta = SERVICE_META[type as ServiceType];
    if (!meta) return { label: type, color: "#94a3b8", icon: Search, port: 80, role: "Service" };
    return {
        label: meta.label,
        color: meta.color,
        icon: ICONS[meta.icon] ?? Search,
        port: DEFAULT_PORTS[type as ServiceType] ?? 80,
        role: SERVICE_ROLES[type as ServiceType] ?? "Service",
    };
}

/** Types proposés dans les listes déroulantes (ordre stable). */
export const SERVICE_TYPE_OPTIONS = ARR_SERVICE_TYPES.map((value) => ({ value, ...serviceVisual(value) }));

/** Libellés FR des statuts (avant : « online / offline / unknown » en anglais). */
export const STATUS_LABELS: Record<HealthStatusType, string> = {
    online: "En ligne",
    offline: "Hors ligne",
    degraded: "Dégradé",
    unknown: "Non vérifié",
};

/** Libellé FR d'un statut, robuste aux valeurs inattendues. */
export function statusLabel(status: string | null | undefined): string {
    return STATUS_LABELS[(status ?? "unknown") as HealthStatusType] ?? "Inconnu";
}

/** URL d'exemple pour le placeholder d'un type (jamais une vraie IP perso). */
export function exampleUrl(type: string): string {
    return `http://192.168.1.10:${DEFAULT_PORTS[type as ServiceType] ?? 8080}`;
}

/**
 * Quand on change le type de service, adapte le port de l'URL déjà saisie :
 * « http://nas:8989 » (Sonarr) devient « http://nas:7878 » (Radarr).
 * On ne touche PAS à un port personnalisé (≠ port par défaut de l'ancien
 * type), ni à une URL vide (le placeholder suffit).
 */
export function swapDefaultPort(url: string, fromType: string, toType: string): string {
    const trimmed = url.trim();
    if (!trimmed) return url;
    const fromPort = DEFAULT_PORTS[fromType as ServiceType];
    const toPort = DEFAULT_PORTS[toType as ServiceType];
    if (!toPort) return url;
    try {
        const u = new URL(trimmed.includes("://") ? trimmed : `http://${trimmed}`);
        if (u.port && Number(u.port) !== fromPort) return url;
        u.port = String(toPort);
        // URL.toString ajoute un « / » final : on le retire pour rester propre.
        return u.toString().replace(/\/$/, "");
    } catch {
        return url;
    }
}
