"use client";

/**
 * Écran d'appoint du salon — la tablette posée sous la TV.
 * ----------------------------------------------------------------
 * Affiche, sans gêner le film :
 *  - l'heure, et pendant une lecture : titre, épisode, affiche, heure de
 *    DÉBUT, heure de FIN prévue, temps restant, barre de progression ;
 *  - l'ampli de la pièce (volume, entrée, programme sonore) ;
 *  - les téléchargements en cours et les sorties de ce soir / demain.
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
import { Download, Loader2, Pause, Speaker, CalendarClock, VolumeX, WifiOff } from "lucide-react";
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
   2. Affichage
   ══════════════════════════════════════════════════════════════ */

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

    // Rien tant que la 1re réponse n'est pas là : recharger la page pendant
    // un film ne doit pas faire flasher l'écran à la luminosité de repos.
    useBrightness(data ? (dimmed ? options.dim : options.rest) : null);
    useWakeLock();
    const shift = usePixelShift();

    return (
        <div
            className="relative min-h-full w-full"
            onPointerDown={() => setAwakeUntil(Date.now() + WAKE_MS)}
            style={{ transform: `translate(${shift.x}px, ${shift.y}px)`, transition: "transform 4s ease-in-out" }}
        >
            {/* Fond : image du film, très sombre et floue (rien pendant le repos) */}
            <AnimatePresence>
                {playing?.fanart && (
                    <motion.div
                        key={playing.fanart}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: dimmed ? 0.1 : 0.22 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 1.5 }}
                        className="pointer-events-none fixed inset-0 bg-cover bg-center blur-md"
                        style={{ backgroundImage: `url(${playing.fanart})` }}
                    />
                )}
            </AnimatePresence>
            <div className="pointer-events-none fixed inset-0 bg-gradient-to-t from-black via-black/70 to-black/40" />

            {/* Contenu : assombri en mode séance (en plus du rétroéclairage) */}
            <div
                className={cn(
                    "relative flex min-h-[100dvh] flex-col gap-6 p-6 transition-[opacity,filter] duration-1000 sm:p-10",
                    dimmed ? "opacity-60 [filter:saturate(0.6)]" : "opacity-100",
                )}
            >
                <Header now={now} data={data} compact={inSession} />

                <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,22rem)]">
                    <div className="flex min-h-0 flex-col justify-end">
                        {playing ? (
                            <NowPlaying playing={playing} now={now} offset={offset} />
                        ) : (
                            <IdleHint room={data?.room_label} />
                        )}
                    </div>
                    <aside className="flex min-h-0 flex-col justify-end gap-5">
                        {data?.amp && <AmpCard amp={data.amp} />}
                        {data && data.downloads.length > 0 && <DownloadsCard downloads={data.downloads} />}
                        {data && data.upcoming.length > 0 && <UpcomingCard upcoming={data.upcoming} now={now} />}
                    </aside>
                </div>
            </div>

            {/* Bandeaux discrets : hors ligne, aperçu */}
            <div className="absolute right-4 top-4 flex items-center gap-2 text-xs">
                {error && !(error instanceof HttpError && error.status === 401) && (
                    <span className="flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-amber-300/80">
                        <WifiOff className="h-3.5 w-3.5" />
                        Hors ligne{data ? ` · données de ${hhmm(new Date(dataUpdatedAt))}` : ""}
                    </span>
                )}
                {auth.kind === "admin" && (
                    <span className="flex items-center gap-1 rounded-full bg-white/5 px-1 py-1 text-slate-400">
                        <span className="px-1.5">Aperçu</span>
                        {(["salon", "cinema"] as const).map((r) => (
                            <button
                                key={r}
                                type="button"
                                onClick={() => setRoom(r)}
                                className={cn("rounded-full px-2 py-0.5", room === r ? "bg-[#4A9EFF]/20 text-[#8CC4FF]" : "hover:text-slate-200")}
                            >
                                {r === "salon" ? "Salon" : "Cinéma"}
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

/* ── En-tête : heure et date ─────────────────────────────────── */

function Header({ now, data, compact }: { now: Date; data?: Ambient; compact: boolean }) {
    return (
        <header className="flex items-start justify-between gap-4">
            <div>
                <p
                    className={cn(
                        "font-extralight leading-none tracking-tight text-slate-100 tabular-nums transition-all duration-700",
                        compact ? "text-6xl sm:text-7xl" : "text-8xl sm:text-[10rem]",
                    )}
                >
                    {hhmm(now)}
                </p>
                {/* « Samedi 10 octobre » : majuscule au premier mot seulement */}
                <p className="mt-2 text-lg text-slate-400 first-letter:uppercase sm:text-xl">{longDay(now)}</p>
            </div>
            {data && <p className="pt-2 text-sm uppercase tracking-[0.25em] text-slate-500">{data.room_label}</p>}
        </header>
    );
}

/* ── Lecture en cours ────────────────────────────────────────── */

function NowPlaying({ playing, now, offset }: { playing: AmbientPlaying; now: Date; offset: number }) {
    const session = sessionAt(playing, now.getTime(), offset);
    return (
        <motion.section
            key={`${playing.title}-${playing.subtitle}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="flex items-end gap-6"
        >
            {playing.poster && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={playing.poster}
                    alt=""
                    className="hidden aspect-[2/3] w-36 shrink-0 rounded-xl object-cover shadow-2xl shadow-black sm:block lg:w-44"
                />
            )}
            <div className="min-w-0 flex-1 space-y-4">
                <div>
                    <p className="flex items-center gap-2 text-sm uppercase tracking-[0.2em] text-slate-500">
                        {session.paused ? (
                            <span className="flex items-center gap-1.5 text-amber-300/80">
                                <Pause className="h-3.5 w-3.5" /> En pause
                            </span>
                        ) : (
                            <span>{playing.kind === "episode" ? "Épisode en cours" : "Film en cours"}</span>
                        )}
                        {playing.device && <span className="normal-case tracking-normal text-slate-600">· {playing.device}</span>}
                    </p>
                    <h2 className="mt-1 truncate text-3xl font-semibold text-slate-100 sm:text-4xl">{playing.title}</h2>
                    {playing.subtitle && <p className="mt-1 truncate text-lg text-slate-400 sm:text-xl">{playing.subtitle}</p>}
                </div>

                <div className="grid grid-cols-3 gap-3">
                    <TimeBlock label="Début" value={hhmm(session.startedAt)} />
                    <TimeBlock
                        label={session.paused ? "Fin, si reprise" : "Fin prévue"}
                        value={hhmm(session.endsAt)}
                        highlight
                    />
                    <TimeBlock label="Reste" value={session.endsAt ? remainingLabel(session.remaining) : "—"} />
                </div>

                {session.endsAt && (
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                            className={cn("h-full rounded-full transition-[width] duration-1000 ease-linear", session.paused ? "bg-amber-300/60" : "bg-[#4A9EFF]/80")}
                            style={{ width: `${(session.progress * 100).toFixed(2)}%` }}
                        />
                    </div>
                )}
            </div>
        </motion.section>
    );
}

function TimeBlock({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
    return (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-3 sm:px-4">
            <p className="truncate text-[11px] uppercase tracking-[0.08em] text-slate-500 sm:text-xs sm:tracking-[0.18em]">{label}</p>
            <p className={cn("mt-1 text-2xl font-light tabular-nums sm:text-3xl", highlight ? "text-[#8CC4FF]" : "text-slate-200")}>{value}</p>
        </div>
    );
}

function IdleHint({ room }: { room?: string }) {
    return (
        <p className="text-base text-slate-600">
            Rien en lecture{room ? ` dans ${room === "Salon" ? "le salon" : `la ${room.toLowerCase()}`}` : ""}. Lance un film sur
            Kodi : l&apos;heure de fin s&apos;affichera ici.
        </p>
    );
}

/* ── Colonne de droite ───────────────────────────────────────── */

function Card({ icon: Icon, title, children }: { icon: typeof Speaker; title: string; children: React.ReactNode }) {
    return (
        <section className="rounded-2xl border border-white/[0.06] bg-white/[0.025] p-4">
            <p className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                <Icon className="h-3.5 w-3.5" /> {title}
            </p>
            {children}
        </section>
    );
}

function AmpCard({ amp }: { amp: NonNullable<Ambient["amp"]> }) {
    const on = amp.power === "on";
    return (
        <Card icon={Speaker} title={amp.name || "Ampli"}>
            {on ? (
                <div className="flex items-end justify-between gap-3">
                    <div className="min-w-0">
                        <p className="truncate text-base text-slate-200">{prettyName(amp.input) || "—"}</p>
                        <p className="truncate text-sm text-slate-500">{prettyName(amp.sound_program)}</p>
                    </div>
                    <p className="flex items-center gap-1.5 text-3xl font-light tabular-nums text-slate-200">
                        {amp.mute ? <VolumeX className="h-6 w-6 text-amber-300/80" /> : null}
                        {amp.volume_pct ?? "—"}
                        <span className="text-base text-slate-500">%</span>
                    </p>
                </div>
            ) : (
                <p className="text-sm text-slate-500">En veille</p>
            )}
        </Card>
    );
}

function DownloadsCard({ downloads }: { downloads: Ambient["downloads"] }) {
    return (
        <Card icon={Download} title="Téléchargements">
            <ul className="space-y-3">
                {downloads.map((d, i) => (
                    <li key={`${d.title}-${i}`} className="space-y-1">
                        <div className="flex items-baseline justify-between gap-3 text-sm">
                            <span className="truncate text-slate-300">{d.title}</span>
                            <span className="shrink-0 tabular-nums text-slate-500">{d.paused ? "en pause" : d.time_left || `${d.progress} %`}</span>
                        </div>
                        <div className="h-1 overflow-hidden rounded-full bg-white/10">
                            <div className={cn("h-full rounded-full", d.paused ? "bg-slate-500" : "bg-[#4A9EFF]/70")} style={{ width: `${d.progress}%` }} />
                        </div>
                    </li>
                ))}
            </ul>
        </Card>
    );
}

function UpcomingCard({ upcoming, now }: { upcoming: Ambient["upcoming"]; now: Date }) {
    return (
        <Card icon={CalendarClock} title="À venir">
            <ul className="space-y-2.5">
                {upcoming.map((u, i) => (
                    <li key={`${u.title}-${u.label}-${i}`} className="flex items-baseline justify-between gap-3 text-sm">
                        <span className="min-w-0 truncate">
                            <span className="text-slate-300">{u.title}</span>
                            <span className="text-slate-500">
                                {" "}
                                {u.kind === "episode" ? u.label : releaseTypeLabel(u.release_type) || u.label}
                            </span>
                        </span>
                        <span className="shrink-0 text-slate-500">{releaseWhen(u.air_date, now, u.kind)}</span>
                    </li>
                ))}
            </ul>
        </Card>
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
