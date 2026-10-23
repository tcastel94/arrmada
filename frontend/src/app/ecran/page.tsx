"use client";

/**
 * Écran d'appoint du salon — la tablette posée sous la TV.
 * ----------------------------------------------------------------
 * Affiche, sans gêner le film, en grand (lu depuis le canapé, à 3-4 m) :
 *  - pendant une lecture : l'affiche sur toute la hauteur, l'heure de FIN
 *    prévue en très grand, l'heure de DÉBUT, le temps restant, la barre de
 *    progression, le titre, l'heure et le volume de l'ampli ; avec l'appli
 *    Android en plus : formats (4K, Dolby Vision, Atmos), pistes, chapitre,
 *    générique et épisode suivant, fiche (résumé, distribution) et une
 *    TÉLÉCOMMANDE TACTILE (pause, −10 s / +30 s, passer l'intro, pistes) ;
 *  - au repos : une grande horloge, « Ce soir » (reprendre, Ma liste,
 *    nouveaux films : un toucher → confirmation → lancé sur la TV de la
 *    pièce), les sorties de ce soir / demain, les téléchargements en cours
 *    et l'ampli de la pièce.
 *
 * Trois états, comme une petite machine à états :
 *  1. « appairage » : pas encore de jeton → code + QR code à valider depuis
 *     le téléphone (Réglages → Kodi → Appareils), comme pour une TV ;
 *  2. « affichage » : jeton « écran » (GET /api/ambient, relevé toutes les
 *     10 s, 5 s pendant une lecture ; et POST /api/ambient/command pour la
 *     télécommande de la lecture en cours de sa pièce) ;
 *  3. « aperçu » : depuis un PC où l'on est connecté en admin, pour régler
 *     l'affichage sans appairer (bouton sur l'écran d'appairage).
 *
 * Luminosité (« mode séance ») : pendant une lecture, la page s'assombrit
 * et, dans Fully Kiosk, baisse le rétroéclairage (`?seance=6`, 0-255) ; au
 * repos elle remonte (`?repos=40`). Toucher l'écran rallume 20 s.
 *
 * Pourquoi pas de réglage dans Kodi : la lecture en cours vient du suivi
 * que l'add-on envoie déjà au serveur (aucun serveur web Kodi à ouvrir).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
    AudioLines,
    CalendarClock,
    ChevronLeft,
    ChevronsRight,
    Download,
    Info,
    Loader2,
    Minus,
    Pause,
    Play,
    Plus,
    Popcorn,
    RefreshCw,
    RotateCcw,
    RotateCw,
    SkipForward,
    Speaker,
    Subtitles,
    Volume2,
    VolumeX,
    WifiOff,
    X,
} from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { API_URL } from "@/lib/constants";
import { getToken } from "@/lib/api-client";
import {
    activeSkip,
    getScreenToken,
    shiftLabel,
    hasFully,
    hhmm,
    longDay,
    platformName,
    prettyName,
    readOptions,
    releaseTypeLabel,
    releaseWhen,
    remainingLabel,
    sessionAt,
    setBrightness,
    setScreenToken,
    untilCredits,
    type Ambient,
    type AmbientPlay,
    type AmbientPlaying,
    type AmbientTile,
    type AmbientCast,
    type AmbientTrack,
    type PersonFilmography,
    type RemoteAction,
    type ScreenOptions,
} from "@/lib/ambient";
import { cn } from "@/lib/utils";

/** Relevé du serveur (s). La position avance toute seule entre deux relevés. */
const POLL_MS = 10_000;
/** Pendant une lecture : relevé plus serré (pistes, « Passer l'intro »). */
const POLL_PLAYING_MS = 5_000;
/** Après une commande : le temps que la TV l'applique et renvoie son état. */
const AFTER_COMMAND_MS = 1_200;
/** Toucher l'écran pendant un film : luminosité de repos pendant ce temps. */
const WAKE_MS = 20_000;
/** Décalage de quelques pixels toutes les 5 min (écran allumé en permanence). */
const SHIFT_MS = 5 * 60_000;

type Auth = { kind: "screen"; token: string } | { kind: "admin"; token: string };

class HttpError extends Error {
    constructor(public status: number, message: string) {
        super(message);
    }
}

function authHeaders(auth: Auth): HeadersInit {
    return auth.kind === "screen" ? { "X-Device-Token": auth.token } : { Authorization: `Bearer ${auth.token}` };
}

/** GET d'une route de l'écran (filmographie d'un acteur…) avec le jeton de la tablette. */
async function fetchJson<T>(auth: Auth, path: string): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, { headers: authHeaders(auth), cache: "no-store" });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
    return response.json();
}

async function fetchAmbient(auth: Auth, room: string): Promise<Ambient> {
    const query = auth.kind === "admin" ? `?room=${room}` : "";
    const response = await fetch(`${API_URL}/api/ambient${query}`, { headers: authHeaders(auth), cache: "no-store" });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
    return response.json();
}

/** Télécommande tactile : la TV de la pièce reçoit la commande en moins d'une seconde. */
async function sendCommand(auth: Auth, room: string, command: RemoteAction): Promise<void> {
    const response = await fetch(`${API_URL}/api/ambient/command`, {
        method: "POST",
        headers: { ...authHeaders(auth), "Content-Type": "application/json" },
        body: JSON.stringify(auth.kind === "admin" ? { ...command, room } : command),
    });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
}

/** « Ce soir » : lance un titre proposé sur la TV de la pièce (le serveur vérifie qu'il est proposé). */
async function sendPlay(auth: Auth, room: string, play: AmbientPlay): Promise<{ device: string; online: boolean }> {
    const response = await fetch(`${API_URL}/api/ambient/play`, {
        method: "POST",
        headers: { ...authHeaders(auth), "Content-Type": "application/json" },
        body: JSON.stringify(auth.kind === "admin" ? { ...play, room } : play),
    });
    if (!response.ok) {
        // Le serveur explique le refus (« Aucune TV appairée dans cette pièce »…)
        const detail = await response
            .json()
            .then((body: { detail?: unknown }) => (typeof body.detail === "string" ? body.detail : ""))
            .catch(() => "");
        throw new HttpError(response.status, detail || `HTTP ${response.status}`);
    }
    return response.json();
}

/* ══════════════════════════════════════════════════════════════
   Page
   ══════════════════════════════════════════════════════════════ */

export default function EcranPage() {
    // Lu après le premier rendu : localStorage et l'adresse n'existent que
    // dans le navigateur (le serveur Next.js prépare la page sans eux).
    const [auth, setAuth] = useState<Auth | null | undefined>(undefined);
    const [options, setOptions] = useState<ScreenOptions>({ dim: 6, rest: 40, room: "salon" });
    const [adminAvailable, setAdminAvailable] = useState(false);

    useEffect(() => {
        setOptions(readOptions(window.location.search));
        const token = getScreenToken();
        setAuth(token ? { kind: "screen", token } : null);
        setAdminAvailable(!!getToken());
    }, []);

    const onPaired = useCallback((token: string) => {
        setScreenToken(token);
        setAuth({ kind: "screen", token });
    }, []);

    const onRevoked = useCallback(() => {
        setScreenToken(null);
        setAuth(null);
    }, []);

    return (
        // Défilement vertical possible (téléphone, tablette en portrait) ; en
        // paysage sur la tablette, tout tient sur un écran.
        <main className="fixed inset-0 overflow-y-auto overflow-x-hidden bg-black text-slate-200 selection:bg-transparent">
            {auth === undefined ? null : auth === null ? (
                <PairingView
                    onPaired={onPaired}
                    onPreview={
                        adminAvailable
                            ? () => {
                                  const token = getToken();
                                  if (token) setAuth({ kind: "admin", token });
                              }
                            : undefined
                    }
                />
            ) : (
                <AmbientView auth={auth} options={options} onRevoked={onRevoked} onLeavePreview={() => setAuth(null)} />
            )}
        </main>
    );
}

/* ══════════════════════════════════════════════════════════════
   1. Appairage
   ══════════════════════════════════════════════════════════════ */

interface PairStart {
    device_code: string;
    user_code: string;
    verification_url: string;
    qr_url: string;
    expires_in: number;
    interval: number;
}

function PairingView({ onPaired, onPreview }: { onPaired: (token: string) => void; onPreview?: () => void }) {
    const [pairing, setPairing] = useState<PairStart | null>(null);
    const [error, setError] = useState("");
    const [attempt, setAttempt] = useState(0);

    // Demande un code (et en redemande un s'il expire ou si le serveur est absent).
    useEffect(() => {
        let cancelled = false;
        let retry: ReturnType<typeof setTimeout> | undefined;
        (async () => {
            try {
                const response = await fetch(`${API_URL}/api/devices/pair/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ platform: platformName(navigator.userAgent), kind: "screen" }),
                });
                if (response.status === 403) {
                    throw new HttpError(403, "Appairage possible seulement depuis le réseau local.");
                }
                if (!response.ok) throw new HttpError(response.status, `Le serveur répond ${response.status}.`);
                const data: PairStart = await response.json();
                if (!cancelled) {
                    setPairing(data);
                    setError("");
                }
            } catch (e) {
                if (cancelled) return;
                setPairing(null);
                setError(e instanceof HttpError ? e.message : "Serveur ArrMada injoignable.");
                retry = setTimeout(() => setAttempt((n) => n + 1), 15_000);
            }
        })();
        return () => {
            cancelled = true;
            if (retry) clearTimeout(retry);
        };
    }, [attempt]);

    // « Est-ce validé ? » toutes les `interval` secondes.
    useEffect(() => {
        if (!pairing) return;
        let stopped = false;
        const timer = setInterval(async () => {
            try {
                const response = await fetch(`${API_URL}/api/devices/pair/poll`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ device_code: pairing.device_code }),
                });
                if (response.status === 410) {
                    // Code expiré (10 min) : on en demande un nouveau
                    if (!stopped) setAttempt((n) => n + 1);
                    return;
                }
                if (!response.ok) return;
                const data = await response.json();
                if (data.status === "ok" && data.token && !stopped) onPaired(data.token);
            } catch {
                // réseau coupé un instant : on réessaie au tour suivant
            }
        }, Math.max(2, pairing.interval) * 1000);
        return () => {
            stopped = true;
            clearInterval(timer);
        };
    }, [pairing, onPaired]);

    return (
        <div className="flex min-h-full items-center justify-center p-8">
            <div className="flex w-full max-w-4xl flex-col items-center gap-10 md:flex-row md:items-center md:gap-14">
                <div className="shrink-0">
                    {pairing ? (
                        // QR code fabriqué par le serveur : il pointe vers la page d'appairage de la web app
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={`${API_URL}${pairing.qr_url}`}
                            alt="QR code d'appairage"
                            className="h-56 w-56 rounded-2xl bg-white p-3 opacity-90"
                        />
                    ) : (
                        <div className="grid h-56 w-56 place-items-center rounded-2xl border border-white/10 bg-white/[0.03]">
                            {error ? <WifiOff className="h-10 w-10 text-slate-500" /> : <Loader2 className="h-8 w-8 animate-spin text-slate-500" />}
                        </div>
                    )}
                </div>
                <div className="min-w-0 flex-1 space-y-5 text-center md:text-left">
                    <div className="flex items-center justify-center gap-3 md:justify-start">
                        <div className="h-9 w-9 overflow-hidden rounded-xl">
                            <BrandIcon />
                        </div>
                        <p className="text-sm uppercase tracking-[0.25em] text-slate-400">Écran d&apos;appoint</p>
                    </div>
                    <h1 className="text-3xl font-semibold text-slate-100">Appairer cet écran</h1>
                    {pairing ? (
                        <>
                            <div className="flex justify-center gap-2 md:justify-start" aria-label={`Code ${pairing.user_code}`}>
                                {pairing.user_code.split("").map((char, i) => (
                                    <span
                                        key={i}
                                        className="grid h-16 w-12 place-items-center rounded-xl border border-[#4A9EFF]/40 bg-[#4A9EFF]/10 font-mono text-3xl font-semibold text-[#8CC4FF]"
                                    >
                                        {char}
                                    </span>
                                ))}
                            </div>
                            <p className="text-base leading-relaxed text-slate-400">
                                Vise le QR code avec ton téléphone connecté à ArrMada, ou va dans{" "}
                                <span className="text-slate-200">Réglages → Kodi → Appareils → Appairer</span> et saisis ce code.
                                Choisis la pièce de cet écran : il affichera ce qui passe sur la TV de cette pièce.
                            </p>
                            <p className="flex items-center justify-center gap-2 text-sm text-slate-500 md:justify-start">
                                <Loader2 className="h-4 w-4 animate-spin" /> En attente de validation…
                            </p>
                        </>
                    ) : error ? (
                        <p className="text-base text-amber-300/90">
                            {error} <span className="text-slate-500">Nouvel essai dans quelques secondes.</span>
                        </p>
                    ) : (
                        <p className="text-base text-slate-500">Demande d&apos;un code…</p>
                    )}
                    {onPreview && (
                        <button
                            type="button"
                            onClick={onPreview}
                            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-400 transition hover:border-[#4A9EFF]/50 hover:text-slate-200"
                        >
                            Aperçu avec ma session admin (sans appairer)
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ══════════════════════════════════════════════════════════════
   2. Affichage — lisible depuis le canapé
   ══════════════════════════════════════════════════════════════
   La tablette est lue à 3-4 m. Les tailles ne sont donc pas en pixels mais
   en « unités d'écran » (u), une variable CSS (--u) :
     - paysage : 1 u = le plus petit de 1 % de la hauteur et 0,625 % de la
       largeur → 8 px sur la Pixel Tablet (1280 × 800), 10,8 px sur un PC
       en 1920 × 1080 ;
     - portrait : 1 u = le plus petit de 0,625 % de la hauteur et 1 % de la
       largeur → 8 px sur la tablette tournée, ~3,9 px sur un téléphone.
   La même page remplit n'importe quel écran sans déborder, un peu comme
   un volume LVM en 100%FREE qui prend toute la place disponible.

   Pendant une lecture : l'affiche sur toute la hauteur, l'heure de FIN en
   très grand, puis le début, le reste et la barre de progression. Rien
   d'autre (les téléchargements et sorties attendent la fin du film).
   Au repos : grande horloge, sorties à venir, téléchargements, ampli.
   ══════════════════════════════════════════════════════════════ */

/** Taille en unités d'écran : u(26) → « calc(var(--u) * 26) ». */
const u = (n: number) => `calc(var(--u) * ${n})`;

function AmbientView({
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
        retry: false,
        // Une panne réseau garde le dernier affichage (avec un petit avertissement)
        placeholderData: (previous) => previous,
    });

    // Jeton révoqué dans la web app (401) → retour à l'appairage. Un 403
    // (adresse hors réseau local) ne doit pas effacer le jeton : on attend.
    useEffect(() => {
        if (error instanceof HttpError && error.status === 401 && auth.kind === "screen") onRevoked();
    }, [error, auth.kind, onRevoked]);

    // Télécommande : envoi, puis relecture rapide de l'état renvoyé par la TV
    const queryClient = useQueryClient();
    const loadPerson = useCallback((id: number) => fetchJson<PersonFilmography>(auth, `/api/ambient/person/${id}`), [auth]);
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
                    <RestView now={now} data={data} onPlay={onPlay} />
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

/* ── Pendant une lecture ─────────────────────────────────────── */

function SessionView({
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

/* ── Télécommande tactile (appli Android) ─────────────────────── */

type Sheet = "subtitles" | "audio" | "info" | "volume" | null;

function RemoteBar({
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

/** Feuille qui monte du bas de l'écran ; toucher à côté la ferme. */
function SheetFrame({
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
function VolumeSheet({ amp, run }: { amp: NonNullable<Ambient["amp"]>; run: (command: RemoteAction) => Promise<void> }) {
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
 * Filmographie d'un acteur : ses films de la médiathèque en premier, mis en
 * avant (liseré bleu, « Disponible » s'il est téléchargé), puis ses autres
 * films, plus discrets.
 */
function PersonSheet({ id, loadPerson }: { id: number; loadPerson: (id: number) => Promise<PersonFilmography> }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["person", id],
        queryFn: () => loadPerson(id),
        staleTime: 3_600_000,
    });
    if (isLoading) {
        return <Loader2 className="mx-auto animate-spin text-slate-400" style={{ width: u(6), height: u(6), margin: `${u(6)} auto` }} />;
    }
    if (isError || !data?.person) {
        return (
            <p className="text-slate-400" style={{ fontSize: u(3) }}>
                {data?.error ?? "Filmographie indisponible pour le moment."}
            </p>
        );
    }
    const p = data.person;
    const facts = [p.birthday ? `Né(e) le ${new Date(p.birthday).toLocaleDateString("fr-FR")}` : "", p.place_of_birth ?? ""].filter(Boolean);
    return (
        <div className="flex flex-col" style={{ gap: u(3) }}>
            <div className="flex" style={{ gap: u(3) }}>
                {p.photo && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.photo} alt="" className="shrink-0 rounded-xl object-cover" style={{ width: u(18), height: u(24) }} />
                )}
                <div className="min-w-0">
                    {facts.length > 0 && (
                        <p className="text-slate-400" style={{ fontSize: u(2.8) }}>
                            {facts.join(" · ")}
                        </p>
                    )}
                    {p.biography && (
                        <p className="line-clamp-5 leading-relaxed text-slate-300" style={{ fontSize: u(2.9), marginTop: u(1) }}>
                            {p.biography}
                        </p>
                    )}
                </div>
            </div>

            {data.in_library.length > 0 && (
                <section>
                    <p className="font-medium uppercase text-[#8CC4FF]" style={{ fontSize: u(2.6), letterSpacing: "0.14em", marginBottom: u(1.6) }}>
                        Dans ta médiathèque · {data.in_library.length}
                    </p>
                    <ul className="grid grid-cols-6 portrait:grid-cols-4" style={{ gap: u(2) }}>
                        {data.in_library.map((movie) => (
                            <MoviePoster key={movie.tmdb_id} movie={movie} owned />
                        ))}
                    </ul>
                </section>
            )}

            {data.discover.length > 0 && (
                <section>
                    <p className="font-medium uppercase text-slate-500" style={{ fontSize: u(2.6), letterSpacing: "0.14em", marginBottom: u(1.6) }}>
                        Autres films
                    </p>
                    <ul className="grid grid-cols-8 portrait:grid-cols-5" style={{ gap: u(1.6) }}>
                        {data.discover.slice(0, 24).map((movie) => (
                            <MoviePoster key={movie.tmdb_id} movie={movie} />
                        ))}
                    </ul>
                </section>
            )}
        </div>
    );
}

function MoviePoster({ movie, owned = false }: { movie: PersonFilmography["discover"][number]; owned?: boolean }) {
    const ready = owned && movie.has_file;
    return (
        <li className={cn("flex flex-col", !owned && "opacity-55")} style={{ gap: u(0.6) }}>
            <div
                className={cn(
                    "relative aspect-[2/3] overflow-hidden bg-white/[0.06]",
                    owned && (ready ? "ring-2 ring-[#4A9EFF]" : "ring-1 ring-white/25"),
                )}
                style={{ borderRadius: u(1.2) }}
            >
                {movie.poster ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={movie.poster} alt="" loading="lazy" className="h-full w-full object-cover" />
                ) : (
                    <span className="flex h-full items-center justify-center p-1 text-center text-slate-500" style={{ fontSize: u(2.2) }}>
                        {movie.title}
                    </span>
                )}
                {owned && (
                    <span
                        className={cn("absolute inset-x-0 bottom-0 text-center font-semibold", ready ? "bg-[#4A9EFF] text-[#0b1220]" : "bg-black/70 text-slate-300")}
                        style={{ fontSize: u(2), padding: `${u(0.4)} 0` }}
                    >
                        {ready ? "Disponible" : "Pas encore téléchargé"}
                    </span>
                )}
            </div>
            <span className="truncate text-slate-200" style={{ fontSize: u(2.4) }}>
                {movie.title}
            </span>
            <span className="truncate text-slate-500" style={{ fontSize: u(2.1) }}>
                {[movie.year, movie.character].filter(Boolean).join(" · ")}
            </span>
        </li>
    );
}

/**
 * Bouton de la télécommande. [round] : icône seule dans un rond (le texte
 * devient l'étiquette d'accessibilité), avec une petite [caption] dessous
 * (« 10 », « 30 ») pour les sauts.
 */
function RemoteButton({
    label,
    caption,
    round,
    primary,
    accent,
    onClick,
    children,
}: {
    label: string;
    caption?: string;
    round?: boolean;
    primary?: boolean;
    accent?: boolean;
    onClick: () => void;
    children: React.ReactNode;
}) {
    if (round) {
        return (
            <button
                type="button"
                onClick={onClick}
                aria-label={label}
                title={label}
                className={cn(
                    "flex shrink-0 flex-col items-center justify-center rounded-full transition-colors active:scale-95",
                    primary ? "bg-[#4A9EFF] text-[#0b1220] hover:bg-[#6cb1ff]" : "bg-white/[0.07] text-slate-200 hover:bg-white/[0.12]",
                )}
                style={{ width: u(primary ? 9.5 : 8), height: u(primary ? 9.5 : 8) }}
            >
                {children}
                {caption && (
                    <span className="font-semibold leading-none tabular-nums" style={{ fontSize: u(1.9), marginTop: u(0.3) }}>
                        {caption}
                    </span>
                )}
            </button>
        );
    }
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "flex shrink-0 items-center rounded-full font-medium transition-colors active:scale-95",
                primary
                    ? "bg-[#4A9EFF] text-[#0b1220] hover:bg-[#6cb1ff]"
                    : accent
                      ? "bg-[#4A9EFF]/15 text-[#8CC4FF] ring-1 ring-[#4A9EFF]/40 hover:bg-[#4A9EFF]/25"
                      : "bg-white/[0.07] text-slate-200 hover:bg-white/[0.12]",
            )}
            style={{ height: u(8.5), padding: `0 ${u(2.6)}`, gap: u(1.1), fontSize: u(3) }}
        >
            {children}
            <span>{label}</span>
        </button>
    );
}

/**
 * Outils de la feuille Sous-titres : Bazarr (télécharger les sous-titres FR,
 * les recaler sur le son) et décalage manuel −/+ 0,5 s de la piste affichée.
 * La TV fait le travail et renvoie l'état (en cours, résultat, décalage).
 */
function SubtitleTools({ playing, run }: { playing: AmbientPlaying; run: (command: RemoteAction) => Promise<void> }) {
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

function TrackSheet({ tracks, allowOff, onPick }: { tracks: AmbientTrack[]; allowOff: boolean; onPick: (index: number) => void }) {
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

function InfoSheet({ playing, onPerson }: { playing: AmbientPlaying; onPerson: (person: AmbientCast) => void }) {
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
                                <img src={person.photo} alt="" className="rounded-full object-cover" style={{ width: u(14), height: u(14) }} />
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

/* ── Au repos ────────────────────────────────────────────────── */

/** Lancer un titre de « Ce soir » : renvoie la TV qui l'a reçu. */
type PlayHandler = (play: AmbientPlay) => Promise<{ device: string; online: boolean }>;

function RestView({ now, data, onPlay }: { now: Date; data?: Ambient; onPlay: PlayHandler }) {
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
                    {data.upcoming.length > 0 && <UpcomingPanel upcoming={data.upcoming} now={now} />}
                    {data.downloads.length > 0 && <DownloadsPanel downloads={data.downloads} />}
                    {amp && <AmpPanel amp={amp} />}
                </div>
            )}
        </div>
    );
}

/* ── « Ce soir » : choisir quoi regarder, le lancer sur la TV ─── */

const TONIGHT_TABS = [
    { key: "resume", label: "Reprendre" },
    { key: "watchlist", label: "Ma liste" },
    { key: "fresh", label: "Nouveaux films" },
] as const;
type TonightKey = (typeof TONIGHT_TABS)[number]["key"];

function TonightShelf({ tonight, inRoom, onPlay }: { tonight: NonNullable<Ambient["tonight"]>; inRoom: string; onPlay: PlayHandler }) {
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

function Panel({
    icon: Icon,
    title,
    className,
    children,
}: {
    icon: typeof Speaker;
    title: string;
    className?: string;
    children: React.ReactNode;
}) {
    return (
        <section
            className={cn("min-w-0 border border-white/[0.07] bg-white/[0.03]", className)}
            style={{ padding: u(2.8), borderRadius: u(2) }}
        >
            <p
                className="flex items-center uppercase text-slate-500"
                style={{ fontSize: u(2.6), gap: u(1.2), letterSpacing: "0.18em", marginBottom: u(2) }}
            >
                <Icon style={{ width: u(2.8), height: u(2.8) }} /> {title}
            </p>
            {children}
        </section>
    );
}

function UpcomingPanel({ upcoming, now }: { upcoming: Ambient["upcoming"]; now: Date }) {
    return (
        <Panel icon={CalendarClock} title="À venir" className="flex-[1.7]">
            <ul className="flex flex-col" style={{ gap: u(1.8), fontSize: u(3.4) }}>
                {upcoming.map((item, i) => (
                    <li key={`${item.title}-${item.label}-${i}`} className="flex items-baseline justify-between" style={{ gap: u(2) }}>
                        <span className="min-w-0 truncate">
                            <span className="text-slate-100">{item.title}</span>
                            <span className="text-slate-500">
                                {" "}
                                {item.kind === "episode" ? item.label : releaseTypeLabel(item.release_type) || item.label}
                            </span>
                        </span>
                        <span className="shrink-0 text-[#8CC4FF]">{releaseWhen(item.air_date, now, item.kind)}</span>
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

function DownloadsPanel({ downloads }: { downloads: Ambient["downloads"] }) {
    return (
        <Panel icon={Download} title="Téléchargements" className="flex-[1.3]">
            <ul className="flex flex-col" style={{ gap: u(2), fontSize: u(3.2) }}>
                {downloads.map((d, i) => (
                    <li key={`${d.title}-${i}`} className="flex flex-col" style={{ gap: u(0.9) }}>
                        <div className="flex items-baseline justify-between" style={{ gap: u(2) }}>
                            <span className="truncate text-slate-100">{d.title}</span>
                            <span className="shrink-0 tabular-nums text-slate-400">{d.paused ? "en pause" : d.time_left || `${d.progress} %`}</span>
                        </div>
                        <div className="overflow-hidden rounded-full bg-white/10" style={{ height: u(0.9) }}>
                            <div className={cn("h-full rounded-full", d.paused ? "bg-slate-500" : "bg-[#4A9EFF]")} style={{ width: `${d.progress}%` }} />
                        </div>
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

function AmpPanel({ amp }: { amp: NonNullable<Ambient["amp"]> }) {
    const on = amp.power === "on";
    return (
        <Panel icon={Speaker} title={amp.name || "Ampli"} className="flex-[0.9]">
            {on ? (
                <div className="flex flex-col" style={{ gap: u(1) }}>
                    <p className="flex items-center leading-none tabular-nums text-slate-100" style={{ fontSize: u(9), gap: u(1.2) }}>
                        {amp.mute ? <VolumeX className="text-amber-300" style={{ width: u(6), height: u(6) }} /> : null}
                        {amp.volume_pct ?? "—"}
                        <span className="text-slate-500" style={{ fontSize: u(4) }}>
                            %
                        </span>
                    </p>
                    <p className="truncate text-slate-300" style={{ fontSize: u(3.2) }}>
                        {prettyName(amp.input) || "—"}
                    </p>
                    <p className="truncate text-slate-500" style={{ fontSize: u(2.8) }}>
                        {prettyName(amp.sound_program)}
                    </p>
                </div>
            ) : (
                <p className="text-slate-500" style={{ fontSize: u(3.2) }}>
                    En veille
                </p>
            )}
        </Panel>
    );
}

/* ══════════════════════════════════════════════════════════════
   Petits outils
   ══════════════════════════════════════════════════════════════ */

/** L'heure, rafraîchie chaque seconde (horloge et position de lecture). */
function useNow(): Date {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const timer = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);
    return now;
}

/** Rétroéclairage (Fully Kiosk) : seulement quand la valeur voulue change (null : ne rien toucher). */
function useBrightness(value: number | null) {
    const last = useRef<number | null>(null);
    useEffect(() => {
        if (value === null || last.current === value || !hasFully()) return;
        if (setBrightness(value)) last.current = value;
    }, [value]);
}

/**
 * Garder l'écran allumé hors de Fully (Chrome) : l'API « Wake Lock » ne
 * marche qu'en HTTPS ; sur le réseau local en http, elle est absente et
 * c'est Fully (« Keep Screen On ») ou Android qu'il faut régler.
 */
function useWakeLock() {
    useEffect(() => {
        type WakeLockSentinel = { release: () => Promise<void> };
        const nav = navigator as Navigator & { wakeLock?: { request: (type: "screen") => Promise<WakeLockSentinel> } };
        if (!nav.wakeLock || !window.isSecureContext) return;
        let sentinel: WakeLockSentinel | null = null;
        const acquire = () => {
            nav.wakeLock
                ?.request("screen")
                .then((s) => (sentinel = s))
                .catch(() => undefined);
        };
        acquire();
        // Le verrou saute quand la page passe en arrière-plan : on le reprend au retour
        const onVisible = () => document.visibilityState === "visible" && acquire();
        document.addEventListener("visibilitychange", onVisible);
        return () => {
            document.removeEventListener("visibilitychange", onVisible);
            sentinel?.release().catch(() => undefined);
        };
    }, []);
}

/** Petit décalage périodique de tout l'affichage (même image affichée des heures). */
function usePixelShift(): { x: number; y: number } {
    const [shift, setShift] = useState({ x: 0, y: 0 });
    useEffect(() => {
        const timer = setInterval(() => {
            setShift({ x: Math.round(Math.random() * 12 - 6), y: Math.round(Math.random() * 12 - 6) });
        }, SHIFT_MS);
        return () => clearInterval(timer);
    }, []);
    return shift;
}
