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
            {/* Barre d'onglets texte soulignée, collée sous la barre du haut au
                défilement (fond flouté, pleine largeur), défilante sur mobile. */}
            <div
                id="media-tabs"
                className="sticky top-[calc(var(--navbar-h)+env(safe-area-inset-top))] z-20 -mx-4 scroll-mt-24 bg-black/80 px-4 backdrop-blur-xl hairline-b md:-mx-6 md:px-6 lg:-mx-8 lg:px-8"
            >
                <TabsList className="h-11 w-full justify-start gap-6 rounded-none bg-transparent p-0">
                    {tabs.map((t) => {
                        const { label } = META[t];
                        const count = counter(t);
                        const isActive = active === t;
                        return (
                            <TabsTrigger
                                key={t}
                                value={t}
                                className="relative h-full rounded-none px-0 text-[15px] font-medium text-muted-foreground hover:text-foreground data-[state=active]:bg-transparent data-[state=active]:font-semibold data-[state=active]:text-foreground data-[state=active]:shadow-none"
                            >
                                <span className="flex items-center gap-1.5">
                                    {label}
                                    {count && <span className="text-[13px] font-normal tabular-nums text-muted-foreground">{count}</span>}
                                    {t === "subtitles" && missingFr > 0 && (
                                        <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-label={`${missingFr} sans sous-titre FR`} />
                                    )}
                                </span>
                                {/* Soulignement qui glisse d'un onglet à l'autre */}
                                {isActive && (
                                    <motion.span layoutId="media-tab-underline" transition={SPRING} className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-foreground" />
                                )}
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
