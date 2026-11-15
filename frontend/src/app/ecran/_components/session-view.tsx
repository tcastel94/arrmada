"use client";

// Rôle : affichage pendant un film : affiche, heure de fin en grand, début,
// temps restant, barre de progression et télécommande.

import { useState } from "react";
import { motion } from "framer-motion";
import { Pause, Volume2, VolumeX } from "lucide-react";
import { hhmm, remainingLabel, sessionAt, untilCredits, type Ambient, type AmbientPlaying, type PersonFilmography, type RemoteAction } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { u } from "../_lib/units";
import { RemoteBar, type Sheet } from "./remote-bar";
import { SheetFrame, VolumeSheet } from "./remote-sheets";

/* ── Pendant une lecture ─────────────────────────────────────── */

export function SessionView({
    playing,
    now,
    offset,
    amp,
    onCommand,
    loadPerson,
}: {
    playing: AmbientPlaying;
    now: Date;
    offset: number;
    amp: Ambient["amp"];
    onCommand: (command: RemoteAction) => Promise<void>;
    loadPerson: (id: number) => Promise<PersonFilmography>;
}) {
    const session = sessionAt(playing, now.getTime(), offset);
    // Feuille ouverte (sous-titres, son, fiche, volume) : ici, car le volume
    // s'ouvre depuis le bandeau du haut et le reste depuis la télécommande
    const [sheet, setSheet] = useState<Sheet>(null);
    const status = session.paused ? "En pause" : playing.kind === "episode" ? "Épisode en cours" : "Film en cours";
    const badges = [playing.video, playing.audio, playing.subtitle_track ? `Sous-titres ${playing.subtitle_track}` : ""].filter(Boolean);
    const credits = untilCredits(playing, session.position);
    // Appli Android : badges, détails et télécommande en plus → tout resserré
    // pour tenir sur un écran de tablette en paysage
    const compact = playing.remote;
    const details = [
        playing.chapter ? `Chapitre : ${playing.chapter}` : "",
        credits !== null ? `Générique dans ${remainingLabel(credits)}` : "",
        playing.next_up ? `Ensuite : ${playing.next_up}` : "",
    ].filter(Boolean);
    return (
        <motion.section
            key={`${playing.title}-${playing.subtitle}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8 }}
            // Paysage (tablette sous la TV) : affiche à gauche, heures à droite.
            // Portrait ou téléphone : l'un sous l'autre.
            className="flex min-h-[100dvh] portrait:flex-col landscape:flex-row"
            style={{ padding: u(4), gap: u(5) }}
        >
            {playing.poster && (
                // Paysage : affiche sur presque toute la hauteur (88 u = 704 px sur
                // la tablette). Portrait : moins haute, les heures passent dessous.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={playing.poster}
                    alt=""
                    className="aspect-[2/3] shrink-0 self-center object-cover shadow-2xl shadow-black landscape:h-[calc(var(--u)*88)] portrait:h-[calc(var(--u)*60)]"
                    style={{ borderRadius: u(1.6) }}
                />
            )}

            <div className="flex min-w-0 flex-1 flex-col justify-between" style={{ gap: u(compact ? 1.6 : 2.5) }}>
                {/* Bandeau : état de la lecture, volume de l'ampli, heure */}
                <div className="flex items-center justify-between" style={{ gap: u(3) }}>
                    <p
                        className={cn("flex items-center font-medium uppercase", session.paused ? "text-amber-300" : "text-slate-400")}
                        style={{ fontSize: u(3.4), gap: u(1.2), letterSpacing: "0.14em" }}
                    >
                        {session.paused ? (
                            <Pause style={{ width: u(3.4), height: u(3.4) }} />
                        ) : (
                            <span className="rounded-full bg-[#4A9EFF]" style={{ width: u(1.6), height: u(1.6) }} />
                        )}
                        {status}
                    </p>
                    <div className="flex items-center tabular-nums" style={{ gap: u(3.5) }}>
                        {amp?.power === "on" && (
                            // Toucher le volume : réglage de l'ampli de la pièce
                            <button
                                type="button"
                                onClick={() => setSheet("volume")}
                                className="flex items-center rounded-full text-slate-300 transition-colors hover:bg-white/[0.08] active:scale-95"
                                style={{ fontSize: u(3.8), gap: u(1), padding: `${u(0.8)} ${u(2)}`, background: "rgba(255,255,255,0.05)" }}
                                aria-label="Régler le volume"
                            >
                                {amp.mute ? (
                                    <VolumeX className="text-amber-300" style={{ width: u(4), height: u(4) }} />
                                ) : (
                                    <Volume2 style={{ width: u(4), height: u(4) }} />
                                )}
                                {amp.volume_pct ?? "—"} %
                            </button>
                        )}
                        <span className="leading-none text-slate-200" style={{ fontSize: u(6.5) }}>
                            {hhmm(now)}
                        </span>
                    </div>
                </div>

                {/* Titre (2 lignes au plus) et épisode ou année */}
                <div>
                    <h1
                        className={cn("font-semibold leading-[1.05] text-white", compact ? "line-clamp-1" : "line-clamp-2")}
                        style={{ fontSize: u(compact ? 7 : 8) }}
                    >
                        {playing.title}
                    </h1>
                    {playing.subtitle && (
                        <p className="truncate text-slate-400" style={{ fontSize: u(compact ? 4 : 4.6), marginTop: u(1) }}>
                            {playing.subtitle}
                        </p>
                    )}
                    {/* Formats de la séance (appli Android) : image, son, sous-titres, sur une ligne */}
                    {badges.length > 0 && (
                        <div className="flex flex-nowrap overflow-hidden" style={{ gap: u(1.2), marginTop: u(1.4) }}>
                            {badges.map((badge) => (
                                <span
                                    key={badge}
                                    className="shrink-0 truncate rounded-full border border-white/10 bg-white/[0.06] text-slate-300"
                                    style={{ fontSize: u(2.7), padding: `${u(0.5)} ${u(1.8)}` }}
                                >
                                    {badge}
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                {/* L'heure de fin : l'info principale, donc la plus grosse */}
                <div>
                    <p className="font-medium uppercase text-slate-400" style={{ fontSize: u(3.6), letterSpacing: "0.14em" }}>
                        {session.paused ? "Fin si reprise maintenant" : "Fin prévue"}
                    </p>
                    <p
                        className={cn("font-medium leading-[0.9] tracking-tight tabular-nums", session.paused ? "text-amber-200" : "text-[#8CC4FF]")}
                        style={{ fontSize: u(compact ? 20 : 26) }}
                    >
                        {hhmm(session.endsAt)}
                    </p>
                </div>

                {/* Début et temps restant */}
                <div className="flex flex-wrap" style={{ columnGap: u(9), rowGap: u(2) }}>
                    <BigFigure label="Début" value={hhmm(session.startedAt)} size={compact ? 8 : 11} />
                    <BigFigure label="Reste" value={session.endsAt ? remainingLabel(session.remaining) : "—"} size={compact ? 8 : 11} />
                </div>

                {session.endsAt && (
                    <div className="overflow-hidden rounded-full bg-white/15" style={{ height: u(1.8) }}>
                        <div
                            className={cn(
                                "h-full rounded-full transition-[width] duration-1000 ease-linear",
                                session.paused ? "bg-amber-300/70" : "bg-[#4A9EFF]",
                            )}
                            style={{ width: `${(session.progress * 100).toFixed(2)}%` }}
                        />
                    </div>
                )}

                {/* Chapitre, générique, épisode suivant */}
                {details.length > 0 && (
                    <p className="truncate text-slate-400" style={{ fontSize: u(3.2) }}>
                        {details.join("   ·   ")}
                    </p>
                )}

                {playing.remote && (
                    <RemoteBar
                        playing={playing}
                        position={session.position}
                        paused={session.paused}
                        onCommand={onCommand}
                        amp={amp}
                        loadPerson={loadPerson}
                        sheet={sheet}
                        setSheet={setSheet}
                    />
                )}
                {/* TV sous Kodi (pas de télécommande) : le volume reste réglable */}
                {!playing.remote && sheet === "volume" && amp && (
                    <SheetFrame title="Volume" onClose={() => setSheet(null)}>
                        <VolumeSheet amp={amp} run={onCommand} />
                    </SheetFrame>
                )}
            </div>
        </motion.section>
    );
}

function BigFigure({ label, value, size = 11 }: { label: string; value: string; size?: number }) {
    return (
        <div className="min-w-0">
            <p className="font-medium uppercase text-slate-400" style={{ fontSize: u(3.2), letterSpacing: "0.14em" }}>
                {label}
            </p>
            <p className="leading-none tabular-nums text-slate-100" style={{ fontSize: u(size), marginTop: u(0.8) }}>
                {value}
            </p>
        </div>
    );
}
