/**
 * Score de santé global de la médiathèque (héros de /health).
 * ----------------------------------------------------------------
 * Moyenne pondérée de trois sous-scores, tous sur 100, volontairement
 * simples à expliquer :
 *  - Qualité   (50 %) : part des films en 1080p ou mieux.
 *  - Doublons  (25 %) : part de la médiathèque SANS titre en double.
 *  - Rangement (25 %) : part de la médiathèque non signalée par le
 *                       nettoyage (approximation : un média peut être
 *                       signalé dans plusieurs catégories).
 * Si une analyse est indisponible, on recalcule avec les autres
 * (pondérations renormalisées) plutôt que d'afficher un faux 0.
 */
import type { QualityOverview } from "@/hooks/use-quality";
import type { DuplicatesData } from "@/hooks/use-duplicates";
import type { CleanupScan } from "@/hooks/use-cleanup";

export interface HealthPart {
    key: "quality" | "duplicates" | "cleanup";
    label: string;
    /** 0-100. */
    score: number;
    weight: number;
    detail: string;
}

export interface HealthResult {
    /** null = aucune donnée exploitable. */
    score: number | null;
    parts: HealthPart[];
}

const clamp = (n: number) => Math.max(0, Math.min(100, n));

export function computeHealth(
    quality: QualityOverview | undefined,
    duplicates: DuplicatesData | undefined,
    cleanup: CleanupScan | undefined,
): HealthResult {
    const parts: HealthPart[] = [];
    // Taille de la médiathèque (films analysés + séries avec fichiers).
    const library = quality ? quality.movies.total + quality.series.total : 0;

    if (quality && quality.movies.total > 0) {
        const res = quality.movies.resolution_distribution;
        const good = (res["2160p"]?.count ?? 0) + (res["1080p"]?.count ?? 0);
        const pct = (good / quality.movies.total) * 100;
        parts.push({
            key: "quality",
            label: "Qualité",
            score: clamp(pct),
            weight: 0.5,
            detail: `${Math.round(pct)} % des films en 1080p ou mieux`,
        });
    }

    if (duplicates && library > 0) {
        const dup = duplicates.stats.total_duplicates;
        parts.push({
            key: "duplicates",
            label: "Doublons",
            score: clamp(100 - (dup / library) * 100),
            weight: 0.25,
            detail: dup === 0 ? "Aucun titre en double" : `${dup} titre${dup > 1 ? "s" : ""} en double`,
        });
    }

    if (cleanup && library > 0) {
        const flagged =
            cleanup.unmonitored.total +
            cleanup.low_quality.total +
            cleanup.oversized.total +
            cleanup.incomplete_ended.total;
        parts.push({
            key: "cleanup",
            label: "Rangement",
            score: clamp(100 - (flagged / library) * 100),
            weight: 0.25,
            detail: flagged === 0 ? "Rien à nettoyer" : `${flagged} signalement${flagged > 1 ? "s" : ""}`,
        });
    }

    if (parts.length === 0) return { score: null, parts };
    const totalWeight = parts.reduce((s, p) => s + p.weight, 0);
    const score = parts.reduce((s, p) => s + p.score * p.weight, 0) / totalWeight;
    return { score: Math.round(score), parts };
}

/** Teinte de jauge selon le score. */
export function healthTone(score: number | null): "emerald" | "amber" | "rose" | "violet" {
    if (score === null) return "violet";
    if (score >= 80) return "emerald";
    if (score >= 60) return "amber";
    return "rose";
}

export function healthVerdict(score: number | null): string {
    if (score === null) return "Analyse indisponible";
    if (score >= 90) return "Excellente forme";
    if (score >= 80) return "Bonne santé";
    if (score >= 60) return "Quelques soins à prévoir";
    return "À soigner";
}
