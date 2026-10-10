"use client";

/**
 * Grand lecteur « En lecture » du Salon (Kodi).
 * ----------------------------------------------------------------
 * - Affiche floutée en fond, affiche nette inclinable (TiltCard), titre,
 *   méta (année, durée, note, genres), infos techniques (4K, HDR, codecs).
 * - Progression = curseur accessible : on peut glisser / utiliser les
 *   flèches pour se déplacer dans le film (commande « seek » de Kodi).
 * - Entre deux interrogations (3 s), la position avance localement chaque
 *   seconde → horloge fluide sans surcharger Kodi.
 * - Lecture/pause, ±10/30 s, stop, volume (envoyé au relâchement) et
 *   sourdine, avec mise à jour optimiste de l'affichage.
 * - États dédiés : Kodi non configuré, injoignable, rien en lecture.
 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
    ArrowUpRight,
    CalendarDays,
    Clapperboard,
    Clock,
    Film,
    Library,
    MonitorPlay,
    Pause,
    Play,
    RotateCcw,
    RotateCw,
    Settings2,
    Square,
    Star,
    Subtitles,
    Volume2,
    VolumeX,
    WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { TiltCard } from "@/components/fx/tilt-card";
import { RangeSlider } from "@/components/remote/range-slider";
import { useKodiControl, useKodiNowPlaying, useKodiSettings, type KodiNowPlaying } from "@/hooks/use-kodi";
import { formatClock } from "@/lib/format";
import { EASE_OUT, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

const NOW_PLAYING_KEY = ["kodi", "now-playing"];

/** Nombre de canaux audio → notation home-cinéma. */
function channelsLabel(ch?: number | null): string | null {
    if (!ch) return null;
    if (ch <= 1) return "Mono";
    if (ch === 2) return "Stéréo";
    if (ch === 6) return "5.1";
    if (ch === 8) return "7.1";
    return `${ch} canaux`;
}

/** Libellés techniques lisibles (codecs en majuscules, alias courants). */
function techLabel(v?: string | null): string | null {
    if (!v) return null;
    const map: Record<string, string> = {
        hevc: "HEVC",
        h264: "H.264",
        avc1: "H.264",
        truehd: "TrueHD",
        eac3: "E-AC3",
        ac3: "AC3",
        dtshd_ma: "DTS-HD MA",
        dca: "DTS",
        dolbyvision: "Dolby Vision",
        hdr10plus: "HDR10+",
    };
    return map[v.toLowerCase()] ?? v.toUpperCase();
}

/** Langue audio ISO 639-2 (« fre ») → code court lisible (« FR »). */
function languageLabel(code?: string | null): string | null {
    if (!code) return null;
    const map: Record<string, string> = { fre: "FR", fra: "FR", eng: "EN", ger: "DE", deu: "DE", spa: "ES", ita: "IT", jpn: "JA", kor: "KO", por: "PT" };
    return map[code.toLowerCase()] ?? code.toUpperCase();
}

/**
 * Position « vivante » : part de la dernière valeur lue et avance d'une
 * seconde par seconde tant que la lecture n'est pas en pause.
 */
function useLivePosition(np: KodiNowPlaying | undefined, fetchedAt: number) {
    const [now, setNow] = useState(() => Date.now());
    const running = !!np?.playing && !np.paused;
    useEffect(() => {
        if (!running) return;
        const id = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(id);
    }, [running]);
    const base = np?.position ?? 0;
    const total = np?.total ?? 0;
    if (!running) return base;
    const elapsed = Math.max(0, (now - fetchedAt) / 1000);
    return total > 0 ? Math.min(total, base + elapsed) : base + elapsed;
}

export function NowPlayingHero() {
    const settings = useKodiSettings();
    const configured = (settings.data?.length ?? 0) > 0;
    const query = useKodiNowPlaying(configured);
    const np = query.data;

    if (settings.isLoading || (configured && query.isLoading)) return <HeroSkeleton />;

    if (settings.isError) {
        return (
            <HeroShell>
                <ErrorState error={settings.error} onRetry={() => settings.refetch()} title="Impossible de lire la configuration Kodi" />
            </HeroShell>
        );
    }

    if (!configured) {
        return (
            <HeroShell>
                <EmptyState
                    icon={MonitorPlay}
                    title="Aucun Kodi configuré"
                    description="Ajoute ton lecteur Kodi pour voir ce qui passe à l'écran et le piloter d'ici."
                    action={{ label: "Configurer Kodi", href: "/settings/kodi" }}
                />
            </HeroShell>
        );
    }

    // Erreur sans aucune donnée précédente (sinon on garde l'affichage).
    if (query.isError && !np) {
        return (
            <HeroShell>
                <ErrorState error={query.error} onRetry={() => query.refetch()} title="Impossible de joindre Kodi" />
            </HeroShell>
        );
    }

    return (
        <AnimatePresence mode="wait" initial={false}>
            {np?.playing ? (
                <motion.div
                    key="playing"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.45, ease: EASE_OUT }}
                >
                    <Player np={np} fetchedAt={query.dataUpdatedAt} />
                </motion.div>
            ) : (
                <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <IdleState np={np} onRetry={() => query.refetch()} retrying={query.isFetching} />
                </motion.div>
            )}
        </AnimatePresence>
    );
}

/* ── Cadres et états ────────────────────────────────────────── */

function HeroShell({ children, className }: { children: React.ReactNode; className?: string }) {
    return <section className={cn("glass border-gradient relative overflow-hidden rounded-3xl", className)}>{children}</section>;
}

function HeroSkeleton() {
    return (
        <HeroShell className="p-5 md:p-7">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-[180px_1fr]">
                <Shimmer className="mx-auto aspect-[2/3] w-36 rounded-2xl md:w-full" />
                <div className="space-y-4">
                    <Shimmer className="h-3 w-32 rounded-md" />
                    <Shimmer className="h-9 w-3/4 rounded-lg" />
                    <Shimmer className="h-3 w-1/2 rounded-md" />
                    <Shimmer className="h-16 w-full rounded-lg" />
                    <Shimmer className="h-2 w-full rounded-full" />
                    <Shimmer className="h-12 w-2/3 rounded-full" />
                </div>
            </div>
        </HeroShell>
    );
}

/** Rien en lecture (ou Kodi injoignable). */
function IdleState({ np, onRetry, retrying }: { np?: KodiNowPlaying; onRetry: () => void; retrying: boolean }) {
    const unreachable = !!(np as { error?: string } | undefined)?.error;
    return (
        <HeroShell>
            {/* Décor : halo violet qui respire + grille */}
            <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid opacity-30 [mask-image:radial-gradient(ellipse_at_center,#000,transparent_70%)]" />
            <div
                aria-hidden
                className="pointer-events-none absolute left-1/2 top-1/2 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40 animate-pulse-glow"
                style={{ background: "radial-gradient(closest-side, hsl(262 83% 60% / 0.5), transparent)" }}
            />
            <div className="relative px-5 pb-8 md:px-8">
                {unreachable ? (
                    <EmptyState
                        tone="error"
                        icon={WifiOff}
                        title={`${np?.kodi ?? "Kodi"} ne répond pas`}
                        description="Il est peut-être éteint, en veille ou a changé d'adresse IP. Rallume-le puis réessaie."
                        action={{ label: retrying ? "Nouvel essai…" : "Réessayer", onClick: onRetry }}
                    />
                ) : (
                    <EmptyState
                        icon={Clapperboard}
                        title="Rien en lecture"
                        description={`${np?.kodi ?? "Kodi"} est prêt. Lance un film depuis ta médiathèque : il s'affichera ici avec sa télécommande.`}
                    />
                )}
                <div className="-mt-2 flex flex-wrap justify-center gap-2">
                    {unreachable ? (
                        <Button asChild variant="outline" size="sm">
                            <Link href="/settings/kodi">
                                <Settings2 /> Vérifier les réglages
                            </Link>
                        </Button>
                    ) : (
                        <>
                            <Button asChild size="sm">
                                <Link href="/media">
                                    <Library /> Ouvrir la médiathèque
                                </Link>
                            </Button>
                            <Button asChild variant="outline" size="sm">
                                <Link href="/calendar">
                                    <CalendarDays /> Sorties à venir
                                </Link>
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </HeroShell>
    );
}

/* ── Lecteur ────────────────────────────────────────────────── */

function Player({ np, fetchedAt }: { np: KodiNowPlaying; fetchedAt: number }) {
    const qc = useQueryClient();
    const control = useKodiControl();
    const total = np.total ?? 0;
    const livePos = useLivePosition(np, fetchedAt);

    // Curseur de progression : valeur locale pendant le glissement.
    const [seeking, setSeeking] = useState<number | null>(null);
    const shownPos = seeking ?? livePos;
    const pct = total > 0 ? (shownPos / total) * 100 : np.percentage ?? 0;

    // Volume : valeur locale pendant le glissement, sinon celle de Kodi
    // (0 affiché en sourdine, mais on peut quand même faire glisser).
    const [vol, setVol] = useState<number | null>(null);
    const shownVol = vol ?? (np.muted ? 0 : np.volume ?? 100);

    /**
     * Applique un changement à l'affichage AVANT la réponse de Kodi.
     * On fige aussi la position « vivante » actuelle : sinon, l'horloge
     * repartirait de la dernière valeur lue (jusqu'à 3 s en arrière).
     */
    const patch = (changes: Partial<KodiNowPlaying>) =>
        qc.setQueryData<KodiNowPlaying>(NOW_PLAYING_KEY, (old) =>
            old ? { ...old, position: Math.round(livePos), ...changes } : old,
        );

    const send = (
        vars: { action: "playpause" | "stop" | "seek" | "volume" | "mute"; value?: number },
        optimistic?: Partial<KodiNowPlaying>,
    ) => {
        const previous = qc.getQueryData<KodiNowPlaying>(NOW_PLAYING_KEY);
        if (optimistic) patch(optimistic);
        control.mutate(vars, {
            onError: (e) => {
                if (previous) qc.setQueryData(NOW_PLAYING_KEY, previous);
                toast.error("Commande Kodi refusée", { description: e.message });
            },
        });
    };

    const seekTo = (seconds: number) => {
        if (total <= 0) return;
        const clamped = Math.max(0, Math.min(total - 1, seconds));
        send({ action: "seek", value: (clamped / total) * 100 }, { position: clamped });
    };

    const techBadges = [
        np.resolution,
        techLabel(np.hdr),
        techLabel(np.video_codec),
        [techLabel(np.audio_codec), channelsLabel(np.audio_channels)].filter(Boolean).join(" "),
        languageLabel(np.audio_language),
    ].filter((b): b is string => !!b);

    const href = np.media_id && np.media_type ? `/media/${np.media_type}/${np.media_id}` : null;
    const remaining = Math.max(0, total - shownPos);

    return (
        <HeroShell>
            {/* Ambiance : affiche floutée + dégradés */}
            {np.poster && (
                <motion.div
                    key={np.poster}
                    aria-hidden
                    initial={{ opacity: 0, scale: 1.4 }}
                    animate={{ opacity: 0.45, scale: 1.25 }}
                    transition={{ duration: 1.2, ease: EASE_OUT }}
                    className="pointer-events-none absolute inset-0 blur-3xl saturate-150"
                    style={{ backgroundImage: `url("${np.poster}")`, backgroundSize: "cover", backgroundPosition: "center" }}
                />
            )}
            <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-t from-background via-background/70 to-background/20" />
            <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background/80 via-transparent to-transparent" />

            <div className="relative grid grid-cols-1 gap-5 p-5 md:grid-cols-[180px_minmax(0,1fr)] md:gap-7 md:p-7">
                {/* Affiche */}
                <div className="mx-auto w-32 sm:w-40 md:w-full">
                    <TiltCard className="rounded-2xl">
                        {np.poster ? (
                            <img
                                src={np.poster}
                                alt={`Affiche de ${np.title}`}
                                className="aspect-[2/3] w-full rounded-2xl object-cover shadow-2xl ring-1 ring-white/15"
                            />
                        ) : (
                            <div className="flex aspect-[2/3] w-full items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/25 to-fuchsia-500/10 ring-1 ring-white/10">
                                <Film className="h-10 w-10 text-violet-300" />
                            </div>
                        )}
                    </TiltCard>
                </div>

                <div className="flex min-w-0 flex-col gap-4">
                    {/* Ligne d'état */}
                    <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-300">
                        <Equalizer paused={!!np.paused} />
                        {np.paused ? "En pause" : "En lecture"}
                        {np.kodi && <span className="truncate font-medium normal-case tracking-normal text-muted-foreground">· {np.kodi}</span>}
                    </p>

                    <div>
                        <h2 className="text-balance text-2xl font-bold leading-tight tracking-tight md:text-4xl">{np.title || "Lecture en cours"}</h2>
                        {np.subtitle && <p className="mt-1 text-sm font-medium text-muted-foreground">{np.subtitle}</p>}
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {np.year && <span>{np.year}</span>}
                            {np.runtime && (
                                <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" /> {np.runtime} min
                                </span>
                            )}
                            {np.rating ? (
                                <span className="flex items-center gap-1 text-amber-300">
                                    <Star className="h-3 w-3 fill-current" /> {np.rating.toLocaleString("fr-FR")}
                                </span>
                            ) : null}
                            {np.genres?.slice(0, 3).map((g) => (
                                <span key={g} className="rounded-full bg-white/[0.06] px-2 py-0.5">
                                    {g}
                                </span>
                            ))}
                        </div>
                    </div>

                    {np.overview && <p className="line-clamp-2 max-w-3xl text-sm leading-relaxed text-muted-foreground md:line-clamp-3">{np.overview}</p>}

                    {(techBadges.length > 0 || !!np.subtitle_count) && (
                        <div className="flex flex-wrap gap-1.5">
                            {techBadges.map((b) => (
                                <span
                                    key={b}
                                    className="rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide text-foreground/85 backdrop-blur"
                                >
                                    {b}
                                </span>
                            ))}
                            {!!np.subtitle_count && (
                                <span className="flex items-center gap-1 rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 text-[10px] font-semibold text-foreground/85">
                                    <Subtitles className="h-3 w-3" /> {np.subtitle_count} ST
                                </span>
                            )}
                        </div>
                    )}

                    {/* Progression (seekable) */}
                    <div className="space-y-1.5">
                        <RangeSlider
                            value={total > 0 ? Math.round(shownPos) : Math.round(pct)}
                            max={total > 0 ? total : 100}
                            step={1}
                            tone="violet"
                            disabled={total <= 0}
                            ariaLabel="Position de lecture"
                            ariaValueText={`${formatClock(shownPos)} sur ${formatClock(total)}`}
                            bubble={(v) => formatClock(v)}
                            onChange={(v) => setSeeking(v)}
                            onCommit={(v) => {
                                setSeeking(null);
                                seekTo(v);
                            }}
                        />
                        <div className="flex justify-between text-[11px] tabular-nums text-muted-foreground">
                            <span>{formatClock(shownPos)}</span>
                            <span>−{formatClock(remaining)}</span>
                        </div>
                    </div>

                    {/* Commandes */}
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-1.5">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="rounded-full"
                                onClick={() => seekTo(shownPos - 10)}
                                disabled={total <= 0}
                                aria-label="Reculer de 10 secondes"
                            >
                                <RotateCcw />
                            </Button>
                            <motion.button
                                whileTap={{ scale: 0.9 }}
                                transition={SPRING}
                                onClick={() => send({ action: "playpause" }, { paused: !np.paused })}
                                aria-label={np.paused ? "Reprendre la lecture" : "Mettre en pause"}
                                className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-[0_0_32px_-4px_rgb(168_85_247/0.85)] transition-[filter] hover:brightness-110"
                            >
                                <AnimatePresence mode="wait" initial={false}>
                                    <motion.span
                                        key={np.paused ? "play" : "pause"}
                                        initial={{ scale: 0.5, opacity: 0, rotate: -30 }}
                                        animate={{ scale: 1, opacity: 1, rotate: 0 }}
                                        exit={{ scale: 0.5, opacity: 0 }}
                                        transition={{ duration: 0.18 }}
                                    >
                                        {np.paused ? <Play className="h-6 w-6 translate-x-0.5 fill-current" /> : <Pause className="h-6 w-6 fill-current" />}
                                    </motion.span>
                                </AnimatePresence>
                            </motion.button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="rounded-full"
                                onClick={() => seekTo(shownPos + 30)}
                                disabled={total <= 0}
                                aria-label="Avancer de 30 secondes"
                            >
                                <RotateCw />
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="rounded-full text-muted-foreground hover:text-red-300"
                                onClick={() => send({ action: "stop" })}
                                aria-label="Arrêter la lecture"
                            >
                                <Square className="fill-current" />
                            </Button>
                        </div>

                        {/* Volume Kodi */}
                        <div className="flex min-w-[180px] flex-1 items-center gap-2 sm:max-w-[260px]">
                            <Button
                                variant="ghost"
                                size="icon-sm"
                                className={cn("rounded-full", np.muted && "bg-red-500/10 text-red-400")}
                                onClick={() => send({ action: "mute" }, { muted: !np.muted })}
                                aria-label={np.muted ? "Réactiver le son" : "Couper le son"}
                                aria-pressed={!!np.muted}
                            >
                                {np.muted ? <VolumeX /> : <Volume2 />}
                            </Button>
                            <RangeSlider
                                size="sm"
                                value={shownVol}
                                tone="violet"
                                ariaLabel="Volume de Kodi"
                                ariaValueText={np.muted && vol === null ? "Sourdine" : `${shownVol} %`}
                                bubble={(v) => `${v} %`}
                                onChange={setVol}
                                onCommit={(v) => {
                                    setVol(null);
                                    send({ action: "volume", value: v }, { volume: v, muted: false });
                                    // Régler le volume en sourdine = vouloir entendre : on la retire.
                                    if (np.muted)
                                        control.mutate(
                                            { action: "mute" },
                                            { onError: (e) => toast.error("Sourdine non retirée", { description: e.message }) },
                                        );
                                }}
                            />
                            <span className="w-8 text-right text-[11px] tabular-nums text-muted-foreground">
                                {np.muted && vol === null ? "—" : shownVol}
                            </span>
                        </div>

                        {href && (
                            <Button asChild variant="outline" size="sm" className="ml-auto">
                                <Link href={href}>
                                    Voir la fiche <ArrowUpRight />
                                </Link>
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Barre de progression lumineuse en bas de carte */}
            <div className="relative h-[3px] bg-white/[0.06]">
                <motion.div
                    className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-400 shadow-[0_0_14px_rgb(217_70_239/0.8)]"
                    animate={{ width: `${Math.min(100, pct)}%` }}
                    transition={{ duration: 0.9, ease: "linear" }}
                />
            </div>
        </HeroShell>
    );
}

/** Égaliseur animé (immobile en pause). */
function Equalizer({ paused }: { paused: boolean }) {
    return (
        <span aria-hidden className="flex h-3 items-end gap-[2px]">
            {[0, 1, 2, 3].map((i) => (
                <motion.span
                    key={i}
                    className="w-[3px] rounded-full bg-violet-400"
                    animate={paused ? { height: 3 } : { height: [3, 12, 5, 10, 3] }}
                    transition={paused ? { duration: 0.3 } : { duration: 1.1, repeat: Infinity, delay: i * 0.13, ease: "easeInOut" }}
                />
            ))}
        </span>
    );
}
