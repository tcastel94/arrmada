"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { Play, Pause, Square, Tv, Film, Star, Clock, Volume2, VolumeX, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useKodiNowPlaying, useKodiControl } from "@/hooks/use-kodi";
import { cn } from "@/lib/utils";

function fmtTime(sec?: number): string {
    const s = Math.max(0, Math.floor(sec || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    const pad = (n: number) => String(n).padStart(2, "0");
    return h > 0 ? `${h}:${pad(m)}:${pad(ss)}` : `${m}:${pad(ss)}`;
}

function fmtChannels(ch?: number | null): string | null {
    if (!ch) return null;
    if (ch <= 1) return "Mono";
    if (ch === 2) return "2.0";
    if (ch === 6) return "5.1";
    if (ch === 8) return "7.1";
    return `${ch}ch`;
}

/** Prominent card showing what's currently playing on Kodi — only visible while playing. */
export function NowPlayingCard() {
    const { data } = useKodiNowPlaying(true);
    const control = useKodiControl();
    const np = data;

    const visible = !!np?.playing;
    const remaining = np ? Math.max(0, (np.total || 0) - (np.position || 0)) : 0;

    const techBadges = np
        ? [
              np.resolution,
              np.hdr,
              np.video_codec,
              np.audio_codec,
              fmtChannels(np.audio_channels),
          ].filter(Boolean)
        : [];

    return (
        <AnimatePresence>
            {visible && np && (
                <motion.div
                    initial={{ opacity: 0, y: -12, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: "auto" }}
                    exit={{ opacity: 0, y: -12, height: 0 }}
                    transition={{ duration: 0.35, ease: "easeOut" }}
                >
                    <Card className="relative overflow-hidden border-0 ring-1 ring-white/10 bg-card/40 backdrop-blur-sm">
                        {/* Blurred poster backdrop */}
                        {np.poster && (
                            <div
                                className="absolute inset-0 opacity-20 blur-2xl scale-110"
                                style={{
                                    backgroundImage: `url(${np.poster})`,
                                    backgroundSize: "cover",
                                    backgroundPosition: "center 30%",
                                }}
                            />
                        )}
                        <div className="absolute inset-0 bg-gradient-to-r from-background/80 via-background/60 to-background/30" />

                        <div className="relative flex gap-4 p-4 sm:p-5">
                            {/* Poster */}
                            <div className="shrink-0">
                                {np.poster ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={np.poster}
                                        alt={np.title || ""}
                                        className="h-36 w-24 sm:h-44 sm:w-28 rounded-lg object-cover ring-1 ring-white/10 shadow-lg"
                                    />
                                ) : (
                                    <div className="h-36 w-24 sm:h-44 sm:w-28 rounded-lg bg-muted/30 ring-1 ring-white/10 flex items-center justify-center">
                                        {np.type === "episode" ? (
                                            <Tv className="h-8 w-8 text-muted-foreground/40" />
                                        ) : (
                                            <Film className="h-8 w-8 text-muted-foreground/40" />
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Info */}
                            <div className="min-w-0 flex-1 flex flex-col">
                                {/* Now-playing chip */}
                                <div className="flex items-center gap-2 mb-1.5">
                                    <span className="relative flex h-2 w-2">
                                        {!np.paused && (
                                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                                        )}
                                        <span className={cn("relative inline-flex h-2 w-2 rounded-full", np.paused ? "bg-amber-400" : "bg-emerald-400")} />
                                    </span>
                                    <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                                        {np.paused ? "En pause" : "En lecture"}
                                        {np.kodi ? ` · ${np.kodi}` : ""}
                                    </span>
                                </div>

                                {/* Title */}
                                <h3 className="text-lg sm:text-xl font-bold leading-tight truncate">{np.title}</h3>
                                {np.subtitle && (
                                    <p className="text-sm text-muted-foreground truncate">{np.subtitle}</p>
                                )}

                                {/* Meta row */}
                                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                    {np.year ? <span className="tabular-nums">{np.year}</span> : null}
                                    {np.runtime ? (
                                        <span className="flex items-center gap-1">
                                            <Clock className="h-3 w-3" />
                                            {np.runtime} min
                                        </span>
                                    ) : null}
                                    {np.rating ? (
                                        <span className="flex items-center gap-1">
                                            <Star className="h-3 w-3 text-amber-400" />
                                            {np.rating}
                                        </span>
                                    ) : null}
                                    {np.genres && np.genres.length > 0 && (
                                        <span className="truncate">{np.genres.slice(0, 3).join(" · ")}</span>
                                    )}
                                </div>

                                {/* Tech badges */}
                                {techBadges.length > 0 && (
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                        {techBadges.map((b, i) => (
                                            <Badge
                                                key={i}
                                                variant="outline"
                                                className="text-[10px] px-1.5 py-0 h-5 border-white/10 text-muted-foreground font-mono"
                                            >
                                                {b}
                                            </Badge>
                                        ))}
                                        {np.muted ? (
                                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 border-white/10 text-muted-foreground">
                                                <VolumeX className="h-3 w-3" />
                                            </Badge>
                                        ) : (
                                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 border-white/10 text-muted-foreground gap-1">
                                                <Volume2 className="h-3 w-3" />
                                                {np.volume}
                                            </Badge>
                                        )}
                                    </div>
                                )}

                                {/* Spacer pushes progress + controls to the bottom */}
                                <div className="flex-1" />

                                {/* Progress */}
                                <div className="mt-3 space-y-1">
                                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted/30">
                                        <div
                                            className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-blue-400 transition-[width] duration-1000 ease-linear"
                                            style={{ width: `${np.percentage ?? 0}%` }}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between text-[11px] tabular-nums text-muted-foreground">
                                        <span>{fmtTime(np.position)}</span>
                                        <span>-{fmtTime(remaining)}</span>
                                    </div>
                                </div>

                                {/* Controls */}
                                <div className="mt-2.5 flex items-center gap-2">
                                    <Button
                                        size="sm"
                                        variant="secondary"
                                        className="h-8 gap-1.5"
                                        disabled={control.isPending}
                                        onClick={() => control.mutate({ action: "playpause" })}
                                    >
                                        {np.paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                                        {np.paused ? "Reprendre" : "Pause"}
                                    </Button>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8 text-muted-foreground hover:text-red-400"
                                        disabled={control.isPending}
                                        onClick={() => control.mutate({ action: "stop" })}
                                        title="Arrêter"
                                    >
                                        <Square className="h-4 w-4" />
                                    </Button>
                                    {np.media_id && np.media_type && (
                                        <Link
                                            href={`/media/${np.media_type}/${np.media_id}`}
                                            className="ml-auto text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                                        >
                                            Fiche
                                            <ArrowUpRight className="h-3.5 w-3.5" />
                                        </Link>
                                    )}
                                </div>
                            </div>
                        </div>
                    </Card>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
