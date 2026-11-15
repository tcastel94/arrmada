"use client";

// Rôle : affichage principal une fois appairé : relève l'état du serveur,
// gère la luminosité et choisit entre la séance (film en cours) et le repos.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { WifiOff } from "lucide-react";
import { useSelfUpdate } from "@/lib/self-update";
import { hasFully, hhmm, type AmbientDownloadDetail, type AmbientPlay, type PersonFilmography, type RemoteAction, type ScreenOptions } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import {
    AFTER_COMMAND_MS,
    AMBIENT_RETRY_DELAY_MS,
    HttpError,
    POLL_MS,
    POLL_PLAYING_MS,
    WAKE_MS,
    fetchAmbient,
    fetchJson,
    sendCommand,
    sendPlay,
    type Auth,
} from "../_lib/api";
import { useBrightness, useNow, usePixelShift, useWakeLock } from "../_lib/hooks";
import { SessionView } from "./session-view";
import { RestView } from "./rest-view";

export function AmbientView({
    auth,
    options,
    onRevoked,
    onLeavePreview,
}: {
    auth: Auth;
    options: ScreenOptions;
    onRevoked: () => void;
    onLeavePreview: () => void;
}) {
    const [room, setRoom] = useState(options.room);
    const { data, error, dataUpdatedAt } = useQuery({
        queryKey: ["ambient", auth.kind, room],
        queryFn: () => fetchAmbient(auth, room),
        refetchInterval: (query) => (query.state.data?.playing ? POLL_PLAYING_MS : POLL_MS),
        refetchIntervalInBackground: true,
        // Un nouvel essai avant « Hors ligne » (pas pour un jeton refusé : 401 / 403)
        retry: (failures, err) => failures < 1 && !(err instanceof HttpError && (err.status === 401 || err.status === 403)),
        retryDelay: AMBIENT_RETRY_DELAY_MS,
        // Une panne réseau garde le dernier affichage (avec un petit avertissement)
        placeholderData: (previous) => previous,
    });

    // Jeton révoqué dans la web app (401) → retour à l'appairage. Un 403
    // (adresse hors réseau local) ne doit pas effacer le jeton : on attend.
    useEffect(() => {
        if (error instanceof HttpError && error.status === 401 && auth.kind === "screen") onRevoked();
    }, [error, auth.kind, onRevoked]);

    // Page ouverte en permanence : se recharge après une mise à jour
    // d'ArrMada, ou si l'API reste injoignable (ancienne version en mémoire,
    // adresse changée…). Un 401/403 n'est pas une panne : rien à recharger.
    useSelfUpdate(dataUpdatedAt, !(error instanceof HttpError && (error.status === 401 || error.status === 403)));

    // Télécommande : envoi, puis relecture rapide de l'état renvoyé par la TV
    const queryClient = useQueryClient();
    const loadPerson = useCallback((id: number) => fetchJson<PersonFilmography>(auth, `/api/ambient/person/${id}`), [auth]);
    const loadDownload = useCallback(
        (key: string) => fetchJson<AmbientDownloadDetail>(auth, `/api/ambient/download/${encodeURIComponent(key)}`),
        [auth],
    );
    const onCommand = useCallback(
        async (command: RemoteAction) => {
            await sendCommand(auth, room, command);
            setTimeout(() => queryClient.invalidateQueries({ queryKey: ["ambient", auth.kind, room] }), AFTER_COMMAND_MS);
        },
        [auth, room, queryClient],
    );

    // « Ce soir » : lancé sur la TV, puis relecture (l'écran passera en mode séance)
    const onPlay = useCallback(
        async (play: AmbientPlay) => {
            const sent = await sendPlay(auth, room, play);
            setTimeout(() => queryClient.invalidateQueries({ queryKey: ["ambient", auth.kind, room] }), 4_000);
            return sent;
        },
        [auth, room, queryClient],
    );

    // Écart d'horloge tablette ↔ serveur, mesuré à chaque réponse
    const offset = useMemo(() => (data ? data.server_time - dataUpdatedAt / 1000 : 0), [data, dataUpdatedAt]);

    const now = useNow();
    const playing = data?.playing ?? null;
    const inSession = !!playing;

    // Toucher l'écran : plein affichage quelques secondes
    const [awakeUntil, setAwakeUntil] = useState(0);
    const awake = now.getTime() < awakeUntil;
    const dimmed = inSession && !awake;

    // Avec Fully, c'est le rétroéclairage qui baisse : le texte reste net.
    // Sans Fully (Chrome, aperçu sur PC), seule la page peut s'assombrir.
    const [fully] = useState(() => hasFully());

    // Rien tant que la 1re réponse n'est pas là : recharger la page pendant
    // un film ne doit pas faire flasher l'écran à la luminosité de repos.
    useBrightness(data ? (dimmed ? options.dim : options.rest) : null);
    useWakeLock();
    const shift = usePixelShift();

    return (
        <div
            // --u : l'unité d'écran (voir plus haut), selon l'orientation
            className="relative min-h-full w-full landscape:[--u:min(1vh,0.625vw)] portrait:[--u:min(0.625vh,1vw)]"
            onPointerDown={() => setAwakeUntil(Date.now() + WAKE_MS)}
            style={{ transform: `translate(${shift.x}px, ${shift.y}px)`, transition: "transform 4s ease-in-out" }}
        >
            {/* Fond : image du film, très sombre et floue (rien pendant le repos) */}
            <AnimatePresence>
                {playing?.fanart && (
                    <motion.div
                        key={playing.fanart}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: dimmed ? 0.08 : 0.18 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 1.5 }}
                        className="pointer-events-none fixed inset-0 bg-cover bg-center blur-md"
                        style={{ backgroundImage: `url(${playing.fanart})` }}
                    />
                )}
            </AnimatePresence>
            <div className="pointer-events-none fixed inset-0 bg-gradient-to-t from-black via-black/75 to-black/50" />

            {/* Contenu : assombri en mode séance (en plus du rétroéclairage) */}
            <div
                className={cn(
                    "relative transition-[opacity,filter] duration-1000",
                    !dimmed ? "opacity-100" : fully ? "opacity-90" : "opacity-60 [filter:saturate(0.6)]",
                )}
            >
                {playing ? (
                    <SessionView
                        playing={playing}
                        now={now}
                        offset={offset}
                        amp={data?.amp ?? null}
                        onCommand={onCommand}
                        loadPerson={loadPerson}
                    />
                ) : (
                    <RestView now={now} data={data} onPlay={onPlay} loadDownload={loadDownload} />
                )}
            </div>

            {/* Bandeaux discrets (en bas, loin de l'heure) : hors ligne, aperçu */}
            <div className="absolute bottom-3 right-3 flex items-center gap-2 text-xs">
                {error && !(error instanceof HttpError && error.status === 401) && (
                    <span className="flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-amber-300/80">
                        <WifiOff className="h-3.5 w-3.5" />
                        Hors ligne{data ? ` · données de ${hhmm(new Date(dataUpdatedAt))}` : ""}
                    </span>
                )}
                {auth.kind === "admin" && (
                    <span className="flex items-center gap-1 rounded-full bg-white/5 px-1 py-1 text-slate-400">
                        <span className="px-1.5">Aperçu</span>
                        {(["salon", "cinema", "bureau"] as const).map((r) => (
                            <button
                                key={r}
                                type="button"
                                onClick={() => setRoom(r)}
                                className={cn("rounded-full px-2 py-0.5", room === r ? "bg-[#4A9EFF]/20 text-[#8CC4FF]" : "hover:text-slate-200")}
                            >
                                {r === "salon" ? "Salon" : r === "cinema" ? "Cinéma" : "Bureau"}
                            </button>
                        ))}
                        <button type="button" onClick={onLeavePreview} className="rounded-full px-2 py-0.5 hover:text-slate-200">
                            Quitter
                        </button>
                    </span>
                )}
            </div>
        </div>
    );
}
