"use client";

/**
 * Mini-lecteur flottant (façon app Musique) : apparaît sur toutes les pages
 * dès que Kodi lit quelque chose (sauf Accueil et Salon qui ont déjà leur
 * carte « En lecture »). Lecture/pause, stop, progression, lien vers la fiche.
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
    // Masqué aussi sur la fiche du média en cours (elle a sa propre télécommande).
    const onPlayingSheet = !!np?.media_id && pathname === `/media/${np.media_type}/${np.media_id}`;
    const visible = !!np?.playing && !onPlayingSheet && !HIDDEN_ON.some((p) => pathname.startsWith(p));
    const pct = np?.total ? Math.min(100, ((np.position || 0) / np.total) * 100) : np?.percentage ?? 0;

    const send = (action: "playpause" | "stop") =>
        control.mutate({ action }, { onError: (e) => toast.error("Commande Kodi refusée", { description: e.message }) });

    const href = np?.media_id && np?.media_type ? `/media/${np.media_type}/${np.media_id}` : "/remote";

    return (
        <AnimatePresence>
            {visible && np && (
                // Le positionnement (fixed + centrage) est porté par un conteneur
                // statique : framer-motion réécrit `transform` sur l'élément animé.
                // Mobile : juste au-dessus de la barre d'onglets, comme le
                // mini-lecteur de l'app Musique.
                <div className="pointer-events-none fixed inset-x-2 bottom-[calc(var(--tabbar-h)+env(safe-area-inset-bottom)+0.5rem)] z-40 flex justify-center lg:inset-x-auto lg:bottom-5 lg:right-6">
                    <motion.div
                        initial={{ y: 24, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 24, opacity: 0 }}
                        transition={SPRING_SOFT}
                        className="pointer-events-auto w-full max-w-[440px] lg:w-[380px]"
                    >
                        <div className="material relative overflow-hidden rounded-[14px] border border-white/[0.08] shadow-[0_12px_40px_-8px_rgb(0_0_0/0.7)]">
                            <div className="flex items-center gap-3 p-2 pr-2.5">
                                <Link href={href} className="shrink-0">
                                    {np.poster ? (
                                        <img src={np.poster} alt="" className="h-12 w-8 rounded-[6px] object-cover" />
                                    ) : (
                                        <div className="flex h-12 w-8 items-center justify-center rounded-[6px] bg-white/[0.08]">
                                            <Sofa className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                    )}
                                </Link>
                                <Link href={href} className="min-w-0 flex-1">
                                    <p className="truncate text-[15px] font-medium leading-tight">{np.title}</p>
                                    <p className="truncate text-[12px] text-muted-foreground">
                                        {np.paused ? "En pause" : np.kodi ? `Sur ${np.kodi}` : "En lecture"}
                                        {" · "}
                                        {formatClock(np.position)} / {formatClock(np.total)}
                                    </p>
                                </Link>
                                <button
                                    onClick={() => send("playpause")}
                                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-foreground transition-transform active:scale-90"
                                    aria-label={np.paused ? "Lecture" : "Pause"}
                                >
                                    {np.paused ? <Play className="h-[22px] w-[22px] fill-current" /> : <Pause className="h-[22px] w-[22px] fill-current" />}
                                </button>
                                <button
                                    onClick={() => send("stop")}
                                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground active:scale-90"
                                    aria-label="Arrêter"
                                >
                                    <Square className="h-4 w-4 fill-current" />
                                </button>
                            </div>
                            {/* Progression (filet en bas) */}
                            <div className="absolute inset-x-0 bottom-0 h-[2px] bg-white/10">
                                <motion.div className="h-full bg-foreground/80" animate={{ width: `${pct}%` }} transition={{ duration: 0.8, ease: "linear" }} />
                            </div>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
}
