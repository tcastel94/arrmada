"use client";

/**
 * « Sur la TV » : lance un film ou un épisode sur une TV appairée (appli Kodi 1.19).
 * ----------------------------------------------------------------
 * La web app ne parle pas à Kodi : elle demande au serveur de publier une
 * demande de lecture adressée à UNE TV. Cette TV la relève dans les 5 s, cherche
 * le titre dans SA médiathèque Kodi et le lance (reprise comprise, préréglage
 * de l'ampli de sa pièce). Analogie : un message sur un bus avec l'adresse du
 * destinataire, plutôt qu'une connexion entrante vers la TV.
 *
 * Piège : une TV éteinte ne reçoit rien ; la demande expire au bout de 2 min
 * (pas de lecture surprise au rallumage). Le menu signale les TV « absentes ».
 */
import { toast } from "sonner";
import { Loader2, RotateCcw, Tv } from "lucide-react";
import { Button, type ButtonProps } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { clockLabel, usePlayOnDevice, useTvDevices, type PlayTarget } from "@/hooks/use-watch";
import type { PairedDevice } from "@/hooks/use-devices";
import type { MediaDetail } from "@/hooks/use-media";
import type { WatchSeriesState } from "@/hooks/use-watch";
import { cn } from "@/lib/utils";

/** La TV a relevé les événements récemment (le serveur note son passage une fois par minute). */
export function isTvOnline(device: Pick<PairedDevice, "last_seen_at">, now = Date.now()): boolean {
    if (!device.last_seen_at) return false;
    // Le serveur renvoie une date UTC sans fuseau : sans « Z », le navigateur
    // la lirait comme une heure locale (décalage d'une ou deux heures).
    const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(device.last_seen_at) ? device.last_seen_at : `${device.last_seen_at}Z`;
    const seen = Date.parse(iso);
    return Number.isFinite(seen) && now - seen <= 150_000;
}

/**
 * Épisode à proposer pour une série : celui en cours, sinon le suivant du
 * dernier vu (présent sur le disque), sinon le premier présent. Spéciaux ignorés.
 */
export function seriesTarget(
    media: Pick<MediaDetail, "seasons" | "tvdb_id" | "title">,
    state?: WatchSeriesState | null,
): (PlayTarget & { resumeAt: number }) | null {
    if (!media.tvdb_id) return null;
    const episodes = (media.seasons ?? [])
        .filter((s) => s.season_number > 0)
        .flatMap((s) => s.episodes ?? [])
        .filter((e) => e.has_file)
        .sort((a, b) => a.season_number - b.season_number || a.episode_number - b.episode_number);
    const make = (season: number, episode: number, resumeAt = 0) => ({
        media_type: "episode" as const,
        id: media.tvdb_id as number,
        season,
        episode,
        title: media.title,
        resumeAt,
    });
    const last = state?.last;
    if (last && !last.watched && last.position > 0) return make(last.season, last.episode, last.position);
    if (last) {
        const next = episodes.find(
            (e) => e.season_number > last.season || (e.season_number === last.season && e.episode_number > last.episode),
        );
        return next ? make(next.season_number, next.episode_number) : null;
    }
    return episodes[0] ? make(episodes[0].season_number, episodes[0].episode_number) : null;
}

interface PlayOnTvButtonProps {
    target: PlayTarget;
    /** Position de reprise connue (s) : propose « Reprendre à … » ET « Depuis le début ». */
    resumeAt?: number;
    label?: string;
    size?: ButtonProps["size"];
    variant?: ButtonProps["variant"];
    className?: string;
}

export function PlayOnTvButton({ target, resumeAt = 0, label = "Sur la TV", size = "lg", variant = "outline", className }: PlayOnTvButtonProps) {
    const tvs = useTvDevices();
    const play = usePlayOnDevice();
    if (tvs.length === 0) return null; // aucune TV appairée : rien à proposer

    const send = (device: PairedDevice, resume: boolean) =>
        play.mutate(
            { ...target, device_id: device.id, resume },
            {
                onSuccess: (r) =>
                    r.online
                        ? toast.success(`Demande envoyée à ${r.device}`, {
                              description: "La lecture démarre dans quelques secondes.",
                          })
                        : toast.warning(`Demande envoyée à ${r.device}`, {
                              description: "Cette TV ne s'est pas manifestée récemment : allumée ? La demande expire dans 2 min.",
                          }),
                onError: (e) => toast.error("Lecture impossible", { description: e.message }),
            },
        );

    return (
        <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
                <Button
                    size={size}
                    variant={variant}
                    className={cn(label && "flex-1 sm:flex-none", className)}
                    disabled={play.isPending}
                    aria-label={label || "Lancer sur une TV"}
                    title="Lancer sur une TV appairée"
                >
                    {play.isPending ? <Loader2 className="animate-spin" /> : <Tv />}
                    {label && <span className="truncate">{label}</span>}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[min(18rem,calc(100vw-2rem))]">
                <DropdownMenuLabel className="eyebrow leading-relaxed">
                    {resumeAt > 0 ? `Reprendre à ${clockLabel(resumeAt)} sur…` : "Lancer sur la TV…"}
                </DropdownMenuLabel>
                {tvs.map((tv) => (
                    <TvItem key={tv.id} device={tv} onSelect={() => send(tv, true)} />
                ))}
                {resumeAt > 0 && (
                    <>
                        <DropdownMenuSeparator />
                        <DropdownMenuLabel className="eyebrow">Depuis le début sur…</DropdownMenuLabel>
                        {tvs.map((tv) => (
                            <DropdownMenuItem key={tv.id} onSelect={() => send(tv, false)}>
                                <RotateCcw /> {tv.name}
                            </DropdownMenuItem>
                        ))}
                    </>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}

function TvItem({ device, onSelect }: { device: PairedDevice; onSelect: () => void }) {
    const online = isTvOnline(device);
    return (
        <DropdownMenuItem onSelect={onSelect} className="items-start py-2">
            <Tv className={cn("mt-0.5", online ? "text-primary" : "text-muted-foreground")} aria-hidden />
            <span className="min-w-0 flex-1">
                <span className="block font-medium">{device.name}</span>
                <span className="block text-[11px] text-muted-foreground">
                    {device.room === "cinema" ? "Salle de cinéma" : "Salon"} · {online ? "en ligne" : "absente (éteinte ?)"}
                </span>
            </span>
            <span
                className={cn("mt-1.5 size-2 shrink-0 rounded-full", online ? "bg-emerald-400" : "bg-muted-foreground/40")}
                aria-label={online ? "En ligne" : "Absente"}
            />
        </DropdownMenuItem>
    );
}
