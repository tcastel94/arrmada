"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Power, Volume2, VolumeX, Minus, Plus, Speaker } from "lucide-react";
import { cn } from "@/lib/utils";
import {
    useYamahaState,
    useYamahaControl,
    useYamahaInputs,
    type YamahaDevice,
} from "@/hooks/use-yamaha";

/** Human labels for the common Yamaha input ids. */
const INPUT_LABELS: Record<string, string> = {
    hdmi1: "HDMI 1", hdmi2: "HDMI 2", hdmi3: "HDMI 3", hdmi4: "HDMI 4",
    hdmi5: "HDMI 5", hdmi6: "HDMI 6", hdmi7: "HDMI 7",
    av1: "AV 1", av2: "AV 2", av3: "AV 3", av4: "AV 4",
    audio1: "Audio 1", audio2: "Audio 2", audio3: "Audio 3",
    tuner: "Tuner", bluetooth: "Bluetooth", airplay: "AirPlay",
    spotify: "Spotify", net_radio: "Net Radio", server: "Serveur", usb: "USB",
    tv: "TV", phono: "Phono",
};

const inputLabel = (id?: string) => (id ? INPUT_LABELS[id] ?? id.toUpperCase() : "—");

function DeviceControl({ device }: { device: YamahaDevice }) {
    const control = useYamahaControl();
    const { data: inputs } = useYamahaInputs(device.id, device.online);

    const max = device.max_volume ?? 161;
    const [localVol, setLocalVol] = useState<number>(device.volume ?? 0);
    const dragging = useRef(false);
    const sendTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Keep the slider in sync with the device unless the user is dragging it.
    useEffect(() => {
        if (!dragging.current) setLocalVol(device.volume ?? 0);
    }, [device.volume]);

    const sendVolume = (v: number) => {
        if (sendTimer.current) clearTimeout(sendTimer.current);
        sendTimer.current = setTimeout(() => {
            control.mutate({ action: "volume", value: v, service_id: device.id });
        }, 200);
    };

    const on = device.power === "on";
    const db = device.actual_db;

    // Union of the API's input list and the current input, so the active one always shows.
    const inputOptions = Array.from(
        new Set([...(inputs ?? []), device.input].filter(Boolean) as string[])
    );

    return (
        <div className="space-y-3">
            {/* Header row */}
            <div className="flex items-center gap-2">
                <Speaker className="h-4 w-4 text-orange-400 shrink-0" />
                <span className="text-sm font-semibold truncate">{device.name}</span>
                {device.online ? (
                    <Badge className={cn("border-0 text-[10px]", on ? "bg-emerald-600/20 text-emerald-300" : "bg-muted/40 text-muted-foreground")}>
                        {on ? "Allumé" : "Veille"}
                    </Badge>
                ) : (
                    <Badge className="border-0 bg-red-500/20 text-[10px] text-red-300">Hors ligne</Badge>
                )}
                <div className="flex-1" />
                <Button
                    size="icon"
                    variant="ghost"
                    className={cn("h-8 w-8", on ? "text-emerald-400" : "text-muted-foreground")}
                    title={on ? "Mettre en veille" : "Allumer"}
                    disabled={!device.online}
                    onClick={() => control.mutate({ action: "power", value: on ? "standby" : "on", service_id: device.id })}
                >
                    <Power className="h-4 w-4" />
                </Button>
            </div>

            {/* Volume */}
            <div className={cn("space-y-1.5", (!device.online || !on) && "opacity-50 pointer-events-none")}>
                <div className="flex items-center gap-2">
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        title="Baisser"
                        onClick={() => control.mutate({ action: "volume_step", value: -5, service_id: device.id })}
                    >
                        <Minus className="h-4 w-4" />
                    </Button>

                    <Button
                        size="icon"
                        variant="ghost"
                        className={cn("h-7 w-7 shrink-0", device.mute && "text-red-400")}
                        title={device.mute ? "Réactiver le son" : "Couper le son"}
                        onClick={() => control.mutate({ action: "mute", value: !device.mute, service_id: device.id })}
                    >
                        {device.mute ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    </Button>

                    <input
                        type="range"
                        min={0}
                        max={max}
                        value={localVol}
                        onPointerDown={() => (dragging.current = true)}
                        onPointerUp={() => (dragging.current = false)}
                        onChange={(e) => {
                            const v = Number(e.target.value);
                            setLocalVol(v);
                            sendVolume(v);
                        }}
                        className="flex-1 accent-orange-500 h-1.5 cursor-pointer"
                    />

                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        title="Monter"
                        onClick={() => control.mutate({ action: "volume_step", value: 5, service_id: device.id })}
                    >
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
                <div className="flex items-center justify-between px-1 text-[11px] text-muted-foreground tabular-nums">
                    <span>{Math.round((localVol / max) * 100)}%</span>
                    {db !== null && db !== undefined && <span>{db > 0 ? `+${db}` : db} dB</span>}
                </div>
            </div>

            {/* Input */}
            {device.online && inputOptions.length > 0 && (
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground shrink-0">Entrée</span>
                    <Select
                        value={device.input ?? undefined}
                        onValueChange={(v) => control.mutate({ action: "input", value: v, service_id: device.id })}
                    >
                        <SelectTrigger className="h-8 border-white/10 bg-transparent text-xs">
                            <SelectValue placeholder={inputLabel(device.input)} />
                        </SelectTrigger>
                        <SelectContent className="max-h-72">
                            {inputOptions.map((i) => (
                                <SelectItem key={i} value={i}>{inputLabel(i)}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}
        </div>
    );
}

/**
 * AVR control panel. Renders one control block per configured Yamaha device.
 * `enabled` gates the polling (pass false when off-screen). `card` wraps it in
 * a styled Card (default); pass card={false} to embed raw.
 */
export function YamahaRemote({ enabled = true, card = true }: { enabled?: boolean; card?: boolean }) {
    const { data } = useYamahaState(enabled);
    const devices = data?.devices ?? [];
    if (devices.length === 0) return null;

    const body = (
        <div className="space-y-4">
            {devices.map((d, i) => (
                <div key={d.id} className={cn(i > 0 && "border-t border-white/5 pt-4")}>
                    <DeviceControl device={d} />
                </div>
            ))}
        </div>
    );

    if (!card) return body;

    return (
        <Card className="border-0 ring-1 ring-orange-500/20 bg-gradient-to-br from-orange-950/20 to-card/40">
            <CardContent className="p-4">{body}</CardContent>
        </Card>
    );
}
