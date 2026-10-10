"use client";

/**
 * Télécommande de lecture affichée sur la fiche du média EN COURS de lecture.
 * ----------------------------------------------------------------
 * Avant : les télécommandes Kodi + Yamaha s'affichaient sur TOUTES les fiches
 * dès que Kodi lisait n'importe quoi. Désormais elles n'apparaissent que si
 * `now-playing` correspond à ce film / cette série.
 *
 * Corrigé aussi :
 *  - la barre de progression est un vrai curseur accessible (clavier, lecteur
 *    d'écran, glisser au doigt) ;
 *  - le volume est « debouncé » : pendant le glisser on envoie au plus une
 *    commande toutes les 250 ms, et le curseur ne saute plus ;
 *  - toute commande refusée par Kodi affiche un toast.
 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { MonitorPlay, Pause, Play, Square, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { YamahaRemote } from "@/components/yamaha-remote";
import { useKodiControl, useKodiNowPlaying, type KodiNowPlaying } from "@/hooks/use-kodi";
import type { MediaDetail } from "@/hooks/use-media";
import { formatClock } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { audioChannelsLabel, resolutionLabel } from "./labels";
import { Scrubber } from "./scrubber";

const normalize = (s: string) =>
    s
        .toLowerCase()
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();

/** Kodi renvoie « hdr10 », « dolbyvision », « hlg »… → libellés lisibles. */
function kodiHdrLabel(hdr: string | null | undefined): string | null {
    if (!hdr) return null;
    const map: Record<string, string> = { hdr10: "HDR10", hdr10plus: "HDR10+", dolbyvision: "Dolby Vision", hlg: "HLG" };
    return map[hdr.toLowerCase().replace(/[^a-z0-9]/g, "")] ?? hdr;
}

/** La lecture Kodi concerne-t-elle CE média ? */
export function nowPlayingMatches(np: KodiNowPlaying | undefined, media: MediaDetail): boolean {
    if (!np?.playing) return false;
    // Cas nominal : le backend a relié la lecture à un média de la bibliothèque.
    if (np.media_id != null && String(np.media_id) === String(media.id)) {
        const t = np.media_type;
        return !t || t === media.type || (media.type === "series" && t === "episode");
    }
    // Épisode : Kodi ne connaît pas l'id Sonarr, mais le sous-titre vaut
    // « Nom de la série S1E2 » → on compare le nom de la série.
    if (media.type === "series" && np.type === "episode" && np.subtitle) {
        return normalize(np.subtitle).startsWith(`${normalize(media.title)} s`);
    }
    return false;
}

export function PlaybackRemote({ media }: { media: MediaDetail }) {
    const { data: np } = useKodiNowPlaying(true);
    const visible = nowPlayingMatches(np, media);

    return (
        <AnimatePresence initial={false}>
            {visible && np && (
                <motion.section
                    key="remote"
                    aria-label="Télécommande de lecture"
                    initial={{ opacity: 0, height: 0, y: 12 }}
                    animate={{ opacity: 1, height: "auto", y: 0 }}
                    exit={{ opacity: 0, height: 0, y: 12 }}
                    transition={{ duration: 0.45, ease: EASE_OUT }}
                    className="overflow-hidden"
                >
                    <div className="grid items-start gap-4 pb-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
                        <KodiRemote np={np} />
                        <YamahaRemote />
                    </div>
                </motion.section>
            )}
        </AnimatePresence>
    );
}

function KodiRemote({ np }: { np: KodiNowPlaying }) {
    const control = useKodiControl();
    const volTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => {
        if (volTimer.current) clearTimeout(volTimer.current);
    }, []);

    const send = (action: "playpause" | "stop" | "seek" | "volume" | "mute", value?: number) =>
        control.mutate(
            { action, value },
            { onError: (e) => toast.error("Commande Kodi refusée", { description: e.message }) },
        );

    // Volume : au plus un envoi toutes les 250 ms pendant le glisser (on
    // entend le changement en direct sans inonder Kodi de requêtes)…
    const lastVolSent = useRef(0);
    const sendVolumeThrottled = (v: number) => {
        if (volTimer.current) clearTimeout(volTimer.current);
        const wait = 250 - (Date.now() - lastVolSent.current);
        const fire = () => {
            lastVolSent.current = Date.now();
            send("volume", Math.round(v));
        };
        if (wait <= 0) fire();
        else volTimer.current = setTimeout(fire, wait);
    };
    // … et un envoi immédiat au relâchement (on annule l'envoi en attente).
    const commitVolume = (v: number) => {
        if (volTimer.current) clearTimeout(volTimer.current);
        send("volume", Math.round(v));
    };

    const pct = np.total ? Math.min(100, ((np.position ?? 0) / np.total) * 100) : np.percentage ?? 0;
    const total = np.total ?? 0;
    const tech = [resolutionLabel(np.resolution ?? undefined), kodiHdrLabel(np.hdr), [np.audio_codec?.toUpperCase(), audioChannelsLabel(np.audio_channels)].filter(Boolean).join(" ")].filter(
        (v): v is string => !!v,
    );
    const volume = np.muted ? 0 : np.volume ?? 100;

    return (
        <div className="glass border-gradient relative overflow-hidden rounded-2xl p-4 sm:p-5">
            {/* Halo violet (= « lecture » dans le code couleur de l'app) */}
            <div
                aria-hidden
                className="pointer-events-none absolute -left-20 -top-24 h-64 w-64 rounded-full opacity-50"
                style={{ background: "radial-gradient(closest-side, hsl(262 83% 60% / 0.6), transparent)" }}
            />
            <div className="relative flex gap-4">
                {np.poster && (
                    <img
                        src={np.poster}
                        alt=""
                        loading="lazy"
                        className="hidden h-24 w-16 shrink-0 rounded-lg object-cover shadow-lg ring-1 ring-white/10 sm:block"
                    />
                )}
                <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="relative flex h-2 w-2">
                            {!np.paused && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-violet-400" />}
                            <span className="relative h-2 w-2 rounded-full bg-violet-400 shadow-[0_0_10px] shadow-violet-400" />
                        </span>
                        <span className="flex items-center gap-1.5 text-xs font-medium text-violet-300">
                            <MonitorPlay className="h-3.5 w-3.5" aria-hidden />
                            En lecture sur {np.kodi ?? "Kodi"}
                        </span>
                        {np.paused && (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-px text-[10px] font-semibold text-amber-300">
                                En pause
                            </span>
                        )}
                        {tech.map((t) => (
                            <span key={t} className="rounded-md bg-white/[0.06] px-1.5 py-px text-[10px] font-medium text-muted-foreground">
                                {t}
                            </span>
                        ))}
                    </div>

                    <div className="min-w-0">
                        <p className="truncate text-base font-semibold">{np.title}</p>
                        {np.subtitle && <p className="truncate text-xs text-muted-foreground">{np.subtitle}</p>}
                    </div>

                    <div>
                        <Scrubber
                            value={pct}
                            label="Position de lecture"
                            valueText={(v) => `${formatClock((v / 100) * total)} sur ${formatClock(total)}`}
                            onCommit={(v) => send("seek", Math.round(v))}
                            disabled={!total}
                        />
                        <div className="flex justify-between text-[11px] tabular-nums text-muted-foreground">
                            <span>{formatClock(np.position)}</span>
                            <span>-{formatClock(Math.max(0, total - (np.position ?? 0)))}</span>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button
                            size="icon"
                            aria-label={np.paused ? "Reprendre la lecture" : "Mettre en pause"}
                            onClick={() => send("playpause")}
                            className="h-11 w-11 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-[0_0_24px_-4px_hsl(262_83%_60%/0.9)] [&_svg]:size-5"
                        >
                            {np.paused ? <Play className="fill-current" /> : <Pause className="fill-current" />}
                        </Button>
                        <Button size="icon" variant="outline" aria-label="Arrêter la lecture" onClick={() => send("stop")} className="rounded-full">
                            <Square />
                        </Button>
                        <div className="flex-1" />
                        <Button
                            size="icon-sm"
                            variant="ghost"
                            aria-label={np.muted ? "Réactiver le son" : "Couper le son"}
                            aria-pressed={!!np.muted}
                            onClick={() => send("mute")}
                        >
                            {np.muted ? <VolumeX className="text-red-400" /> : <Volume2 />}
                        </Button>
                        <Scrubber
                            value={volume}
                            label="Volume Kodi"
                            size="sm"
                            step={5}
                            onChange={sendVolumeThrottled}
                            onCommit={commitVolume}
                            className="w-24 sm:w-32"
                        />
                        <span className={cn("w-8 text-right text-[11px] tabular-nums text-muted-foreground")}>{Math.round(volume)}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
