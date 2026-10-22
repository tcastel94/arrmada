"use client";

/**
 * Onglets de la fiche média, synchronisés avec l'URL (?tab=…).
 * ----------------------------------------------------------------
 * - Série : Saisons (défaut) · Fichiers & qualité · Sous-titres · Casting · Infos · Artworks · Releases
 * - Film  : Infos (défaut) · Fichiers & qualité · Sous-titres · Casting · Artworks · Releases
 * « Recherche » est renommé « Releases », Fichier + Qualité sont fusionnés.
 * La barre d'onglets reste collée sous l'en-tête au défilement et
 * défile horizontalement sur mobile ; la pastille active glisse d'un onglet
 * à l'autre (layoutId).
 */
import { motion } from "framer-motion";
import { Captions, Disc3, HardDrive, Info, Layers, Radar, Users, type LucideIcon } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MediaDetail } from "@/hooks/use-media";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { ArtworksTab } from "./artworks-tab";
import { CastSection } from "./cast-section";
import { FilesQualityTab } from "./files-quality";
import { InfoTab } from "./info-tab";
import { seriesStats } from "./labels";
import { ReleasesTab } from "./releases";
import { SeasonsSection } from "./seasons";
import { SubtitlesTab, countMissingFr } from "./subtitles";

export type DetailTab = "seasons" | "infos" | "files" | "subtitles" | "cast" | "artworks" | "releases";

const META: Record<DetailTab, { label: string; icon: LucideIcon }> = {
    seasons: { label: "Saisons", icon: Layers },
    infos: { label: "Infos", icon: Info },
    files: { label: "Fichiers & qualité", icon: HardDrive },
    subtitles: { label: "Sous-titres", icon: Captions },
    cast: { label: "Casting", icon: Users },
    artworks: { label: "Artworks", icon: Disc3 },
    releases: { label: "Releases", icon: Radar },
};

/** Onglets disponibles pour ce média (Casting masqué s'il est vide). */
export function availableTabs(media: MediaDetail): DetailTab[] {
    const hasCast = (media.cast?.length ?? 0) > 0 || (media.crew?.length ?? 0) > 0;
    const tabs: DetailTab[] =
        media.type === "series"
            ? ["seasons", "files", "subtitles", "cast", "infos", "artworks", "releases"]
            : ["infos", "files", "subtitles", "cast", "artworks", "releases"];
    return tabs.filter((t) => t !== "cast" || hasCast);
}

export function defaultTab(type: "movie" | "series"): DetailTab {
    return type === "series" ? "seasons" : "infos";
}

export function DetailTabs({
    media,
    tab,
    onTabChange,
    onMove,
}: {
    media: MediaDetail;
    tab: string;
    onTabChange: (t: DetailTab) => void;
    onMove: () => void;
}) {
    const tabs = availableTabs(media);
    // Onglet inconnu dans l'URL (ex : ?tab=seasons sur un film) → onglet par défaut.
    const active: DetailTab = (tabs as string[]).includes(tab) ? (tab as DetailTab) : defaultTab(media.type);

    const stats = media.type === "series" ? seriesStats(media.seasons) : null;
    const missingFr = countMissingFr(media);
    const castCount = media.cast?.length ?? 0;

    const counter = (t: DetailTab) => {
        if (t === "seasons" && stats && stats.aired > 0) return `${stats.have}/${stats.aired}`;
        if (t === "cast" && castCount > 0) return String(castCount);
        return null;
    };

    return (
        <Tabs value={active} onValueChange={(v) => onTabChange(v as DetailTab)} className="space-y-4">
            {/* Barre collée sous l'en-tête (h-14 + marge) pendant le défilement */}
            <div id="media-tabs" className="sticky top-[calc(var(--navbar-h)+env(safe-area-inset-top))] z-20 -mx-1 scroll-mt-24 px-1">
                <TabsList className="w-full justify-start bg-background/70 shadow-[0_10px_30px_-12px_rgb(0_0_0/0.8)] backdrop-blur-xl sm:w-auto">
                    {tabs.map((t) => {
                        const { label, icon: Icon } = META[t];
                        const count = counter(t);
                        const isActive = active === t;
                        return (
                            <TabsTrigger
                                key={t}
                                value={t}
                                // La pastille animée remplace le fond « actif » par défaut du TabsTrigger.
                                className="relative data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                            >
                                {isActive && (
                                    <motion.span
                                        layoutId="media-tab-pill"
                                        transition={SPRING}
                                        className="absolute inset-0 rounded-lg bg-primary/15"
                                    />
                                )}
                                <span className="relative z-[1] flex items-center gap-1.5">
                                    <Icon className="h-3.5 w-3.5" aria-hidden />
                                    {label}
                                    {count && (
                                        <span
                                            className={cn(
                                                "rounded-md px-1.5 py-px text-[10px] font-semibold tabular-nums",
                                                isActive ? "bg-primary/20 text-primary" : "bg-white/[0.06] text-muted-foreground",
                                            )}
                                        >
                                            {count}
                                        </span>
                                    )}
                                    {t === "subtitles" && missingFr > 0 && (
                                        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shadow-amber-400" aria-label={`${missingFr} sans sous-titre FR`} />
                                    )}
                                </span>
                            </TabsTrigger>
                        );
                    })}
                </TabsList>
            </div>

            {media.type === "series" && (
                <TabsContent value="seasons">
                    <SeasonsSection media={media} />
                </TabsContent>
            )}
            <TabsContent value="infos">
                <InfoTab media={media} onMove={onMove} />
            </TabsContent>
            <TabsContent value="files">
                <FilesQualityTab media={media} />
            </TabsContent>
            <TabsContent value="subtitles">
                <SubtitlesTab media={media} />
            </TabsContent>
            {tabs.includes("cast") && (
                <TabsContent value="cast">
                    <CastSection cast={media.cast} crew={media.crew} />
                </TabsContent>
            )}
            <TabsContent value="artworks">
                <ArtworksTab media={media} />
            </TabsContent>
            {/* forceMount : les résultats d'une recherche (lente) survivent au changement d'onglet */}
            <TabsContent value="releases" forceMount className="data-[state=inactive]:hidden">
                <ReleasesTab media={media} />
            </TabsContent>
        </Tabs>
    );
}
