import { ServiceType } from "@/types";

/**
 * Préfixe des appels API.
 * Vide par défaut : le navigateur appelle `/api/...` sur la MÊME adresse que
 * l'interface (même hôte, même port). C'est la passerelle du conteneur
 * (docker/gateway.js) — ou les rewrites de `next dev` — qui relaie vers
 * FastAPI. Résultat : un seul port à ouvrir, pas de CORS, et ça marche
 * derrière n'importe quel reverse proxy HTTPS ou nom de domaine.
 * NEXT_PUBLIC_API_URL ne sert que si l'API est hébergée ailleurs (rare).
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

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
