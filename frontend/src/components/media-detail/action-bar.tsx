"use client";

/**
 * Barre d'actions de la fiche média, hiérarchisée.
 * ----------------------------------------------------------------
 * Avant : 8 à 11 boutons multicolores de même poids côte à côte.
 * Maintenant :
 *  - 1 action principale (bouton plein) :
 *      film lisible → « Lire · <pièce> » (bouton scindé : choix de la pièce
 *                     Salon / Salle de cinéma, autres Kodi, Caster). Le
 *                     backend lance Kodi ET règle l'ampli Yamaha pour la pièce.
 *      sinon        → « Recherche auto »
 *  - « Sur la TV » (contour, appli Kodi 1.19) : lance le film, ou l'épisode à
 *    suivre d'une série, sur une TV appairée ; masqué sans TV appairée
 *  - 1 action secondaire (contour) : « Recherche auto » ou « Recherche manuelle »
 *  - Bande-annonce en bouton discret (lecteur YouTube dans une modale)
 *  - un menu « ⋯ » : Éditer, Scraper NFO/Art (films seulement — le backend
 *    ne gère que Radarr), Déplacer, Supprimer (en rouge).
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import {
    Cast,
    Check,
    ChevronDown,
    FolderInput,
    Loader2,
    MonitorPlay,
    MoreHorizontal,
    Pencil,
    Play,
    Radar,
    Search,
    SlidersHorizontal,
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
import { TrailerModal } from "@/components/media/trailer-modal";
import { PlayOnTvButton, seriesTarget } from "@/components/media/play-on-tv";
import { episodeCode, useWatchSummary } from "@/hooks/use-watch";
import { useKodiPlay, useKodiSettings, type KodiInstance, type KodiRoom } from "@/hooks/use-kodi";
import { useYamahaProfiles, type RoomProfile } from "@/hooks/use-yamaha";
import { ROOM_META, describeApplied, soundProgramShortLabel, volumePct } from "@/components/remote/yamaha-audio";
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
    // Vu / reprise partagés par les TV : reprise du film, épisode à suivre
    const { data: watch } = useWatchSummary();
    const movieState = isMovie && media.tmdb_id ? watch?.movies[String(media.tmdb_id)] : undefined;
    const episode = !isMovie ? seriesTarget(media, media.tvdb_id ? watch?.series[String(media.tvdb_id)] : null) : null;

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

            {/* ── Sur une TV appairée (appli ArrMada) ───────────── */}
            {playable && (
                <PlayOnTvButton
                    target={{ media_type: "movie", id: media.tmdb_id as number, title: media.title }}
                    resumeAt={movieState && !movieState.watched ? movieState.position : 0}
                />
            )}
            {episode && (
                <PlayOnTvButton
                    target={episode}
                    resumeAt={episode.resumeAt}
                    label={`${episodeCode(episode.season, episode.episode)} sur la TV`}
                />
            )}

            {/* ── Action secondaire ─────────────────────────────── */}
            {playable ? (
                searchButton(false)
            ) : (
                <Button size="lg" variant="outline" className="flex-1 sm:flex-none" onClick={onManualSearch}>
                    <Radar /> Recherche manuelle
                </Button>
            )}

            {/* ── Bande-annonce (discrète, lecteur intégré) ─────── */}
            <TrailerModal youtubeId={media.youtube_trailer_id} title={media.title} />

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

/* ── Pièces (préréglages de l'ampli) ─────────────────────── */

/*
 * Libellés et icônes des pièces : ceux de la télécommande (ROOM_META), pour
 * que « Salon » / « Salle de cinéma » se ressemblent partout dans l'app.
 */
const ROOM_IDS: KodiRoom[] = ["salon", "cinema"];

/** Résumé par défaut d'un préréglage, si les profils de l'ampli sont illisibles. */
const DEFAULT_HINTS: Record<KodiRoom, string> = {
    salon: "Volume modéré · dialogues renforcés",
    cinema: "Volume cinéma · son direct (Atmos / DTS:X)",
};

/** « Volume 40 % · Surround Decoder » : ce que le préréglage va vraiment appliquer. */
function roomHint(room: KodiRoom, profile?: RoomProfile): string {
    if (!profile) return DEFAULT_HINTS[room];
    const parts = [
        typeof profile.volume_raw === "number" ? `Volume ${volumePct(profile.volume_raw)} %` : null,
        profile.movie_sound_program ? soundProgramShortLabel(profile.movie_sound_program) : null,
    ].filter((v): v is string => !!v);
    return parts.length > 0 ? parts.join(" · ") : DEFAULT_HINTS[room];
}

/** Pièce à partir d'une valeur libre (réponse backend) ; « salon » par défaut, comme le backend. */
const roomOf = (value?: string | null): KodiRoom => (value && /cin/i.test(value) ? "cinema" : "salon");

const ROOM_STORAGE_KEY = "arrmada:kodi-room";

/**
 * Dernière pièce choisie, mémorisée dans le navigateur : le bouton principal
 * relance dans la même pièce sans rouvrir le menu. Lue après le montage
 * (pas de stockage côté serveur) et protégée (stockage bloqué = « Salon »).
 */
function useRoomPreference() {
    const [room, setRoom] = useState<KodiRoom>("salon");
    useEffect(() => {
        try {
            const saved = window.localStorage.getItem(ROOM_STORAGE_KEY);
            if (saved === "salon" || saved === "cinema") setRoom(saved);
        } catch {
            /* stockage indisponible : on reste sur « Salon » */
        }
    }, []);
    const update = useCallback((next: KodiRoom) => {
        setRoom(next);
        try {
            window.localStorage.setItem(ROOM_STORAGE_KEY, next);
        } catch {
            /* pas mémorisé, sans gravité */
        }
    }, []);
    return [room, update] as const;
}

/**
 * Action principale d'un film présent sur le disque : « Lire · <pièce> »
 * (bouton scindé : choix Salon / Salle de cinéma, autres Kodi, Caster), ou
 * « Caster » si aucun Kodi n'est configuré. Composant séparé pour ne pas
 * interroger la config Kodi sur les séries / films absents.
 */
function PlayAction({ media }: { media: MediaDetail }) {
    const qc = useQueryClient();
    const kodiPlay = useKodiPlay();
    const [castOpen, setCastOpen] = useState(false);
    const [room, setRoom] = useRoomPreference();
    const current = ROOM_META[room];
    const RoomIcon = current.icon;
    // Profils audio par pièce (Réglages › Ampli Yamaha) : rendent les
    // indications du menu fidèles à TA configuration. Facultatif.
    const { data: profiles } = useYamahaProfiles();

    // Instances Kodi configurées : le libellé reprend leur vrai nom
    // (avant : « Kodi (Salon) » codé en dur).
    const { data: kodiSettings, isSuccess: kodiKnown } = useKodiSettings();
    // Tri par id : la première instance est aussi celle que le backend choisit par défaut.
    const kodis = (kodiSettings ?? []).filter((k) => k.is_enabled).sort((a, b) => a.id - b.id);
    // Tant qu'on ne sait pas (chargement / erreur), on garde « Lire » :
    // le backend choisit alors la première instance active.
    const canKodi = !kodiKnown || kodis.length > 0;

    const play = (target: KodiRoom, kodi?: KodiInstance) => {
        if (!media.tmdb_id) return;
        kodiPlay.mutate(
            { tmdb_id: media.tmdb_id, service_id: kodi?.id, room: target },
            {
                onSuccess: (r) => {
                    if (r.status !== "ok") {
                        toast.error("Lecture impossible", { description: r.detail || "Kodi n'a pas trouvé ce film dans sa bibliothèque." });
                        return;
                    }
                    const where = ROOM_META[roomOf(r.room ?? target)].label;
                    const device = r.kodi ?? kodi?.name ?? "Kodi";
                    const avr = r.avr;
                    // « Aucun ampli configuré » n'est pas une panne : pas d'alerte dans ce cas.
                    if (avr?.status === "error" && !/aucun ampli/i.test(avr.detail ?? "")) {
                        toast.warning(`Lecture lancée — ${where}`, {
                            description: `Sur ${device}, mais l'ampli n'a pas pu être réglé${avr.detail ? ` : ${avr.detail}` : "."}`,
                        });
                    } else {
                        toast.success(`Lecture lancée — ${where}`, {
                            description:
                                avr?.status === "ok"
                                    ? `Sur ${device} · ampli réglé : ${describeApplied(avr.applied) ?? "préréglage appliqué"}.`
                                    : `Sur ${device}. La télécommande s'affiche sous l'en-tête dans quelques secondes.`,
                        });
                    }
                    qc.invalidateQueries({ queryKey: ["kodi", "now-playing"] });
                    // Volume / programme sonore de l'ampli viennent de changer.
                    qc.invalidateQueries({ queryKey: ["yamaha", "state"] });
                },
                onError: (e) => toast.error("Kodi injoignable", { description: e.message }),
            },
        );
    };

    /** Choix d'une pièce dans le menu : mémorisée, puis lecture immédiate. */
    const playInRoom = (target: KodiRoom) => {
        setRoom(target);
        play(target, kodis[0]);
    };

    return (
        <>
            {canKodi ? (
                <div className="flex flex-1 rounded-xl sm:flex-none">
                    <Button
                        size="lg"
                        className="min-w-0 flex-1 rounded-r-none pr-4 sm:flex-none"
                        disabled={kodiPlay.isPending}
                        onClick={() => play(room, kodis[0])}
                        title="Lancer la lecture sur Kodi & régler l'ampli"
                    >
                        {kodiPlay.isPending ? <Loader2 className="animate-spin" /> : <Play className="fill-current" />}
                        <span className="truncate">{kodis.length > 1 ? `Lire sur ${kodis[0].name}` : "Lire"}</span>
                        {/* Pièce mémorisée : change d'une pièce à l'autre avec une petite animation. */}
                        <motion.span
                            key={room}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.25 }}
                            className="inline-flex shrink-0 items-center gap-1 rounded-md bg-black/20 px-1.5 py-0.5 text-xs font-semibold"
                        >
                            <RoomIcon className="!size-3.5" aria-hidden />
                            {current.short}
                        </motion.span>
                    </Button>
                    <DropdownMenu modal={false}>
                        <DropdownMenuTrigger asChild>
                            <Button
                                size="lg"
                                className="rounded-l-none border-l border-black/20 px-2.5"
                                aria-label="Choisir la pièce ou l'appareil de lecture"
                                title="Choisir la pièce (Salon / Salle de cinéma)"
                                disabled={kodiPlay.isPending}
                            >
                                <ChevronDown />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[min(18rem,calc(100vw-2rem))]">
                            <DropdownMenuLabel className="eyebrow leading-relaxed">Lancer la lecture sur Kodi & régler l&apos;ampli</DropdownMenuLabel>
                            {ROOM_IDS.map((id) => {
                                const meta = ROOM_META[id];
                                const Icon = meta.icon;
                                const selected = id === room;
                                return (
                                    <DropdownMenuItem key={id} onSelect={() => playInRoom(id)} className="items-start py-2">
                                        <Icon className={cn("mt-0.5", selected ? "text-primary" : "text-muted-foreground")} aria-hidden />
                                        <span className="min-w-0 flex-1">
                                            <span className={cn("block font-medium", selected && "text-primary")}>{meta.label}</span>
                                            <span className="block text-[11px] text-muted-foreground">{roomHint(id, profiles?.[id])}</span>
                                        </span>
                                        {selected && <Check className="mt-0.5 text-primary" aria-label="Dernière pièce utilisée" />}
                                    </DropdownMenuItem>
                                );
                            })}
                            {kodis.length > 1 && (
                                <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuLabel className="eyebrow">Lire sur · {current.label}</DropdownMenuLabel>
                                    {kodis.map((k) => (
                                        <DropdownMenuItem key={k.id} onSelect={() => play(room, k)}>
                                            <MonitorPlay /> {k.name}
                                        </DropdownMenuItem>
                                    ))}
                                </>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onSelect={() => setCastOpen(true)}>
                                <Cast /> Caster sur un appareil…
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                                <Link href="/settings/yamaha" className="text-muted-foreground">
                                    <SlidersHorizontal /> Régler les préréglages de l&apos;ampli…
                                </Link>
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
