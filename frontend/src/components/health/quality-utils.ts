/**
 * Outils « qualité » partagés par les onglets du hub Santé.
 * ----------------------------------------------------------------
 * Les noms de qualité *arr sont des chaînes ("Bluray-1080p",
 * "WEBDL-2160p", "SDTV"…). Pour les trier (2160p → SD) ou désigner la
 * meilleure copie d'un doublon, on les convertit en rang numérique.
 * Les classes Tailwind sont écrites EN ENTIER ici : Tailwind ne génère
 * que les classes qu'il voit littéralement dans le code (l'ancienne page
 * faisait `colors.bg.replace("/20","/10")` → classe jamais générée).
 */
import type { ProgressTone } from "@/components/fx/gradient-progress";

export type Resolution = "2160p" | "1080p" | "720p" | "SD" | "Other";

/** Ordre d'affichage : de la meilleure à la moins bonne. */
export const RESOLUTION_ORDER: Resolution[] = ["2160p", "1080p", "720p", "SD", "Other"];

export const RESOLUTION_META: Record<
    Resolution,
    { label: string; hint: string; tone: ProgressTone; badge: string; dot: string; text: string }
> = {
    "2160p": {
        label: "4K · 2160p",
        hint: "Ultra HD",
        tone: "violet",
        badge: "border-primary/30 bg-primary/15 text-primary",
        dot: "bg-primary",
        text: "text-primary",
    },
    "1080p": {
        label: "1080p",
        hint: "Full HD",
        tone: "primary",
        badge: "border-primary/30 bg-primary/15 text-primary",
        dot: "bg-primary",
        text: "text-primary",
    },
    "720p": {
        label: "720p",
        hint: "HD",
        tone: "amber",
        badge: "border-warning/30 bg-warning/15 text-warning",
        dot: "bg-warning",
        text: "text-warning",
    },
    SD: {
        label: "SD",
        hint: "DVD, SDTV",
        tone: "rose",
        badge: "border-rose-400/30 bg-rose-500/15 text-rose-300",
        dot: "bg-rose-400",
        text: "text-rose-300",
    },
    Other: {
        label: "Autre",
        hint: "Qualité inconnue",
        tone: "slate",
        badge: "border-white/10 bg-white/[0.06] text-muted-foreground",
        dot: "bg-slate-400",
        text: "text-muted-foreground",
    },
};

/** Le backend renvoie l'ID du profil (un nombre) comme « qualité » des séries. */
export function isProfileId(quality: string | null | undefined): boolean {
    return !!quality && /^\d+$/.test(quality.trim());
}

/** Libellé lisible d'une qualité (« Profil n°4 » pour un ID de profil série). */
export function qualityLabel(quality: string | null | undefined): string {
    if (!quality || quality === "?" || quality === "None") return "Qualité inconnue";
    if (isProfileId(quality)) return `Profil n°${quality.trim()}`;
    return quality;
}

/** Résolution déduite d'un nom de qualité *arr. */
export function resolutionOf(quality: string | null | undefined): Resolution {
    const q = (quality ?? "").toLowerCase();
    if (/2160|4k|uhd/.test(q)) return "2160p";
    if (/1080/.test(q)) return "1080p";
    if (/720/.test(q)) return "720p";
    if (/sdtv|dvd|480|576|\bsd\b/.test(q)) return "SD";
    return "Other";
}

/**
 * Rang de qualité (plus grand = meilleur) : résolution d'abord, puis la
 * source (Remux > Bluray > WEB > HDTV). Même logique que le backend.
 */
export function qualityRank(quality: string | null | undefined): number {
    const base: Record<Resolution, number> = { "2160p": 40, "1080p": 30, "720p": 20, SD: 10, Other: 0 };
    const q = (quality ?? "").toLowerCase();
    let bonus = 0;
    if (q.includes("remux")) bonus = 4;
    else if (q.includes("bluray") || q.includes("blu-ray")) bonus = 3;
    else if (q.includes("web")) bonus = 2;
    else if (q.includes("hdtv")) bonus = 1;
    return base[resolutionOf(quality)] + bonus;
}

/** Classes du badge de qualité (couleur = résolution). */
export function qualityBadgeClass(quality: string | null | undefined): string {
    return RESOLUTION_META[resolutionOf(quality)].badge;
}
