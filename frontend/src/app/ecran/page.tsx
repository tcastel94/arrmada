"use client";

/**
 * Écran d'appoint du salon — la tablette posée sous la TV.
 * ----------------------------------------------------------------
 * Affiche, sans gêner le film, en grand (lu depuis le canapé, à 3-4 m) :
 *  - pendant une lecture : l'affiche sur toute la hauteur, l'heure de FIN
 *    prévue en très grand, l'heure de DÉBUT, le temps restant, la barre de
 *    progression, le titre, l'heure et le volume de l'ampli ;
 *  - au repos : une grande horloge, les sorties de ce soir / demain, les
 *    téléchargements en cours et l'ampli de la pièce.
 *
 * Trois états, comme une petite machine à états :
 *  1. « appairage » : pas encore de jeton → code + QR code à valider depuis
 *     le téléphone (Réglages → Kodi → Appareils), comme pour une TV ;
 *  2. « affichage » : jeton « écran » (lecture seule, une seule route
 *     serveur : GET /api/ambient), relevé toutes les 10 s ;
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
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarClock, Download, Loader2, Pause, Speaker, Volume2, VolumeX, WifiOff } from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { API_URL } from "@/lib/constants";
import { getToken } from "@/lib/api-client";
import {
    getScreenToken,
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
    type Ambient,
    type AmbientPlaying,
    type ScreenOptions,
} from "@/lib/ambient";
import { cn } from "@/lib/utils";

/** Relevé du serveur (s). La position avance toute seule entre deux relevés. */
const POLL_MS = 10_000;
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

async function fetchAmbient(auth: Auth, room: string): Promise<Ambient> {
    const query = auth.kind === "admin" ? `?room=${room}` : "";
    const response = await fetch(`${API_URL}/api/ambient${query}`, { headers: authHeaders(auth), cache: "no-store" });
    if (!response.ok) throw new HttpError(response.status, `HTTP ${response.status}`);
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
        refetchInterval: POLL_MS,
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
                    <SessionView playing={playing} now={now} offset={offset} amp={data?.amp ?? null} />
                ) : (
                    <RestView now={now} data={data} />
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
}: {
    playing: AmbientPlaying;
    now: Date;
    offset: number;
    amp: Ambient["amp"];
}) {
    const session = sessionAt(playing, now.getTime(), offset);
    const status = session.paused ? "En pause" : playing.kind === "episode" ? "Épisode en cours" : "Film en cours";
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

            <div className="flex min-w-0 flex-1 flex-col justify-between" style={{ gap: u(2.5) }}>
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
                            <span className="flex items-center text-slate-400" style={{ fontSize: u(3.8), gap: u(1) }}>
                                {amp.mute ? (
                                    <VolumeX className="text-amber-300" style={{ width: u(4), height: u(4) }} />
                                ) : (
                                    <Volume2 style={{ width: u(4), height: u(4) }} />
                                )}
                                {amp.volume_pct ?? "—"} %
                            </span>
                        )}
                        <span className="leading-none text-slate-200" style={{ fontSize: u(6.5) }}>
                            {hhmm(now)}
                        </span>
                    </div>
                </div>

                {/* Titre (2 lignes au plus) et épisode ou année */}
                <div>
                    <h1 className="line-clamp-2 font-semibold leading-[1.05] text-white" style={{ fontSize: u(8) }}>
                        {playing.title}
                    </h1>
                    {playing.subtitle && (
                        <p className="truncate text-slate-400" style={{ fontSize: u(4.6), marginTop: u(1) }}>
                            {playing.subtitle}
                        </p>
                    )}
                </div>

                {/* L'heure de fin : l'info principale, donc la plus grosse */}
                <div>
                    <p className="font-medium uppercase text-slate-400" style={{ fontSize: u(3.6), letterSpacing: "0.14em" }}>
                        {session.paused ? "Fin si reprise maintenant" : "Fin prévue"}
                    </p>
                    <p
                        className={cn("font-medium leading-[0.9] tracking-tight tabular-nums", session.paused ? "text-amber-200" : "text-[#8CC4FF]")}
                        style={{ fontSize: u(26) }}
                    >
                        {hhmm(session.endsAt)}
                    </p>
                </div>

                {/* Début et temps restant */}
                <div className="flex flex-wrap" style={{ columnGap: u(9), rowGap: u(2) }}>
                    <BigFigure label="Début" value={hhmm(session.startedAt)} />
                    <BigFigure label="Reste" value={session.endsAt ? remainingLabel(session.remaining) : "—"} />
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
            </div>
        </motion.section>
    );
}

function BigFigure({ label, value }: { label: string; value: string }) {
    return (
        <div className="min-w-0">
            <p className="font-medium uppercase text-slate-400" style={{ fontSize: u(3.2), letterSpacing: "0.14em" }}>
                {label}
            </p>
            <p className="leading-none tabular-nums text-slate-100" style={{ fontSize: u(11), marginTop: u(0.8) }}>
                {value}
            </p>
        </div>
    );
}

/* ── Au repos ────────────────────────────────────────────────── */

function RestView({ now, data }: { now: Date; data?: Ambient }) {
    const room = data?.room_label;
    const amp = data?.amp ?? null;
    const hasPanels = !!data && (data.upcoming.length > 0 || data.downloads.length > 0 || !!amp);
    return (
        <div className="flex min-h-[100dvh] flex-col justify-between" style={{ padding: u(5), gap: u(4) }}>
            <header className="flex items-start justify-between" style={{ gap: u(3) }}>
                <div>
                    <p className="font-light leading-[0.85] tracking-tight tabular-nums text-slate-100" style={{ fontSize: u(30) }}>
                        {hhmm(now)}
                    </p>
                    {/* « Samedi 10 octobre » : majuscule au premier mot seulement */}
                    <p className="text-slate-400 first-letter:uppercase" style={{ fontSize: u(5), marginTop: u(2.5) }}>
                        {longDay(now)}
                    </p>
                </div>
                {room && (
                    <p className="uppercase text-slate-500" style={{ fontSize: u(3), letterSpacing: "0.2em", paddingTop: u(2) }}>
                        {room}
                    </p>
                )}
            </header>

            <div className="flex flex-col" style={{ gap: u(3) }}>
                <p className="text-slate-500" style={{ fontSize: u(3) }}>
                    Rien en lecture{room ? ` dans ${room === "Salle de cinéma" ? "la salle de cinéma" : `le ${room.toLowerCase()}`}` : ""}. Lance un film sur
                    Kodi : l&apos;heure de fin s&apos;affichera ici en grand.
                </p>
                {hasPanels && (
                    <div className="flex portrait:flex-col" style={{ gap: u(3) }}>
                        {data.upcoming.length > 0 && <UpcomingPanel upcoming={data.upcoming} now={now} />}
                        {data.downloads.length > 0 && <DownloadsPanel downloads={data.downloads} />}
                        {amp && <AmpPanel amp={amp} />}
                    </div>
                )}
            </div>
        </div>
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
