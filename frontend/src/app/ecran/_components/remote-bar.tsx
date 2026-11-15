"use client";

// Rôle : télécommande tactile (appli Android) : pause, sauts, passer l'intro,
// épisode suivant, et ouverture des feuilles (sous-titres, son, fiche, volume).

import { useState } from "react";
import { AudioLines, ChevronsRight, Info, Loader2, Pause, Play, RotateCcw, RotateCw, SkipForward, Subtitles } from "lucide-react";
import { activeSkip, type Ambient, type AmbientCast, type AmbientPlaying, type PersonFilmography, type RemoteAction } from "@/lib/ambient";
import { u } from "../_lib/units";
import { RemoteButton } from "./remote-button";
import { InfoSheet, SheetFrame, SubtitleTools, TrackSheet, VolumeSheet } from "./remote-sheets";
import { PersonSheet } from "./person-sheet";

/* ── Télécommande tactile (appli Android) ─────────────────────── */

export type Sheet = "subtitles" | "audio" | "info" | "volume" | null;

export function RemoteBar({
    playing,
    position,
    paused,
    onCommand,
    amp,
    loadPerson,
    sheet,
    setSheet,
}: {
    playing: AmbientPlaying;
    position: number;
    paused: boolean;
    onCommand: (command: RemoteAction) => Promise<void>;
    amp: Ambient["amp"];
    loadPerson: (id: number) => Promise<PersonFilmography>;
    sheet: Sheet;
    setSheet: (sheet: Sheet) => void;
}) {
    // Acteur ouvert depuis la fiche : sa filmographie remplace la fiche
    const [person, setPerson] = useState<AmbientCast | null>(null);
    const [busy, setBusy] = useState(false);
    const [failed, setFailed] = useState(false);
    const skip = activeSkip(playing, position);
    // Générique commencé et épisode suivant connu : « Épisode suivant »
    const nextReady = !!playing.next_up && playing.credits_at > 0 && position >= playing.credits_at;

    const run = async (command: RemoteAction) => {
        setBusy(true);
        setFailed(false);
        try {
            await onCommand(command);
        } catch {
            setFailed(true);
        } finally {
            setBusy(false);
        }
    };

    return (
        <>
            {/* Une seule ligne : boutons ronds, seul l'action du moment (intro, suivant) garde son texte */}
            <div className="flex items-center" style={{ gap: u(1.2) }}>
                <RemoteButton label="Reculer de 10 s" caption="10" round onClick={() => run({ action: "seek", value: -10 })}>
                    <RotateCcw style={{ width: u(3.4), height: u(3.4) }} />
                </RemoteButton>
                <RemoteButton label={paused ? "Lecture" : "Pause"} round primary onClick={() => run({ action: "toggle" })}>
                    {busy ? (
                        <Loader2 className="animate-spin" style={{ width: u(4.4), height: u(4.4) }} />
                    ) : paused ? (
                        <Play style={{ width: u(4.4), height: u(4.4) }} />
                    ) : (
                        <Pause style={{ width: u(4.4), height: u(4.4) }} />
                    )}
                </RemoteButton>
                <RemoteButton label="Avancer de 30 s" caption="30" round onClick={() => run({ action: "seek", value: 30 })}>
                    <RotateCw style={{ width: u(3.4), height: u(3.4) }} />
                </RemoteButton>
                {skip && (
                    <RemoteButton label={skip.label} accent onClick={() => run({ action: "skip" })}>
                        <ChevronsRight style={{ width: u(3.8), height: u(3.8) }} />
                    </RemoteButton>
                )}
                {nextReady && (
                    <RemoteButton label="Épisode suivant" accent onClick={() => run({ action: "next" })}>
                        <SkipForward style={{ width: u(3.8), height: u(3.8) }} />
                    </RemoteButton>
                )}
                <span className="flex-1" />
                {(playing.subtitle_tracks.length > 0 || playing.subtitle_tools) && (
                    <RemoteButton label="Sous-titres" round onClick={() => setSheet("subtitles")}>
                        <Subtitles style={{ width: u(3.8), height: u(3.8) }} />
                    </RemoteButton>
                )}
                {playing.audio_tracks.length > 1 && (
                    <RemoteButton label="Son" round onClick={() => setSheet("audio")}>
                        <AudioLines style={{ width: u(3.8), height: u(3.8) }} />
                    </RemoteButton>
                )}
                {(playing.overview || playing.cast.length > 0) && (
                    <RemoteButton label="Fiche" round onClick={() => setSheet("info")}>
                        <Info style={{ width: u(3.8), height: u(3.8) }} />
                    </RemoteButton>
                )}
            </div>
            {failed && (
                <p className="text-amber-300/80" style={{ fontSize: u(2.8) }}>
                    La TV n&apos;a pas répondu : réessaie dans un instant.
                </p>
            )}

            {sheet && (
                <SheetFrame
                    title={
                        sheet === "subtitles"
                            ? "Sous-titres"
                            : sheet === "audio"
                              ? "Son"
                              : sheet === "volume"
                                ? "Volume"
                                : person
                                  ? person.name
                                  : playing.title
                    }
                    onBack={sheet === "info" && person ? () => setPerson(null) : undefined}
                    onClose={() => {
                        setSheet(null);
                        setPerson(null);
                    }}
                >
                    {sheet === "subtitles" && <SubtitleTools playing={playing} run={run} />}
                    {(sheet === "subtitles" || sheet === "audio") && (
                        <TrackSheet
                            tracks={sheet === "subtitles" ? playing.subtitle_tracks : playing.audio_tracks}
                            allowOff={sheet === "subtitles"}
                            onPick={(index) => {
                                void run({ action: "track", value: { type: sheet === "subtitles" ? "text" : "audio", index } });
                                setSheet(null);
                            }}
                        />
                    )}
                    {sheet === "volume" && amp && <VolumeSheet amp={amp} run={run} />}
                    {sheet === "info" &&
                        (person?.tmdb_id ? (
                            <PersonSheet id={person.tmdb_id} loadPerson={loadPerson} />
                        ) : (
                            <InfoSheet playing={playing} onPerson={setPerson} />
                        ))}
                </SheetFrame>
            )}
        </>
    );
}
