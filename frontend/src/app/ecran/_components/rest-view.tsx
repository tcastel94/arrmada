"use client";

// Rôle : affichage au repos (aucun film) : grande horloge, « Ce soir »,
// panneaux À venir / Téléchargements / Ampli et leurs fiches au toucher.

import { useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence } from "framer-motion";
import { hhmm, longDay, type Ambient, type AmbientDownloadDetail, type AmbientPlay, type AmbientUpcoming } from "@/lib/ambient";
import { u } from "../_lib/units";
import { TonightShelf } from "./tonight";
import { AmpPanel, DownloadsPanel, UpcomingPanel } from "./rest-panels";
import { DownloadSheet, UpcomingSheet } from "./detail-sheets";

/* ── Au repos ────────────────────────────────────────────────── */

/** Lancer un titre de « Ce soir » : renvoie la TV qui l'a reçu. */
export type PlayHandler = (play: AmbientPlay) => Promise<{ device: string; online: boolean }>;

/** Fiche ouverte au toucher depuis les panneaux du repos. */
type RestSheet = { kind: "upcoming"; item: AmbientUpcoming } | { kind: "download"; key: string; title: string } | null;

export function RestView({
    now,
    data,
    onPlay,
    loadDownload,
}: {
    now: Date;
    data?: Ambient;
    onPlay: PlayHandler;
    loadDownload: (key: string) => Promise<AmbientDownloadDetail>;
}) {
    const [sheet, setSheet] = useState<RestSheet>(null);
    const room = data?.room_label;
    const amp = data?.amp ?? null;
    const hasPanels = !!data && (data.upcoming.length > 0 || data.downloads.length > 0 || !!amp);
    const tonight = data?.tonight ?? null;
    const hasTonight = !!tonight && (tonight.resume.length > 0 || tonight.watchlist.length > 0 || tonight.fresh.length > 0);
    // « dans le salon » / « dans la salle de cinéma »
    const inRoom = room ? ` dans ${room === "Salle de cinéma" ? "la salle de cinéma" : `le ${room.toLowerCase()}`}` : "";
    return (
        <div className="flex min-h-[100dvh] flex-col justify-between" style={{ padding: u(hasTonight ? 4 : 5), gap: u(hasTonight ? 2.5 : 4) }}>
            <header className="flex items-start justify-between" style={{ gap: u(3) }}>
                <div>
                    {/* Horloge plus petite quand « Ce soir » prend la place */}
                    <p
                        className="font-light leading-[0.85] tracking-tight tabular-nums text-slate-100"
                        style={{ fontSize: u(hasTonight ? 15 : 30) }}
                    >
                        {hhmm(now)}
                    </p>
                    {/* « Samedi 10 octobre » : majuscule au premier mot seulement */}
                    <p className="text-slate-400 first-letter:uppercase" style={{ fontSize: u(hasTonight ? 3.4 : 5), marginTop: u(hasTonight ? 1.4 : 2.5) }}>
                        {longDay(now)}
                    </p>
                </div>
                {room && (
                    <p className="uppercase text-slate-500" style={{ fontSize: u(3), letterSpacing: "0.2em", paddingTop: u(2) }}>
                        {room}
                    </p>
                )}
            </header>

            {hasTonight ? (
                <TonightShelf tonight={tonight} inRoom={inRoom} onPlay={onPlay} />
            ) : (
                <p className="text-slate-500" style={{ fontSize: u(3) }}>
                    Rien en lecture{inRoom}. Lance un film sur la TV : l&apos;heure de fin s&apos;affichera ici en grand.
                </p>
            )}

            {hasPanels && (
                <div className="flex portrait:flex-col" style={{ gap: u(3) }}>
                    {data.upcoming.length > 0 && (
                        <UpcomingPanel upcoming={data.upcoming} now={now} onOpen={(item) => setSheet({ kind: "upcoming", item })} />
                    )}
                    {data.downloads.length > 0 && (
                        <DownloadsPanel
                            downloads={data.downloads}
                            onOpen={(key, title) => setSheet({ kind: "download", key, title })}
                        />
                    )}
                    {amp && <AmpPanel amp={amp} />}
                </div>
            )}

            {/* Fiches au toucher : portail vers <body> (la page est décalée par l'anti-marquage) */}
            {createPortal(
                <AnimatePresence>
                    {sheet?.kind === "upcoming" && <UpcomingSheet key="up" item={sheet.item} now={now} onClose={() => setSheet(null)} />}
                    {sheet?.kind === "download" && (
                        <DownloadSheet key={`dl-${sheet.key}`} downloadKey={sheet.key} title={sheet.title} load={loadDownload} onClose={() => setSheet(null)} />
                    )}
                </AnimatePresence>,
                document.body,
            )}
        </div>
    );
}
