/** Service types supported by ArrMada */
export type ServiceType =
    | "sonarr"
    | "radarr"
    | "lidarr"
    | "readarr"
    | "prowlarr"
    | "bazarr"
    | "jellyfin"
    | "sabnzbd";

/** Health status of a service */
export type HealthStatusType = "online" | "offline" | "degraded" | "unknown";

/** Media types */
export type MediaType = "movie" | "series" | "music" | "book";

/** Request statuses */
export type RequestStatus =
    | "requested"
    | "searching"
    | "downloading"
    | "available"
    | "failed";

/** Duplicate statuses */
export type DuplicateStatus = "pending" | "resolved" | "ignored";
