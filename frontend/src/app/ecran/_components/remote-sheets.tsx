"use client";

// Rôle : feuilles qui montent du bas pendant un film : volume de l'ampli,
// outils et pistes de sous-titres, pistes son, fiche du titre (distribution).

import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, Download, Loader2, Minus, Plus, RefreshCw, Volume2, VolumeX, X } from "lucide-react";
import { prettyName, shiftLabel, type Ambient, type AmbientCast, type AmbientPlaying, type AmbientTrack, type RemoteAction } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { u } from "../_lib/units";
import { RemoteButton } from "./remote-button";

/** Feuille qui monte du bas de l'écran ; toucher à côté la ferme. */
export function SheetFrame({
    title,
    onClose,
    onBack,
    children,
}: {
    title: string;
    onClose: () => void;
    onBack?: () => void;
    children: React.ReactNode;
}) {
    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-20 flex items-end justify-center bg-black/80 backdrop-blur-sm"
                onClick={onClose}
            >
                <motion.div
                    initial={{ y: 40 }}
                    animate={{ y: 0 }}
                    exit={{ y: 40 }}
                    className="w-full max-w-[min(100%,calc(var(--u)*150))] overflow-y-auto border border-white/10 bg-[#0d1117]"
                    style={{ maxHeight: "85dvh", padding: u(4), borderRadius: `${u(3)} ${u(3)} 0 0` }}
                    onClick={(event) => event.stopPropagation()}
                >
                    <div className="flex items-center justify-between" style={{ marginBottom: u(2.5), gap: u(2) }}>
                        <div className="flex min-w-0 items-center" style={{ gap: u(1.5) }}>
                            {onBack && (
                                <button type="button" onClick={onBack} className="rounded-full p-2 text-slate-400 hover:bg-white/10" aria-label="Retour à la fiche">
                                    <ChevronLeft style={{ width: u(4.4), height: u(4.4) }} />
                                </button>
                            )}
                            <p className="truncate font-semibold text-white" style={{ fontSize: u(4.4) }}>
                                {title}
                            </p>
                        </div>
                        <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-white/10" aria-label="Fermer">
                            <X style={{ width: u(4.4), height: u(4.4) }} />
                        </button>
                    </div>
                    {children}
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

/** Volume de l'ampli de la pièce : gros boutons, sourdine. Le serveur pilote l'ampli. */
export function VolumeSheet({ amp, run }: { amp: NonNullable<Ambient["amp"]>; run: (command: RemoteAction) => Promise<void> }) {
    const big = { width: u(16), height: u(16) };
    return (
        <div className="flex flex-col items-center" style={{ gap: u(3), paddingBottom: u(2) }}>
            <div className="flex items-center" style={{ gap: u(5) }}>
                <button
                    type="button"
                    onClick={() => run({ action: "volume_step", value: -3 })}
                    className="flex items-center justify-center rounded-full bg-white/[0.07] text-slate-100 active:scale-95"
                    style={big}
                    aria-label="Baisser le volume"
                >
                    <Minus style={{ width: u(6), height: u(6) }} />
                </button>
                <p className="tabular-nums text-white" style={{ fontSize: u(14), minWidth: u(30), textAlign: "center" }}>
                    {amp.volume_pct ?? "—"}
                    <span className="text-slate-500" style={{ fontSize: u(5) }}>
                        {" "}
                        %
                    </span>
                </p>
                <button
                    type="button"
                    onClick={() => run({ action: "volume_step", value: 3 })}
                    className="flex items-center justify-center rounded-full bg-[#4A9EFF] text-[#0b1220] active:scale-95"
                    style={big}
                    aria-label="Monter le volume"
                >
                    <Plus style={{ width: u(6), height: u(6) }} />
                </button>
            </div>
            <RemoteButton label={amp.mute ? "Remettre le son" : "Couper le son"} accent={amp.mute} onClick={() => run({ action: "mute", value: !amp.mute })}>
                {amp.mute ? <Volume2 style={{ width: u(3.8), height: u(3.8) }} /> : <VolumeX style={{ width: u(3.8), height: u(3.8) }} />}
            </RemoteButton>
            <p className="text-slate-500" style={{ fontSize: u(2.6) }}>
                {amp.name}
                {amp.sound_program ? ` · ${prettyName(amp.sound_program)}` : ""}
            </p>
        </div>
    );
}

/**
 * Outils de la feuille Sous-titres : Bazarr (télécharger les sous-titres FR,
 * les recaler sur le son) et décalage manuel −/+ 0,5 s de la piste affichée.
 * La TV fait le travail et renvoie l'état (en cours, résultat, décalage).
 */
export function SubtitleTools({ playing, run }: { playing: AmbientPlaying; run: (command: RemoteAction) => Promise<void> }) {
    const busy = playing.subtitle_busy;
    const shift = playing.subtitle_shift_ms;
    return (
        <div className="flex flex-col" style={{ gap: u(1.6), marginBottom: u(3) }}>
            <div className="flex flex-wrap items-center" style={{ gap: u(1.2) }}>
                {playing.subtitle_tools && (
                    <>
                        <RemoteButton label={busy ? "Bazarr…" : "Sous-titres FR"} onClick={() => !busy && run({ action: "subtitle_download" })}>
                            {busy ? <Loader2 className="animate-spin" style={{ width: u(3.6), height: u(3.6) }} /> : <Download style={{ width: u(3.6), height: u(3.6) }} />}
                        </RemoteButton>
                        <RemoteButton label="Resynchro auto" onClick={() => !busy && run({ action: "subtitle_sync" })}>
                            <RefreshCw style={{ width: u(3.6), height: u(3.6) }} />
                        </RemoteButton>
                    </>
                )}
                <span className="flex-1" />
                <RemoteButton label="0,5 s plus tôt" onClick={() => run({ action: "subtitle_shift", value: -500 })}>
                    <Minus style={{ width: u(3.6), height: u(3.6) }} />
                </RemoteButton>
                <span className="tabular-nums text-slate-300" style={{ fontSize: u(3), minWidth: u(12), textAlign: "center" }}>
                    {shift === 0 ? "0 s" : shiftLabel(shift)}
                </span>
                <RemoteButton label="0,5 s plus tard" onClick={() => run({ action: "subtitle_shift", value: 500 })}>
                    <Plus style={{ width: u(3.6), height: u(3.6) }} />
                </RemoteButton>
            </div>
            <p className="text-slate-500" style={{ fontSize: u(2.6) }}>
                {playing.subtitle_note ||
                    "Resynchro auto : Bazarr recale le fichier sur le son. Décalage apparu en plein film : − / + 0,5 s (− = plus tôt)."}
            </p>
        </div>
    );
}

export function TrackSheet({ tracks, allowOff, onPick }: { tracks: AmbientTrack[]; allowOff: boolean; onPick: (index: number) => void }) {
    const none = !tracks.some((t) => t.selected);
    const rows: { index: number; label: string; detail: string; selected: boolean }[] = [
        ...(allowOff ? [{ index: -1, label: "Aucun", detail: "Sous-titres désactivés", selected: none }] : []),
        ...tracks,
    ];
    return (
        <ul className="flex flex-col" style={{ gap: u(1.2) }}>
            {rows.map((track) => (
                <li key={track.index}>
                    <button
                        type="button"
                        onClick={() => onPick(track.index)}
                        className={cn(
                            "flex w-full items-center justify-between text-left transition-colors",
                            track.selected ? "bg-[#4A9EFF]/15 ring-1 ring-[#4A9EFF]/50" : "bg-white/[0.04] hover:bg-white/[0.08]",
                        )}
                        style={{ padding: `${u(2)} ${u(2.8)}`, borderRadius: u(1.6), gap: u(2) }}
                    >
                        <span className="min-w-0">
                            <span className="block truncate text-slate-100" style={{ fontSize: u(3.4) }}>
                                {track.label}
                            </span>
                            {track.detail && (
                                <span className="block truncate text-slate-500" style={{ fontSize: u(2.7) }}>
                                    {track.detail}
                                </span>
                            )}
                        </span>
                        {track.selected && <span className="shrink-0 rounded-full bg-[#4A9EFF]" style={{ width: u(1.6), height: u(1.6) }} />}
                    </button>
                </li>
            ))}
        </ul>
    );
}

export function InfoSheet({ playing, onPerson }: { playing: AmbientPlaying; onPerson: (person: AmbientCast) => void }) {
    return (
        <div className="flex flex-col" style={{ gap: u(3) }}>
            {playing.meta_line && (
                <p className="text-slate-400" style={{ fontSize: u(3) }}>
                    {playing.meta_line}
                </p>
            )}
            {playing.overview && (
                <p className="leading-relaxed text-slate-200" style={{ fontSize: u(3.4) }}>
                    {playing.overview}
                </p>
            )}
            {playing.cast.length > 0 && (
                <ul className="grid grid-cols-4 portrait:grid-cols-3" style={{ gap: u(2.5) }}>
                    {playing.cast.map((person) => (
                        <li
                            key={`${person.name}-${person.character}`}
                            // Toucher un acteur (film) : sa filmographie, médiathèque en tête
                            onClick={person.tmdb_id ? () => onPerson(person) : undefined}
                            className={cn(
                                "flex flex-col items-center rounded-xl text-center",
                                person.tmdb_id && "cursor-pointer transition-colors hover:bg-white/[0.05] active:scale-95",
                            )}
                            style={{ gap: u(0.8), padding: u(1) }}
                        >
                            {person.photo ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={person.photo} alt="" className="rounded-full object-cover object-top" style={{ width: u(14), height: u(14) }} />
                            ) : (
                                <span className="rounded-full bg-white/10" style={{ width: u(14), height: u(14) }} />
                            )}
                            <span className="w-full truncate text-slate-100" style={{ fontSize: u(2.8) }}>
                                {person.name}
                            </span>
                            {person.character && (
                                <span className="w-full truncate text-slate-500" style={{ fontSize: u(2.5) }}>
                                    {person.character}
                                </span>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
