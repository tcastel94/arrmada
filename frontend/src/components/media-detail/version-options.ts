/**
 * Libellés des versions (langue, doublage, qualité) : un seul endroit pour
 * la fiche, la barre d'actions et l'action groupée de la médiathèque.
 */
import { Captions, Flag, Globe, Languages, type LucideIcon } from "lucide-react";
import type { MediaVersion, VersionDub, VersionLanguage, VersionQuality } from "@/hooks/use-media-version";

export interface LanguageOption {
    value: VersionLanguage;
    label: string;
    desc: string;
    icon: LucideIcon;
}

export const LANGUAGE_OPTIONS: LanguageOption[] = [
    { value: "vf", label: "VF", desc: "Piste française obligatoire. Idéal pour les enfants.", icon: Flag },
    { value: "multi", label: "MULTi", desc: "VO et VF dans le même fichier : tu choisis à la lecture.", icon: Languages },
    { value: "vostfr", label: "VOSTFR", desc: "Version originale, sous-titres français.", icon: Captions },
    { value: "vo", label: "VO", desc: "Version originale, sans exigence de français.", icon: Globe },
];

export const DUB_OPTIONS: { value: VersionDub; label: string; short: string }[] = [
    { value: "france", label: "France (VFF)", short: "VFF" },
    { value: "quebec", label: "Québec (VFQ)", short: "VFQ" },
    { value: "any", label: "Peu importe", short: "" },
];

export const QUALITY_OPTIONS: { value: VersionQuality; label: string; desc: string }[] = [
    { value: "1080p", label: "1080p", desc: "Full HD : fichiers plus légers" },
    { value: "2160p", label: "4K", desc: "Ultra HD : meilleure image, fichiers lourds" },
];

export const qualityLabel = (q: VersionQuality) => (q === "2160p" ? "4K" : "1080p");

/** « VF (VFF) · 4K » */
export function versionLabel(v: Pick<MediaVersion, "language" | "dub"> & { quality?: VersionQuality | null }): string {
    const lang = LANGUAGE_OPTIONS.find((o) => o.value === v.language)?.label ?? v.language;
    const dub = v.language === "vf" ? DUB_OPTIONS.find((o) => o.value === v.dub)?.short : "";
    const head = dub ? `${lang} (${dub})` : lang;
    return v.quality ? `${head} · ${qualityLabel(v.quality)}` : head;
}

/** Noms de langue renvoyés par Radarr/Sonarr (anglais) → français. */
const LANGUAGE_NAMES: Record<string, string> = {
    French: "Français",
    English: "Anglais",
    Japanese: "Japonais",
    Spanish: "Espagnol",
    German: "Allemand",
    Italian: "Italien",
    Korean: "Coréen",
    Chinese: "Chinois",
    Portuguese: "Portugais",
    Russian: "Russe",
};

export const languageName = (name: string) => LANGUAGE_NAMES[name] ?? name;
