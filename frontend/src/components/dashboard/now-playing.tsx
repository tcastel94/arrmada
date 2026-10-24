"use client";

/**
 * Carte « En lecture » de l'Accueil — visible uniquement pendant une
 * lecture Kodi. Style « À l'écran » des apps Apple : affiche, titre,
 * TV qui joue, progression et temps restant, commandes, détails
 * techniques en petites étiquettes grises.
 */
/* eslint-disable @next/next/no-img-element */
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { Film, Pause, Play, Square, Tv } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useModuleEnabled } from "@/hooks/use-modules";
import { useKodiNowPlaying, useKodiControl } from "@/hooks/use-kodi";
import { formatClock } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";

/** Nombre de canaux audio → notation home-cinéma. */
function fmtChannels(ch?: number | null): string | null {
    if (!ch) return null;
    if (ch <= 1) return "Mono";
    if (ch === 2) return "Stéréo";
    if (ch === 6) return "5.1";
    if (ch === 8) return "7.1";
    return `${ch} canaux`;
}

export function NowPlayingCard() {
    // Sans TV (module désactivé), pas d'interrogation de Kodi toutes les secondes
    const { data: np } = useKodiNowPlaying(useModuleEnabled()("tv"));
    const control = useKodiControl();

    const visible = !!np?.playing;
    const remaining = np ? Math.max(0, (np.total || 0) - (np.position || 0)) : 0;
    const pct = np?.total ? Math.min(100, ((np.position || 0) / np.total) * 100) : np?.percentage ?? 0;
    const tech = np ? [np.resolution, np.hdr, np.video_codec, np.audio_codec, fmtChannels(np.audio_channels)].filter(Boolean) : [];
    const href = np?.media_id && np?.media_type ? `/media/${np.media_type}/${np.media_id}` : "/remote";

    const send = (action: "playpause" | "stop") =>
        control.mutate({ action }, { onError: (e) => toast.error("Commande refusée par la TV", { description: e.message }) });

    return (
        <AnimatePresence initial={false}>
            {visible && np && (
                <motion.section
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.35, ease: EASE_OUT }}
                    className="overflow-hidden"
                >
                    <p className="mb-2.5 text-[20px] font-bold tracking-tight">À l&apos;écran</p>
                    <div className="flex gap-4 rounded-2xl bg-card p-3 sm:p-4">
                        <Link href={href} className="shrink-0">
                            {np.poster ? (
                                <img src={np.poster} alt="" className="h-[132px] w-[88px] rounded-[10px] object-cover sm:h-[156px] sm:w-[104px]" />
                            ) : (
                                <div className="flex h-[132px] w-[88px] items-center justify-center rounded-[10px] bg-white/[0.06] sm:h-[156px] sm:w-[104px]">
                                    {np.type === "episode" ? <Tv className="h-7 w-7 text-white/25" /> : <Film className="h-7 w-7 text-white/25" />}
                                </div>
                            )}
                        </Link>

                        <div className="flex min-w-0 flex-1 flex-col">
                            <p className="text-[13px] font-medium text-primary">
                                {np.paused ? "En pause" : "En lecture"}
                                {np.kodi ? ` sur ${np.kodi}` : ""}
                            </p>
                            <Link href={href} className="mt-0.5 truncate text-[19px] font-semibold leading-tight tracking-tight hover:underline sm:text-[22px]">
                                {np.title}
                            </Link>
                            {np.subtitle && <p className="truncate text-[14px] text-muted-foreground">{np.subtitle}</p>}
                            {tech.length > 0 && (
                                <div className="mt-2 hidden flex-wrap gap-1 sm:flex">
                                    {tech.map((t) => (
                                        <span key={String(t)} className="rounded-[5px] bg-white/[0.08] px-1.5 py-0.5 text-[11px] font-medium text-foreground/70">
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            )}

                            <div className="flex-1" />

                            {/* Progression */}
                            <div className="mt-3">
                                <div className="h-1 overflow-hidden rounded-full bg-white/[0.12]">
                                    <motion.div className="h-full rounded-full bg-foreground" animate={{ width: `${pct}%` }} transition={{ duration: 1, ease: "linear" }} />
                                </div>
                                <div className="mt-1 flex justify-between text-[11px] tabular-nums text-muted-foreground">
                                    <span>{formatClock(np.position)}</span>
                                    <span>-{formatClock(remaining)}</span>
                                </div>
                            </div>

                            {/* Commandes */}
                            <div className="mt-2 flex items-center gap-2">
                                <Button size="sm" variant="secondary" onClick={() => send("playpause")} disabled={control.isPending}>
                                    {np.paused ? <Play className="fill-current" /> : <Pause className="fill-current" />}
                                    {np.paused ? "Lecture" : "Pause"}
                                </Button>
                                <Button size="icon-sm" variant="secondary" onClick={() => send("stop")} disabled={control.isPending} aria-label="Arrêter la lecture">
                                    <Square className="!size-3.5 fill-current" />
                                </Button>
                                <Link href="/remote" className="ml-auto text-[14px] text-primary hover:opacity-80">
                                    Télécommande
                                </Link>
                            </div>
                        </div>
                    </div>
                </motion.section>
            )}
        </AnimatePresence>
    );
}
