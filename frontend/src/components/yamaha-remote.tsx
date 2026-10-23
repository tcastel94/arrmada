"use client";

/**
 * Télécommande de l'ampli Yamaha (MusicCast / YamahaExtendedControl).
 * ----------------------------------------------------------------
 * Deux présentations :
 *  - `variant="full"`    : grand cadran de volume, gros bouton marche,
 *                          entrées en pastilles → page Salon (/remote) ;
 *  - `variant="compact"` : une ligne volume + liste d'entrées → fiche
 *                          média, pendant une lecture (valeur par défaut,
 *                          pour ne rien casser chez les appelants existants).
 * Les commandes sont OPTIMISTES (cf. useYamahaControl) : l'interface
 * réagit tout de suite, et revient en arrière si l'ampli refuse.
 * L'état réel est relu toutes les 4 s.
 *
 * Préréglages par pièce (Salon / Cinéma) : un clic applique le profil
 * enregistré dans Paramètres → Ampli Yamaha (allumage, source, programme
 * sonore, volume, voix…). Si Kodi lit quelque chose, on transmet le type
 * de média et le format audio pour que le backend choisisse le bon
 * programme (série ≠ film ≠ musique).
 * Variante complète : un volet « Réglages du son » (replié par défaut,
 * pour ne pas surcharger) donne aussi le programme sonore et le
 * rehaussement des voix à la volée.
 */
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Loader2, Minus, Plus, Power, SlidersHorizontal, Speaker, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RingGauge } from "@/components/fx/ring-gauge";
import { StatusDot } from "@/components/fx/status-dot";
import { Label } from "@/components/ui/label";
import { RangeSlider } from "@/components/remote/range-slider";
import { StepPicker } from "@/components/remote/step-picker";
import { SoundProgramSelect } from "@/components/remote/sound-program-select";
import {
    ROOMS,
    ROOM_META,
    describeApplied,
    presetContext,
    programFor,
    soundProgramShortLabel,
    volumePct,
} from "@/components/remote/yamaha-audio";
import { EASE_OUT, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useKodiNowPlaying } from "@/hooks/use-kodi";
import {
    useApplyYamahaPreset,
    useYamahaState,
    useYamahaControl,
    useYamahaInputs,
    useYamahaProfiles,
    type YamahaControlVars,
    type YamahaDevice,
    type YamahaPresetApplied,
    type YamahaRoom,
} from "@/hooks/use-yamaha";

/** Libellés lisibles des identifiants d'entrée Yamaha. */
const INPUT_LABELS: Record<string, string> = {
    hdmi1: "HDMI 1", hdmi2: "HDMI 2", hdmi3: "HDMI 3", hdmi4: "HDMI 4",
    hdmi5: "HDMI 5", hdmi6: "HDMI 6", hdmi7: "HDMI 7",
    av1: "AV 1", av2: "AV 2", av3: "AV 3", av4: "AV 4",
    audio1: "Audio 1", audio2: "Audio 2", audio3: "Audio 3",
    tuner: "Tuner", bluetooth: "Bluetooth", airplay: "AirPlay",
    spotify: "Spotify", net_radio: "Radio web", server: "Serveur", usb: "USB",
    tv: "TV", phono: "Phono", optical: "Optique", coaxial: "Coaxial",
};

export const inputLabel = (id?: string) => (id ? INPUT_LABELS[id] ?? id.replace(/_/g, " ").toUpperCase() : "—");

/** Valeur dB lisible : « −32,5 dB ». */
function formatDb(db: number | null | undefined): string | null {
    if (db === null || db === undefined) return null;
    const v = db.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
    return `${db > 0 ? "+" : ""}${v} dB`;
}

/**
 * Logique commune aux deux variantes : envoi des commandes (avec toast
 * d'erreur) et volume local pendant le glissement du curseur.
 */
function useDeviceControls(device: YamahaDevice) {
    const control = useYamahaControl();
    const max = device.max_volume ?? 161;
    const [localVol, setLocalVol] = useState<number>(device.volume ?? 0);
    const dragging = useRef(false);

    // Suit l'état réel de l'ampli, sauf pendant que l'utilisateur fait glisser.
    useEffect(() => {
        if (!dragging.current) setLocalVol(device.volume ?? 0);
    }, [device.volume]);

    /** `onError` : pour annuler un état local (ex: niveau de voix affiché). */
    const send = (vars: Omit<YamahaControlVars, "service_id">, opts?: { onError?: () => void }) =>
        control.mutate(
            { ...vars, service_id: device.id },
            {
                onError: (e) => {
                    opts?.onError?.();
                    toast.error(`${device.name} : commande refusée`, { description: e.message });
                },
            },
        );

    return {
        max,
        localVol,
        pct: Math.round((localVol / max) * 100),
        on: device.power === "on",
        send,
        onSlide: (v: number) => {
            dragging.current = true;
            setLocalVol(v);
        },
        onCommit: (v: number) => {
            dragging.current = false;
            send({ action: "volume", value: v });
        },
    };
}

/** Liste des entrées : celles annoncées par l'ampli + l'entrée active. */
function useInputOptions(device: YamahaDevice) {
    const { data: inputs } = useYamahaInputs(device.id, device.online);
    return Array.from(new Set([...(inputs ?? []), device.input].filter(Boolean) as string[]));
}

/**
 * Application d'un préréglage de pièce, avec toast et état par bouton.
 * `onApplied` reçoit ce que l'ampli a réellement reçu (ex: niveau de voix).
 */
function usePresets(device: YamahaDevice, onApplied?: (applied: YamahaPresetApplied) => void) {
    const apply = useApplyYamahaPreset();
    const { data: profiles } = useYamahaProfiles();
    // Lecture PASSIVE (enabled=false) : on lit l'état Kodi déjà en cache,
    // rafraîchi par le lecteur du Salon ou de la fiche média, sans lancer
    // de requêtes supplémentaires.
    const { data: nowPlaying } = useKodiNowPlaying(false);
    const context = presetContext(nowPlaying);
    const [pending, setPending] = useState<YamahaRoom | null>(null);
    const [done, setDone] = useState<YamahaRoom | null>(null);

    // Coche de confirmation éphémère sur le bouton utilisé.
    useEffect(() => {
        if (!done) return;
        const t = window.setTimeout(() => setDone(null), 2500);
        return () => window.clearTimeout(t);
    }, [done]);

    const run = (room: YamahaRoom) => {
        const label = ROOM_META[room].short;
        setPending(room);
        apply.mutate(
            { room, service_id: device.id, ...context?.vars },
            {
                onSuccess: (res) => {
                    toast.success(`Préréglage ${label} appliqué`, { description: describeApplied(res.applied, inputLabel) });
                    if (res.applied) onApplied?.(res.applied);
                    setDone(room);
                },
                onError: (e) => toast.error(`Préréglage ${label} : échec`, { description: e.message }),
                onSettled: () => setPending(null),
            },
        );
    };

    return { run, pending, done, context, profiles };
}

/** Deux tuiles « Salon » / « Cinéma » avec un aperçu de ce qui sera appliqué. */
function PresetTiles({ device, onApplied }: { device: YamahaDevice; onApplied?: (applied: YamahaPresetApplied) => void }) {
    const { run, pending, done, context, profiles } = usePresets(device, onApplied);

    return (
        <div className="space-y-2">
            <div className="flex items-baseline justify-between gap-3">
                <p className="eyebrow shrink-0">Préréglages</p>
                {context && (
                    <p className="truncate text-[11px] text-muted-foreground" title="Le programme sonore suit ce que Kodi lit en ce moment">
                        Adapté à : {context.label}
                    </p>
                )}
            </div>
            <div className="grid grid-cols-2 gap-2">
                {ROOMS.map((room) => {
                    const meta = ROOM_META[room];
                    const Icon = meta.icon;
                    const profile = profiles?.[room];
                    const summary = profile
                        ? `${soundProgramShortLabel(programFor(profile, context?.kind ?? null))} · ${volumePct(profile.volume_raw)} %`
                        : "Profil enregistré";
                    const busy = pending === room;
                    return (
                        <motion.button
                            key={room}
                            type="button"
                            whileTap={{ scale: 0.97 }}
                            onClick={() => run(room)}
                            disabled={!device.online || pending !== null}
                            title={`Appliquer le préréglage ${meta.label} (${summary})`}
                            className="glass glass-hover flex min-w-0 items-center gap-2.5 rounded-xl p-2.5 text-left transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ring-1", meta.tile)}>
                                {busy ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : done === room ? (
                                    <Check className="h-4 w-4 text-success" />
                                ) : (
                                    <Icon className="h-4 w-4" />
                                )}
                            </span>
                            <span className="min-w-0">
                                <span className="block truncate text-sm font-semibold">
                                    <span className="sr-only">Préréglage </span>
                                    {meta.short}
                                </span>
                                <span className="block truncate text-[11px] text-muted-foreground">{summary}</span>
                            </span>
                        </motion.button>
                    );
                })}
            </div>
        </div>
    );
}

/**
 * Volet repliable « Réglages du son » : programme sonore et rehaussement
 * des voix. Replié par défaut pour garder la télécommande lisible.
 */
function SoundSettings({
    device,
    voice,
    onVoiceChange,
    onProgramChange,
}: {
    device: YamahaDevice;
    voice: number | null;
    onVoiceChange: (value: number) => void;
    onProgramChange: (program: string) => void;
}) {
    const [open, setOpen] = useState(false);
    const panelId = `yamaha-sound-${device.id}`;

    return (
        <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02]">
            <button
                type="button"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() => setOpen((o) => !o)}
                className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm font-medium transition-colors hover:bg-white/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/60"
            >
                <SlidersHorizontal className="h-4 w-4 shrink-0 text-orange-300" />
                <span className="shrink-0">Réglages du son</span>
                <span className="ml-auto min-w-0 truncate text-xs text-muted-foreground">{soundProgramShortLabel(device.sound_program)}</span>
                <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300", open && "rotate-180")} />
            </button>
            <AnimatePresence initial={false}>
                {open && (
                    <motion.div
                        id={panelId}
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: EASE_OUT }}
                    >
                        <div className="space-y-4 border-t border-white/[0.06] px-3.5 py-3.5">
                            <div className="space-y-1.5">
                                <Label htmlFor={`${panelId}-program`} className="text-xs">
                                    Programme sonore
                                </Label>
                                <SoundProgramSelect id={`${panelId}-program`} size="sm" value={device.sound_program} onChange={onProgramChange} />
                            </div>
                            <div className="space-y-1.5">
                                <p id={`${panelId}-voice`} className="text-xs font-medium">
                                    Rehaussement des voix
                                </p>
                                <StepPicker
                                    layoutId={`yamaha-voice-${device.id}`}
                                    ariaLabelledBy={`${panelId}-voice`}
                                    ariaDescribedBy={`${panelId}-voice-hint`}
                                    value={voice}
                                    max={5}
                                    onChange={onVoiceChange}
                                />
                                <p id={`${panelId}-voice-hint`} className="text-[11px] leading-relaxed text-muted-foreground">
                                    {voice === null
                                        ? "L'ampli ne communique pas ce réglage : choisis un niveau pour l'imposer."
                                        : "Remonte les voix vers l'écran quand les enceintes sont basses."}
                                </p>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/* ── Variante complète (Salon) ─────────────────────────────── */

function FullDeviceControl({ device }: { device: YamahaDevice }) {
    const { max, localVol, pct, on, send, onSlide, onCommit } = useDeviceControls(device);
    const inputs = useInputOptions(device);
    const live = device.online && on;
    const db = formatDb(device.actual_db);
    // L'état de l'ampli ne remonte pas le niveau de voix : on affiche le
    // dernier envoyé d'ici (réglage direct ou préréglage), sinon « inconnu ».
    const [voice, setVoice] = useState<number | null>(null);

    const changeVoice = (value: number) => {
        const previous = voice;
        setVoice(value);
        send({ action: "dialog_lift", value }, { onError: () => setVoice(previous) });
    };

    return (
        <div className="space-y-5">
            {/* En-tête : nom, état, bouton marche */}
            <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500/30 to-amber-500/10 text-orange-300 ring-1 ring-orange-400/25">
                    <Speaker className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{device.name}</p>
                    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <StatusDot tone={!device.online ? "offline" : on ? "online" : "unknown"} size="sm" />
                        {!device.online ? "Hors ligne" : on ? "Allumé" : "En veille"}
                        {live && device.sound_program && (
                            <span className="truncate text-muted-foreground/70">· {soundProgramShortLabel(device.sound_program)}</span>
                        )}
                    </p>
                </div>
                <motion.button
                    whileTap={{ scale: 0.9 }}
                    disabled={!device.online}
                    onClick={() => send({ action: "power", value: on ? "standby" : "on" })}
                    aria-label={on ? `Mettre ${device.name} en veille` : `Allumer ${device.name}`}
                    aria-pressed={on}
                    className={cn(
                        "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-all duration-300 disabled:opacity-40",
                        on
                            ? "border-success/40 bg-success/15 text-success"
                            : "border-white/10 bg-white/[0.04] text-muted-foreground hover:text-foreground",
                    )}
                >
                    <Power className="h-5 w-5" />
                </motion.button>
            </div>

            {!device.online ? (
                <p className="rounded-xl border border-destructive/20 bg-destructive/[0.07] px-3.5 py-3 text-xs text-destructive">
                    L&apos;ampli ne répond pas{device.error ? ` (${device.error})` : ""}. Vérifie qu&apos;il est branché au réseau.
                </p>
            ) : (
                <div className={cn("space-y-5 transition-opacity duration-300", !on && "pointer-events-none opacity-40")} aria-disabled={!on}>
                    {/* Cadran de volume */}
                    <div className="flex items-center justify-center gap-4 sm:gap-6">
                        <Button
                            variant="outline"
                            size="icon"
                            className="h-12 w-12 rounded-full"
                            onClick={() => send({ action: "volume_step", value: -5 })}
                            aria-label="Baisser le volume"
                        >
                            <Minus />
                        </Button>
                        <RingGauge value={device.mute ? 0 : pct} size={148} stroke={9} tone="amber">
                            <div className="text-center">
                                <motion.p
                                    key={device.mute ? "mute" : "vol"}
                                    initial={{ scale: 0.85, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    transition={SPRING}
                                    className="text-3xl font-bold tabular-nums"
                                >
                                    {device.mute ? <VolumeX className="mx-auto h-8 w-8 text-destructive" /> : `${pct}`}
                                </motion.p>
                                <p className="text-[11px] text-muted-foreground">{device.mute ? "Sourdine" : db ?? "%"}</p>
                            </div>
                        </RingGauge>
                        <Button
                            variant="outline"
                            size="icon"
                            className="h-12 w-12 rounded-full"
                            onClick={() => send({ action: "volume_step", value: 5 })}
                            aria-label="Monter le volume"
                        >
                            <Plus />
                        </Button>
                    </div>

                    <div className="flex items-center gap-3">
                        <Button
                            variant="ghost"
                            size="icon-sm"
                            className={cn(device.mute && "bg-destructive/10 text-destructive hover:text-destructive")}
                            onClick={() => send({ action: "mute", value: !device.mute })}
                            aria-label={device.mute ? "Réactiver le son" : "Couper le son"}
                            aria-pressed={!!device.mute}
                        >
                            {device.mute ? <VolumeX /> : <Volume2 />}
                        </Button>
                        <RangeSlider
                            value={localVol}
                            max={max}
                            onChange={onSlide}
                            onCommit={onCommit}
                            tone="orange"
                            ariaLabel={`Volume de ${device.name}`}
                            ariaValueText={`${pct} %`}
                            bubble={(v) => `${Math.round((v / max) * 100)} %`}
                        />
                    </div>

                    {/* Entrées */}
                    {inputs.length > 0 && (
                        <div className="space-y-2">
                            <p className="eyebrow">Source</p>
                            <div role="radiogroup" aria-label={`Entrée de ${device.name}`} className="flex flex-wrap gap-1.5">
                                {inputs.map((i) => {
                                    const active = i === device.input;
                                    return (
                                        <button
                                            key={i}
                                            role="radio"
                                            aria-checked={active}
                                            onClick={() => !active && send({ action: "input", value: i })}
                                            className={cn(
                                                "relative rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                                                active ? "text-warning" : "bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
                                            )}
                                        >
                                            {active && (
                                                <motion.span
                                                    layoutId={`yamaha-input-${device.id}`}
                                                    transition={SPRING}
                                                    className="absolute inset-0 rounded-full border border-warning/40 bg-warning/15"
                                                />
                                            )}
                                            <span className="relative">{inputLabel(i)}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {device.online && (
                <>
                    {/* Préréglages : actifs même en veille (le backend allume l'ampli). */}
                    <PresetTiles device={device} onApplied={(a) => a.dialog_lift !== undefined && setVoice(a.dialog_lift)} />
                    {on && (
                        <SoundSettings
                            device={device}
                            voice={voice}
                            onVoiceChange={changeVoice}
                            onProgramChange={(program) => send({ action: "sound_program", value: program })}
                        />
                    )}
                </>
            )}

            {device.online && !on && (
                <Button variant="glow" className="w-full" onClick={() => send({ action: "power", value: "on" })}>
                    <Power /> Allumer l&apos;ampli
                </Button>
            )}
        </div>
    );
}

/* ── Variante compacte (fiche média) ───────────────────────── */

function CompactDeviceControl({ device }: { device: YamahaDevice }) {
    const { max, localVol, pct, on, send, onSlide, onCommit } = useDeviceControls(device);
    const inputs = useInputOptions(device);
    const db = formatDb(device.actual_db);

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Speaker className="h-4 w-4 shrink-0 text-orange-400" />
                <span className="truncate text-sm font-semibold">{device.name}</span>
                <span
                    className={cn(
                        "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
                        !device.online ? "bg-destructive/15 text-destructive" : on ? "bg-success/15 text-success" : "bg-white/[0.06] text-muted-foreground",
                    )}
                >
                    {!device.online ? "Hors ligne" : on ? "Allumé" : "Veille"}
                </span>
                <div className="flex-1" />
                <Button
                    size="icon-sm"
                    variant="ghost"
                    className={cn(on ? "text-success" : "text-muted-foreground")}
                    aria-label={on ? "Mettre en veille" : "Allumer"}
                    aria-pressed={on}
                    disabled={!device.online}
                    onClick={() => send({ action: "power", value: on ? "standby" : "on" })}
                >
                    <Power />
                </Button>
            </div>

            <div className={cn("space-y-1", (!device.online || !on) && "pointer-events-none opacity-50")}>
                <div className="flex items-center gap-1.5">
                    <Button size="icon-sm" variant="ghost" aria-label="Baisser le volume" onClick={() => send({ action: "volume_step", value: -5 })}>
                        <Minus />
                    </Button>
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className={cn(device.mute && "text-destructive")}
                        aria-label={device.mute ? "Réactiver le son" : "Couper le son"}
                        aria-pressed={!!device.mute}
                        onClick={() => send({ action: "mute", value: !device.mute })}
                    >
                        {device.mute ? <VolumeX /> : <Volume2 />}
                    </Button>
                    <RangeSlider
                        size="sm"
                        value={localVol}
                        max={max}
                        onChange={onSlide}
                        onCommit={onCommit}
                        tone="orange"
                        ariaLabel={`Volume de ${device.name}`}
                        ariaValueText={`${pct} %`}
                        bubble={(v) => `${Math.round((v / max) * 100)} %`}
                    />
                    <Button size="icon-sm" variant="ghost" aria-label="Monter le volume" onClick={() => send({ action: "volume_step", value: 5 })}>
                        <Plus />
                    </Button>
                </div>
                <div className="flex items-center justify-between px-1 text-[11px] tabular-nums text-muted-foreground">
                    <span>{pct} %</span>
                    {db && <span>{db}</span>}
                </div>
            </div>

            {device.online && inputs.length > 0 && (
                <div className="flex items-center gap-2">
                    <span className="shrink-0 text-xs text-muted-foreground">Entrée</span>
                    <Select value={device.input ?? undefined} onValueChange={(v) => send({ action: "input", value: v })}>
                        <SelectTrigger className="h-8 text-xs" aria-label={`Entrée de ${device.name}`}>
                            <SelectValue placeholder={inputLabel(device.input)} />
                        </SelectTrigger>
                        <SelectContent className="max-h-72">
                            {inputs.map((i) => (
                                <SelectItem key={i} value={i}>
                                    {inputLabel(i)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}

            {device.online && <CompactPresets device={device} />}
        </div>
    );
}

/** Préréglages en version compacte : deux petits boutons sur une ligne. */
function CompactPresets({ device }: { device: YamahaDevice }) {
    const { run, pending, done, context } = usePresets(device);
    return (
        <div className="space-y-1">
            <div className="flex items-center gap-2">
                <span className="shrink-0 text-xs text-muted-foreground">Préréglage</span>
                {ROOMS.map((room) => {
                    const meta = ROOM_META[room];
                    const Icon = meta.icon;
                    return (
                        <Button
                            key={room}
                            variant="outline"
                            size="sm"
                            className="min-w-0 flex-1"
                            disabled={pending !== null}
                            onClick={() => run(room)}
                            aria-label={`Appliquer le préréglage ${meta.label}`}
                        >
                            {pending === room ? <Loader2 className="animate-spin" /> : done === room ? <Check className="text-success" /> : <Icon />}
                            <span className="truncate">{meta.short}</span>
                        </Button>
                    );
                })}
            </div>
            {context && <p className="truncate px-1 text-[11px] text-muted-foreground">Programme adapté à : {context.label}</p>}
        </div>
    );
}

/**
 * Télécommande : un bloc par ampli configuré. Ne rend rien s'il n'y a
 * aucun ampli (la page appelante gère son propre état « non configuré »).
 * `enabled` coupe l'interrogation (ex: composant hors écran) ; `card`
 * entoure le tout d'une carte en verre (par défaut).
 */
export function YamahaRemote({
    enabled = true,
    card = true,
    variant = "compact",
}: {
    enabled?: boolean;
    card?: boolean;
    variant?: "compact" | "full";
}) {
    const { data } = useYamahaState(enabled);
    const devices = data?.devices ?? [];
    if (devices.length === 0) return null;

    const Control = variant === "full" ? FullDeviceControl : CompactDeviceControl;
    const body = (
        <div className={variant === "full" ? "space-y-6" : "space-y-4"}>
            {devices.map((d, i) => (
                <div key={d.id} className={cn(i > 0 && "border-t border-white/[0.06] pt-5")}>
                    <Control device={d} />
                </div>
            ))}
        </div>
    );

    if (!card) return body;

    return (
        <div className="glass relative overflow-hidden rounded-2xl p-4">
            <div className="relative">{body}</div>
        </div>
    );
}
