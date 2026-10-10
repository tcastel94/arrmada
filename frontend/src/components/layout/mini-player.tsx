"use client";

/**
 * Mini-lecteur flottant : apparaît sur toutes les pages dès que Kodi lit
 * quelque chose (sauf Dashboard et Salon qui ont déjà leur carte « En
 * lecture »). Lecture/pause, stop, progression, lien vers la fiche.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Pause, Play, Square, Sofa } from "lucide-react";
import { toast } from "sonner";
import { useKodiControl, useKodiNowPlaying } from "@/hooks/use-kodi";
import { formatClock } from "@/lib/format";
import { SPRING_SOFT } from "@/lib/motion";

const HIDDEN_ON = ["/dashboard", "/remote"];

export function MiniPlayer() {
    const pathname = usePathname();
    const { data: np } = useKodiNowPlaying(true);
    const control = useKodiControl();
    const visible = !!np?.playing && !HIDDEN_ON.some((p) => pathname.startsWith(p));
    const pct = np?.total ? Math.min(100, ((np.position || 0) / np.total) * 100) : np?.percentage ?? 0;

    const send = (action: "playpause" | "stop") =>
        control.mutate({ action }, { onError: (e) => toast.error("Commande Kodi refusée", { description: e.message }) });

    const href = np?.media_id && np?.media_type ? `/media/${np.media_type}/${np.media_id}` : "/remote";

    return (
        <AnimatePresence>
            {visible && np && (
                <motion.div
                    initial={{ y: 80, opacity: 0, scale: 0.95 }}
                    animate={{ y: 0, opacity: 1, scale: 1 }}
                    exit={{ y: 80, opacity: 0, scale: 0.95 }}
                    transition={SPRING_SOFT}
                    className="fixed bottom-[calc(5.5rem+env(safe-area-inset-bottom))] left-1/2 z-40 w-[min(calc(100vw-1.5rem),440px)] -translate-x-1/2 lg:bottom-5 lg:left-auto lg:right-5 lg:translate-x-0"
                >
                    <div className="glass-strong border-gradient relative overflow-hidden rounded-2xl">
                        {np.poster && (
                            <div
                                aria-hidden
                                className="absolute inset-0 scale-125 opacity-25 blur-2xl"
                                style={{ backgroundImage: `url("${np.poster}")`, backgroundSize: "cover", backgroundPosition: "center" }}
                            />
                        )}
                        <div className="relative flex items-center gap-3 p-2.5 pr-3">
                            <Link href={href} className="shrink-0">
                                {np.poster ? (
                                    <img src={np.poster} alt="" className="h-14 w-10 rounded-lg object-cover ring-1 ring-white/15" />
                                ) : (
                                    <div className="flex h-14 w-10 items-center justify-center rounded-lg bg-primary/15">
                                        <Sofa className="h-4 w-4 text-primary" />
                                    </div>
                                )}
                            </Link>
                            <Link href={href} className="min-w-0 flex-1">
                                <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                                    {/* Égaliseur animé */}
                                    <span className="flex h-2.5 items-end gap-[2px]">
                                        {[0, 1, 2].map((i) => (
                                            <motion.span
                                                key={i}
                                                className="w-[2px] rounded-full bg-primary"
                                                animate={np.paused ? { height: 3 } : { height: [3, 10, 5, 9, 3] }}
                                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
                                            />
                                        ))}
                                    </span>
                                    {np.paused ? "En pause" : "En lecture"}
                                    {np.kodi ? ` · ${np.kodi}` : ""}
                                </p>
                                <p className="truncate text-sm font-semibold">{np.title}</p>
                                <p className="truncate text-[11px] text-muted-foreground">
                                    {np.subtitle ? `${np.subtitle} · ` : ""}
                                    {formatClock(np.position)} / {formatClock(np.total)}
                                </p>
                            </Link>
                            <div className="flex shrink-0 items-center gap-1">
                                <button
                                    onClick={() => send("playpause")}
                                    className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_0_20px_-2px_hsl(var(--primary)/0.8)] transition-transform hover:scale-105 active:scale-95"
                                    aria-label={np.paused ? "Lecture" : "Pause"}
                                >
                                    {np.paused ? <Play className="h-4 w-4 translate-x-px fill-current" /> : <Pause className="h-4 w-4 fill-current" />}
                                </button>
                                <button
                                    onClick={() => send("stop")}
                                    className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                                    aria-label="Arrêter"
                                >
                                    <Square className="h-3.5 w-3.5 fill-current" />
                                </button>
                            </div>
                        </div>
                        {/* Progression */}
                        <div className="relative h-[3px] bg-white/10">
                            <motion.div
                                className="h-full bg-gradient-to-r from-primary to-brand shadow-[0_0_10px_hsl(var(--primary))]"
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.8, ease: "linear" }}
                            />
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
