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
 */
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Minus, Plus, Power, Speaker, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RingGauge } from "@/components/fx/ring-gauge";
import { StatusDot } from "@/components/fx/status-dot";
import { RangeSlider } from "@/components/remote/range-slider";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
    useYamahaState,
    useYamahaControl,
    useYamahaInputs,
    type YamahaControlVars,
    type YamahaDevice,
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

    const send = (vars: Omit<YamahaControlVars, "service_id">) =>
        control.mutate(
            { ...vars, service_id: device.id },
            { onError: (e) => toast.error(`${device.name} : commande refusée`, { description: e.message }) },
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

/* ── Variante complète (Salon) ─────────────────────────────── */

function FullDeviceControl({ device }: { device: YamahaDevice }) {
    const { max, localVol, pct, on, send, onSlide, onCommit } = useDeviceControls(device);
    const inputs = useInputOptions(device);
    const live = device.online && on;
    const db = formatDb(device.actual_db);

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
                            <span className="truncate text-muted-foreground/70">· {device.sound_program.replace(/_/g, " ")}</span>
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
                            ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-300 shadow-[0_0_28px_-4px_rgb(52_211_153/0.7)]"
                            : "border-white/10 bg-white/[0.04] text-muted-foreground hover:text-foreground",
                    )}
                >
                    <Power className="h-5 w-5" />
                </motion.button>
            </div>

            {!device.online ? (
                <p className="rounded-xl border border-red-500/20 bg-red-500/[0.07] px-3.5 py-3 text-xs text-red-300">
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
                                    {device.mute ? <VolumeX className="mx-auto h-8 w-8 text-red-400" /> : `${pct}`}
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
                            className={cn(device.mute && "bg-red-500/10 text-red-400 hover:text-red-300")}
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
                                                active ? "text-amber-200" : "bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
                                            )}
                                        >
                                            {active && (
                                                <motion.span
                                                    layoutId={`yamaha-input-${device.id}`}
                                                    transition={SPRING}
                                                    className="absolute inset-0 rounded-full border border-amber-400/40 bg-amber-500/15 shadow-[0_0_18px_-6px_rgb(251_191_36/0.8)]"
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
                        !device.online ? "bg-red-500/15 text-red-300" : on ? "bg-emerald-500/15 text-emerald-300" : "bg-white/[0.06] text-muted-foreground",
                    )}
                >
                    {!device.online ? "Hors ligne" : on ? "Allumé" : "Veille"}
                </span>
                <div className="flex-1" />
                <Button
                    size="icon-sm"
                    variant="ghost"
                    className={cn(on ? "text-emerald-400" : "text-muted-foreground")}
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
                        className={cn(device.mute && "text-red-400")}
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
            {/* Lueur ambrée discrète : identité visuelle « ampli » */}
            <div
                aria-hidden
                className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full opacity-30 blur-2xl"
                style={{ background: "radial-gradient(closest-side, hsl(32 95% 58% / 0.6), transparent)" }}
            />
            <div className="relative">{body}</div>
        </div>
    );
}
