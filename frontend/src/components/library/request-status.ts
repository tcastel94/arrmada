/**
 * Statuts des demandes d'ajout — SOURCE UNIQUE (avant : deux tables de
 * statuts différentes entre /requests et /search, avec des couleurs et
 * libellés qui ne correspondaient pas).
 */
import type { RequestStatus } from "@/hooks/use-requests";
import type { StatusTone } from "@/components/fx/status-dot";

export interface RequestStatusMeta {
    label: string;
    /** Couleur de la pastille StatusDot. */
    tone: StatusTone;
    /** Onde animée pour les états « vivants ». */
    pulse: boolean;
    /** Classes du badge (fond + texte + liseré). */
    badge: string;
}

export const REQUEST_STATUS: Record<RequestStatus, RequestStatusMeta> = {
    requested: {
        label: "En attente",
        tone: "unknown",
        pulse: false,
        badge: "bg-slate-500/10 text-slate-300 ring-slate-400/25",
    },
    searching: {
        label: "Recherche",
        tone: "warning",
        pulse: true,
        badge: "bg-warning/10 text-warning ring-warning/25",
    },
    downloading: {
        label: "Téléchargement",
        tone: "primary",
        pulse: true,
        badge: "bg-primary/10 text-primary ring-primary/25",
    },
    available: {
        label: "Disponible",
        tone: "success",
        pulse: false,
        badge: "bg-success/10 text-success ring-success/25",
    },
    failed: {
        label: "Échec",
        tone: "error",
        pulse: false,
        badge: "bg-destructive/10 text-destructive ring-destructive/25",
    },
};

/** Ordre d'affichage des filtres. */
export const REQUEST_STATUS_ORDER: RequestStatus[] = ["requested", "searching", "downloading", "available", "failed"];

/** Métadonnées d'un statut (repli « En attente » pour une valeur inconnue). */
export function requestStatusMeta(status: string): RequestStatusMeta {
    return REQUEST_STATUS[status as RequestStatus] ?? REQUEST_STATUS.requested;
}

/** Une demande est « active » tant qu'elle n'est ni disponible ni en échec. */
export const isActiveRequest = (status: string) => status !== "available" && status !== "failed";
