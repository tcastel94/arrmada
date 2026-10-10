"use client";

/**
 * Carte « En lecture » (Dashboard) — visible uniquement pendant une lecture
 * Kodi. Ambiance cinéma : affiche floutée en fond, égaliseur animé,
 * progression lumineuse, badges techniques (4K, HDR, codec, 5.1…).
 */
/* eslint-disable @next/next/no-img-element */
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { Play, Pause, Square, Tv, Film, Star, Clock, Volume2, VolumeX, ArrowUpRight, Sofa } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
    const { data: np } = useKodiNowPlaying(true);
    const control = useKodiControl();

    const visible = !!np?.playing;
    const remaining = np ? Math.max(0, (np.total || 0) - (np.position || 0)) : 0;
    const pct = np?.total ? Math.min(100, ((np.position || 0) / np.total) * 100) : np?.percentage ?? 0;
    const techBadges = np
        ? [np.resolution, np.hdr, np.video_codec, np.audio_codec, fmtChannels(np.audio_channels)].filter(Boolean)
        : [];

    const send = (action: "playpause" | "stop") =>
        control.mutate({ action }, { onError: (e) => toast.error("Commande Kodi refusée", { description: e.message }) });

    return (
        <AnimatePresence>
            {visible && np && (
                <motion.section
                    initial={{ opacity: 0, height: 0, y: -10 }}
                    animate={{ opacity: 1, height: "auto", y: 0 }}
                    exit={{ opacity: 0, height: 0, y: -10 }}
                    transition={{ duration: 0.5, ease: EASE_OUT }}
                    className="overflow-hidden"
                >
                    <div className="glass border-gradient relative overflow-hidden rounded-3xl">
                        {/* Affiche floutée en arrière-plan */}
                        {np.poster && (
                            <div
                                aria-hidden
                                className="absolute inset-0 scale-125 opacity-30 blur-3xl saturate-150"
                                style={{
                                    backgroundImage: `url("${np.poster}")`,
                                    backgroundSize: "cover",
                                    backgroundPosition: "center 30%",
                                }}
                            />
                        )}
                        <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-background/90 via-background/70 to-background/30" />

                        <div className="relative flex gap-4 p-4 sm:gap-6 sm:p-6">
                            {/* Affiche */}
                            <motion.div
                                initial={{ rotate: -4, scale: 0.9, opacity: 0 }}
                                animate={{ rotate: 0, scale: 1, opacity: 1 }}
                                transition={{ type: "spring", stiffness: 200, damping: 18, delay: 0.15 }}
                                className="relative shrink-0"
                            >
                                <div className="absolute -inset-2 rounded-2xl bg-primary/30 blur-xl animate-pulse-glow" aria-hidden />
                                {np.poster ? (
                                    <img
                                        src={np.poster}
                                        alt={np.title || ""}
                                        className="relative h-36 w-24 rounded-xl object-cover shadow-2xl ring-1 ring-white/15 sm:h-48 sm:w-32"
                                    />
                                ) : (
                                    <div className="relative flex h-36 w-24 items-center justify-center rounded-xl bg-muted/50 ring-1 ring-white/10 sm:h-48 sm:w-32">
                                        {np.type === "episode" ? <Tv className="h-8 w-8 opacity-40" /> : <Film className="h-8 w-8 opacity-40" />}
                                    </div>
                                )}
                            </motion.div>

                            {/* Infos */}
                            <div className="flex min-w-0 flex-1 flex-col">
                                <div className="mb-2 flex items-center gap-2">
                                    {/* Égaliseur */}
                                    <span className="flex h-3.5 items-end gap-[3px]" aria-hidden>
                                        {[0, 1, 2, 3].map((i) => (
                                            <motion.span
                                                key={i}
                                                className="w-[3px] rounded-full bg-gradient-to-t from-primary to-brand"
                                                animate={np.paused ? { height: 3 } : { height: [3, 14, 6, 12, 4] }}
                                                transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
                                            />
                                        ))}
                                    </span>
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                                        {np.paused ? "En pause" : "En lecture"}
                                    </span>
                                    {np.kodi && (
                                        <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                            <Sofa className="h-3 w-3" /> {np.kodi}
                                        </span>
                                    )}
                                </div>

                                <h2 className="truncate text-xl font-bold leading-tight tracking-tight sm:text-3xl">{np.title}</h2>
                                {np.subtitle && <p className="truncate text-sm text-muted-foreground">{np.subtitle}</p>}

                                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                    {np.year ? <span className="tabular-nums">{np.year}</span> : null}
                                    {np.runtime ? (
                                        <span className="flex items-center gap-1">
                                            <Clock className="h-3 w-3" /> {np.runtime} min
                                        </span>
                                    ) : null}
                                    {np.rating ? (
                                        <span className="flex items-center gap-1">
                                            <Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {np.rating.toFixed(1)}
                                        </span>
                                    ) : null}
                                    {np.genres && np.genres.length > 0 && <span className="truncate">{np.genres.slice(0, 3).join(" · ")}</span>}
                                </div>

                                {techBadges.length > 0 && (
                                    <div className="mt-3 hidden flex-wrap gap-1.5 sm:flex">
                                        {techBadges.map((b) => (
                                            <span
                                                key={String(b)}
                                                className="rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 font-mono text-[10px] text-foreground/80 backdrop-blur"
                                            >
                                                {b}
                                            </span>
                                        ))}
                                        <span className="flex items-center gap-1 rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 font-mono text-[10px] text-foreground/80 backdrop-blur">
                                            {np.muted ? <VolumeX className="h-3 w-3" /> : <Volume2 className="h-3 w-3" />}
                                            {np.muted ? "muet" : `${np.volume ?? 0} %`}
                                        </span>
                                    </div>
                                )}

                                <div className="flex-1" />

                                {/* Progression */}
                                <div className="mt-4 space-y-1.5">
                                    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                                        <motion.div
                                            className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary via-sky-400 to-brand shadow-[0_0_14px_hsl(var(--primary))]"
                                            animate={{ width: `${pct}%` }}
                                            transition={{ duration: 1, ease: "linear" }}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between text-[11px] tabular-nums text-muted-foreground">
                                        <span>{formatClock(np.position)}</span>
                                        <span>-{formatClock(remaining)}</span>
                                    </div>
                                </div>

                                {/* Commandes */}
                                <div className="mt-3 flex min-w-0 items-center gap-2">
                                    <Button size="sm" onClick={() => send("playpause")} disabled={control.isPending}>
                                        {np.paused ? <Play className="fill-current" /> : <Pause className="fill-current" />}
                                        {np.paused ? "Reprendre" : "Pause"}
                                    </Button>
                                    <Button
                                        size="icon-sm"
                                        variant="ghost"
                                        onClick={() => send("stop")}
                                        disabled={control.isPending}
                                        aria-label="Arrêter la lecture"
                                        className="hover:text-red-400"
                                    >
                                        <Square className="fill-current" />
                                    </Button>
                                    <div className="ml-auto flex items-center gap-3 text-xs">
                                        <Link href="/remote" className="hidden text-muted-foreground transition-colors hover:text-primary sm:inline">
                                            Télécommande
                                        </Link>
                                        {np.media_id && np.media_type && (
                                            <Link
                                                href={`/media/${np.media_type}/${np.media_id}`}
                                                className="flex items-center gap-1 text-muted-foreground transition-colors hover:text-primary"
                                            >
                                                Fiche <ArrowUpRight className="h-3.5 w-3.5" />
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.section>
            )}
        </AnimatePresence>
    );
}
