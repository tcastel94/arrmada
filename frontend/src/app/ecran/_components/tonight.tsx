"use client";

// Rôle : rangée « Ce soir » (reprendre, Ma liste, nouveaux films) et
// confirmation avant de lancer un titre sur la TV de la pièce.

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Play, Popcorn } from "lucide-react";
import type { Ambient, AmbientTile } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { u } from "../_lib/units";
import type { PlayHandler } from "./rest-view";

/* ── « Ce soir » : choisir quoi regarder, le lancer sur la TV ─── */

const TONIGHT_TABS = [
    { key: "resume", label: "Reprendre" },
    { key: "watchlist", label: "Ma liste" },
    { key: "fresh", label: "Nouveaux films" },
] as const;
type TonightKey = (typeof TONIGHT_TABS)[number]["key"];

export function TonightShelf({ tonight, inRoom, onPlay }: { tonight: NonNullable<Ambient["tonight"]>; inRoom: string; onPlay: PlayHandler }) {
    // Une seule rangée à la fois (lisible depuis le canapé) : onglets, et
    // seulement ceux qui ont quelque chose à proposer
    const tabs = TONIGHT_TABS.filter((tab) => tonight[tab.key].length > 0);
    const [picked, setPicked] = useState<TonightKey | null>(null);
    const active = tabs.find((tab) => tab.key === picked)?.key ?? tabs[0]?.key;
    const [chosen, setChosen] = useState<AmbientTile | null>(null);
    if (!active) return null;
    return (
        <section className="flex min-h-0 flex-col" style={{ gap: u(1.8) }}>
            <div className="flex items-center" style={{ gap: u(1.2) }}>
                <p className="flex items-center text-slate-300" style={{ fontSize: u(3.4), gap: u(1.2), marginRight: u(1.5) }}>
                    <Popcorn style={{ width: u(3.6), height: u(3.6) }} className="text-[#4A9EFF]" />
                    Ce soir
                </p>
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        type="button"
                        onClick={() => setPicked(tab.key)}
                        className={cn(
                            "rounded-full transition-colors duration-200",
                            tab.key === active ? "bg-white text-black" : "bg-white/[0.08] text-slate-300 active:bg-white/[0.15]",
                        )}
                        style={{ fontSize: u(2.6), padding: `${u(0.9)} ${u(2.4)}` }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>
            {/* Défilement horizontal au doigt ; « snap » : les affiches s'alignent au bord */}
            <div
                key={active}
                className="flex snap-x snap-mandatory overflow-x-auto overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                style={{ gap: u(2.4), scrollPaddingLeft: 0 }}
            >
                {tonight[active].map((tile, i) => (
                    <TonightTile key={`${tile.title}-${tile.subtitle}-${i}`} tile={tile} index={i} onPick={() => setChosen(tile)} />
                ))}
            </div>
            {/* Portail vers <body> : la page entière est décalée de quelques pixels
                (anti-marquage, `transform`), ce qui casserait le « plein écran » fixe */}
            {createPortal(
                <AnimatePresence>
                    {chosen && <LaunchSheet tile={chosen} inRoom={inRoom} onPlay={onPlay} onClose={() => setChosen(null)} />}
                </AnimatePresence>,
                document.body,
            )}
        </section>
    );
}

function TonightTile({ tile, index, onPick }: { tile: AmbientTile; index: number; onPick: () => void }) {
    return (
        <motion.button
            type="button"
            onClick={onPick}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: Math.min(index, 6) * 0.04, ease: [0.22, 1, 0.36, 1] }}
            whileTap={{ scale: 0.96 }}
            className="shrink-0 snap-start text-left"
            style={{ width: u(15) }}
        >
            <div className="relative overflow-hidden bg-white/[0.06]" style={{ aspectRatio: "2 / 3", borderRadius: u(1.6) }}>
                {tile.poster ? (
                    // eslint-disable-next-line @next/next/no-img-element -- affiches distantes (Radarr / TMDB), pas d'optimisation Next ici
                    <img src={tile.poster} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
                ) : (
                    <div className="absolute inset-0 flex items-center justify-center p-3 text-center text-slate-300" style={{ fontSize: u(2.6) }}>
                        {tile.title}
                    </div>
                )}
                {tile.progress !== null && (
                    <div className="absolute inset-x-0 bottom-0 bg-black/50" style={{ height: u(0.7) }}>
                        <div className="h-full bg-[#4A9EFF]" style={{ width: `${tile.progress}%` }} />
                    </div>
                )}
            </div>
            <p className="truncate text-slate-200" style={{ fontSize: u(2.4), marginTop: u(1) }}>
                {tile.title}
            </p>
            <p className="truncate text-slate-500" style={{ fontSize: u(2.1) }}>
                {tile.subtitle}
            </p>
        </motion.button>
    );
}

/**
 * Confirmation avant de lancer : un enfant qui tapote la tablette ne doit
 * pas déclencher un film. Un toucher en dehors annule.
 */
function LaunchSheet({ tile, inRoom, onPlay, onClose }: { tile: AmbientTile; inRoom: string; onPlay: PlayHandler; onClose: () => void }) {
    const [state, setState] = useState<{ kind: "idle" | "sending" | "sent" | "error"; text?: string }>({ kind: "idle" });

    // Envoyé : la fenêtre se ferme seule après un court message
    useEffect(() => {
        if (state.kind !== "sent") return;
        const timer = setTimeout(onClose, 2_500);
        return () => clearTimeout(timer);
    }, [state.kind, onClose]);

    const launch = async () => {
        if (!tile.play || state.kind === "sending") return;
        setState({ kind: "sending" });
        try {
            const sent = await onPlay(tile.play);
            setState({
                kind: "sent",
                text: sent.online ? `Lancement sur ${sent.device}…` : `${sent.device} semble éteinte : allume-la, la demande attend 2 min.`,
            });
        } catch (err) {
            setState({ kind: "error", text: err instanceof Error ? err.message : "Envoi impossible" });
        }
    };

    const what = tile.kind === "episode" ? `${tile.title} · ${tile.subtitle}` : tile.title;
    return (
        <motion.div
            // Rendue hors de la page (portail) : l'unité --u y est redéclarée
            className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm landscape:[--u:min(1vh,0.625vw)] portrait:[--u:min(0.625vh,1vw)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
        >
            <motion.div
                className="relative w-full overflow-hidden bg-[#1C1C1E]"
                style={{ maxWidth: u(110), margin: u(4), borderRadius: u(3) }}
                initial={{ y: 40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 40, opacity: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
                onClick={(event) => event.stopPropagation()}
            >
                {tile.fanart && (
                    <div className="absolute inset-0 bg-cover bg-center opacity-25" style={{ backgroundImage: `url(${tile.fanart})` }} />
                )}
                <div className="relative flex items-center" style={{ padding: u(4), gap: u(4) }}>
                    {tile.poster && (
                        // eslint-disable-next-line @next/next/no-img-element -- affiche distante
                        <img src={tile.poster} alt="" className="shrink-0 object-cover" style={{ width: u(16), aspectRatio: "2 / 3", borderRadius: u(1.4) }} />
                    )}
                    <div className="min-w-0 flex-1">
                        <p className="text-slate-400" style={{ fontSize: u(2.6) }}>
                            {tile.play ? (tile.play.resume && tile.progress ? `Reprendre sur la TV${inRoom}` : `Lancer sur la TV${inRoom}`) : "Ma liste"}
                        </p>
                        <p className="font-semibold text-white" style={{ fontSize: u(4.4), lineHeight: 1.15, marginTop: u(0.8) }}>
                            {what}
                        </p>
                        {!tile.play && (
                            <p className="text-slate-400" style={{ fontSize: u(2.8), marginTop: u(1.4) }}>
                                Série pas encore commencée : choisis l&apos;épisode depuis la TV.
                            </p>
                        )}
                        {state.text && (
                            <p
                                className={state.kind === "error" ? "text-[#FF6961]" : "text-[#8CC4FF]"}
                                style={{ fontSize: u(2.8), marginTop: u(1.4) }}
                            >
                                {state.text}
                            </p>
                        )}
                        <div className="flex" style={{ gap: u(2), marginTop: u(3) }}>
                            {tile.play && state.kind !== "sent" && (
                                <button
                                    type="button"
                                    onClick={launch}
                                    disabled={state.kind === "sending"}
                                    className="flex items-center rounded-full bg-[#4A9EFF] font-semibold text-white transition-opacity active:opacity-80 disabled:opacity-60"
                                    style={{ fontSize: u(3), padding: `${u(1.6)} ${u(4)}`, gap: u(1.2) }}
                                >
                                    {state.kind === "sending" ? (
                                        <Loader2 className="animate-spin" style={{ width: u(3.2), height: u(3.2) }} />
                                    ) : (
                                        <Play className="fill-current" style={{ width: u(3.2), height: u(3.2) }} />
                                    )}
                                    {tile.play.resume && tile.progress ? "Reprendre" : "Lancer"}
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={onClose}
                                className="rounded-full bg-white/[0.1] text-slate-200 active:bg-white/[0.18]"
                                style={{ fontSize: u(3), padding: `${u(1.6)} ${u(4)}` }}
                            >
                                {state.kind === "sent" || !tile.play ? "Fermer" : "Annuler"}
                            </button>
                        </div>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
}
