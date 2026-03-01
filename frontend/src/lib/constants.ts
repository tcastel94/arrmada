import { ServiceType } from "@/types";

/** API base URL */
export const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420";

/** Service type metadata */
export const SERVICE_META: Record<
    ServiceType,
    { label: string; color: string; icon: string }
> = {
    sonarr: { label: "Sonarr", color: "#35c5f4", icon: "tv" },
    radarr: { label: "Radarr", color: "#ffc230", icon: "film" },
    lidarr: { label: "Lidarr", color: "#00c853", icon: "music" },
    readarr: { label: "Readarr", color: "#8e24aa", icon: "book-open" },
    prowlarr: { label: "Prowlarr", color: "#e040fb", icon: "search" },
    bazarr: { label: "Bazarr", color: "#2196f3", icon: "subtitles" },
    jellyfin: { label: "Jellyfin", color: "#00a4dc", icon: "play-circle" },
    sabnzbd: { label: "SABnzbd", color: "#fec72e", icon: "download" },
};

/** Health status badges */
export const STATUS_COLORS: Record<string, string> = {
    online: "bg-green-500",
    offline: "bg-red-500",
    degraded: "bg-yellow-500",
    unknown: "bg-gray-500",
};

/** Media type labels */
export const MEDIA_TYPE_LABELS: Record<string, string> = {
    movie: "Films",
    series: "Séries",
    music: "Musique",
    book: "Livres",
};

/** Quality profiles commonly used */
export const QUALITY_PROFILES = [
    "Any",
    "SD",
    "720p",
    "1080p",
    "2160p (4K)",
    "Bluray-1080p",
    "Bluray-2160p",
];
