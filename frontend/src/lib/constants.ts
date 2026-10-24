import { ServiceType } from "@/types";

/** API base URL */
export const API_URL = typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8420`
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420");

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
    deluge: { label: "Deluge", color: "#4a8fce", icon: "download" },
};
