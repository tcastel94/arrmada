"use client";

/**
 * Barre d'actions de la fiche média, hiérarchisée.
 * ----------------------------------------------------------------
 * Avant : 8 à 11 boutons multicolores de même poids côte à côte.
 * Maintenant :
 *  - 1 action principale (bouton plein) :
 *      film lisible → « Lire sur <Kodi> » (bouton scindé : autres Kodi + Caster)
 *      sinon        → « Recherche auto »
 *  - 1 action secondaire (contour) : « Recherche auto » ou « Recherche manuelle »
 *  - Bande-annonce en bouton discret
 *  - un menu « ⋯ » : Éditer, Scraper NFO/Art (films seulement — le backend
 *    ne gère que Radarr), Déplacer, Supprimer (en rouge).
 */
import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
    Cast,
    ChevronDown,
    Clapperboard,
    FolderInput,
    Loader2,
    MonitorPlay,
    MoreHorizontal,
    Pencil,
    Play,
    Radar,
    Search,
    Trash2,
    Wand2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CastDialog } from "@/components/cast-button";
import { useKodiPlay, useKodiSettings } from "@/hooks/use-kodi";
import { useScrapeMedia, type MediaDetail } from "@/hooks/use-media";
import { useTriggerMediaSearch } from "@/hooks/use-media-actions";
import { cn } from "@/lib/utils";
import { seriesStats } from "./labels";

interface ActionBarProps {
    media: MediaDetail;
    onEdit: () => void;
    onMove: () => void;
    onDelete: () => void;
    /** Ouvre l'onglet « Releases » (recherche interactive). */
    onManualSearch: () => void;
}

export function ActionBar({ media, onEdit, onMove, onDelete, onManualSearch }: ActionBarProps) {
    const isMovie = media.type === "movie";
    const arr = isMovie ? "Radarr" : "Sonarr";
    const triggerSearch = useTriggerMediaSearch();
    const scrape = useScrapeMedia();
    const playable = isMovie && !!media.has_file && !!media.tmdb_id;
    const missing = !isMovie ? seriesStats(media.seasons).missing : 0;

    const autoSearch = () =>
        triggerSearch.mutate(
            { type: media.type, id: media.id },
            {
                onSuccess: () =>
                    toast.success(`Recherche automatique lancée dans ${arr}`, {
                        description: isMovie
                            ? "La meilleure release sera envoyée au client de téléchargement."
                            : "Sonarr cherche tous les épisodes surveillés manquants.",
                    }),
                onError: (e) => toast.error("Recherche impossible", { description: e.message }),
            },
        );

    const runScrape = () =>
        scrape.mutate(
            { movie_id: media.id, tmdb_id: media.tmdb_id, imdb_id: media.imdb_id },
            {
                // Tâche de fond côté backend : on annonce un lancement, pas une fin.
                onSuccess: () =>
                    toast.success("Scraping lancé", {
                        description: "Le NFO et les illustrations seront écrits à côté du fichier d'ici quelques instants.",
                    }),
                onError: (e) => toast.error("Scraping impossible", { description: e.message }),
            },
        );

    const searchButton = (primary: boolean) => (
        <Button
            size="lg"
            variant={primary ? "default" : "outline"}
            className="flex-1 sm:flex-none"
            disabled={triggerSearch.isPending}
            onClick={autoSearch}
        >
            {triggerSearch.isPending ? <Loader2 className="animate-spin" /> : <Search />}
            Recherche auto
            {missing > 0 && (
                <span
                    className={cn(
                        "rounded-md px-1.5 py-px text-[11px] font-bold tabular-nums",
                        primary ? "bg-black/20" : "bg-amber-500/15 text-amber-300",
                    )}
                    aria-label={`${missing} épisodes manquants`}
                >
                    {missing}
                </span>
            )}
        </Button>
    );

    return (
        <div className="flex flex-wrap items-center gap-2">
            {/* ── Action principale ─────────────────────────────── */}
            {playable ? <PlayAction media={media} /> : searchButton(true)}

            {/* ── Action secondaire ─────────────────────────────── */}
            {playable ? (
                searchButton(false)
            ) : (
                <Button size="lg" variant="outline" className="flex-1 sm:flex-none" onClick={onManualSearch}>
                    <Radar /> Recherche manuelle
                </Button>
            )}

            {/* ── Bande-annonce (discrète) ──────────────────────── */}
            {media.youtube_trailer_id && (
                <Button size="lg" variant="ghost" className="px-3" asChild>
                    <a
                        href={`https://www.youtube.com/watch?v=${media.youtube_trailer_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Voir la bande-annonce sur YouTube (nouvel onglet)"
                    >
                        <Clapperboard />
                        <span className="hidden sm:inline">Bande-annonce</span>
                    </a>
                </Button>
            )}

            {/* ── Menu « ⋯ » ─────────────────────────────────────── */}
            {/* modal={false} : sinon Radix peut laisser <body> non cliquable
                quand un item ouvre une boîte de dialogue. */}
            <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                    <Button size="lg" variant="outline" className="w-11 px-0" aria-label="Plus d'actions">
                        <MoreHorizontal />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-60">
                    <DropdownMenuItem onSelect={onEdit}>
                        <Pencil /> Éditer dans {arr}
                    </DropdownMenuItem>
                    {isMovie && (
                        <DropdownMenuItem disabled={scrape.isPending} onSelect={runScrape}>
                            {scrape.isPending ? <Loader2 className="animate-spin" /> : <Wand2 />}
                            Scraper NFO / illustrations
                        </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onSelect={onMove}>
                        <FolderInput /> Déplacer les fichiers…
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onSelect={onDelete}
                        className="text-red-400 focus:bg-red-500/10 focus:text-red-300"
                    >
                        <Trash2 /> Supprimer…
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    );
}

/**
 * Action principale d'un film présent sur le disque : « Lire sur <Kodi> »
 * (bouton scindé : autres instances Kodi + Caster), ou « Caster » si aucun
 * Kodi n'est configuré. Composant séparé pour ne pas interroger la config
 * Kodi sur les séries / films absents.
 */
function PlayAction({ media }: { media: MediaDetail }) {
    const qc = useQueryClient();
    const kodiPlay = useKodiPlay();
    const [castOpen, setCastOpen] = useState(false);

    // Instances Kodi configurées : le libellé reprend leur vrai nom
    // (avant : « Kodi (Salon) » codé en dur).
    const { data: kodiSettings, isSuccess: kodiKnown } = useKodiSettings();
    // Tri par id : la première instance est aussi celle que le backend choisit par défaut.
    const kodis = (kodiSettings ?? []).filter((k) => k.is_enabled).sort((a, b) => a.id - b.id);
    // Tant qu'on ne sait pas (chargement / erreur), on garde « Lire sur Kodi » :
    // le backend choisit alors la première instance active.
    const canKodi = !kodiKnown || kodis.length > 0;

    const play = (serviceId?: number, name?: string) => {
        if (!media.tmdb_id) return;
        kodiPlay.mutate(
            { tmdb_id: media.tmdb_id, service_id: serviceId },
            {
                onSuccess: (r) => {
                    if (r.status === "ok") {
                        toast.success(`Lecture lancée sur ${r.kodi ?? name ?? "Kodi"}`, {
                            description: "La télécommande s'affiche sous l'en-tête dans quelques secondes.",
                        });
                        qc.invalidateQueries({ queryKey: ["kodi", "now-playing"] });
                    } else {
                        toast.error("Lecture impossible", { description: r.detail || "Kodi n'a pas trouvé ce film dans sa bibliothèque." });
                    }
                },
                onError: (e) => toast.error("Kodi injoignable", { description: e.message }),
            },
        );
    };

    return (
        <>
            {canKodi ? (
                <div className="flex flex-1 rounded-xl sm:flex-none">
                    <Button
                        size="lg"
                        className="min-w-0 flex-1 rounded-r-none pr-4 sm:flex-none"
                        disabled={kodiPlay.isPending}
                        onClick={() => play(kodis[0]?.id, kodis[0]?.name)}
                    >
                        {kodiPlay.isPending ? <Loader2 className="animate-spin" /> : <Play className="fill-current" />}
                        <span className="truncate">Lire sur {kodis[0]?.name ?? "Kodi"}</span>
                    </Button>
                    <DropdownMenu modal={false}>
                        <DropdownMenuTrigger asChild>
                            <Button size="lg" className="rounded-l-none border-l border-black/20 px-2.5" aria-label="Autres façons de lire">
                                <ChevronDown />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-60">
                            {kodis.length > 1 && (
                                <>
                                    <DropdownMenuLabel className="eyebrow">Lire sur</DropdownMenuLabel>
                                    {kodis.map((k) => (
                                        <DropdownMenuItem key={k.id} onSelect={() => play(k.id, k.name)}>
                                            <MonitorPlay /> {k.name}
                                        </DropdownMenuItem>
                                    ))}
                                    <DropdownMenuSeparator />
                                </>
                            )}
                            <DropdownMenuItem onSelect={() => setCastOpen(true)}>
                                <Cast /> Caster sur un appareil…
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            ) : (
                <Button size="lg" className="flex-1 sm:flex-none" onClick={() => setCastOpen(true)}>
                    <Cast /> Caster
                </Button>
            )}
            {media.tmdb_id && (
                <CastDialog open={castOpen} onOpenChange={setCastOpen} tmdbId={media.tmdb_id} mediaId={String(media.id)} title={media.title} />
            )}
        </>
    );
}
