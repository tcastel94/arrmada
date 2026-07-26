"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Cast,
    Tv,
    Speaker,
    Loader2,
    Radar,
    Pause,
    Play,
    Square,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    useCastDevices,
    useCastDiscover,
    useCastPlay,
    useCastControl,
    type CastDevice,
} from "@/hooks/use-cast";

export function CastButton({
    tmdbId,
    mediaId,
    title,
    className,
}: {
    tmdbId: number;
    mediaId?: string;
    title?: string;
    className?: string;
}) {
    const [open, setOpen] = useState(false);
    const [castingOn, setCastingOn] = useState<CastDevice | null>(null);
    const { data: devices, isLoading } = useCastDevices();
    const discover = useCastDiscover();
    const play = useCastPlay();
    const control = useCastControl();

    const video = (devices ?? []).filter((d) => d.video_capable);
    const audio = (devices ?? []).filter((d) => !d.video_capable);

    const castTo = (d: CastDevice) => {
        play.mutate(
            { tmdb_id: tmdbId, device_id: d.id, media_id: mediaId, title },
            {
                onSuccess: (r) => {
                    if (r.status === "casting") {
                        setCastingOn(d);
                        toast.success(`Cast lancé sur ${d.name}`, {
                            description: "Jellyfin transcode le flux — quelques secondes avant l'image.",
                        });
                    } else {
                        toast.error(`Cast impossible sur ${d.name}`, { description: r.detail });
                    }
                },
                onError: (e) => toast.error("Échec du cast", { description: e.message }),
            },
        );
    };

    const doControl = (action: "pause" | "play" | "stop") => {
        if (!castingOn) return;
        control.mutate(
            { device_id: castingOn.id, action },
            {
                onSuccess: () => {
                    if (action === "stop") setCastingOn(null);
                },
                onError: (e) => toast.error("Commande échouée", { description: e.message }),
            },
        );
    };

    return (
        <>
            <Button
                variant="outline"
                className={cn("gap-2 border-white/10", className)}
                onClick={() => setOpen(true)}
            >
                <Cast className="h-4 w-4" />
                Caster
            </Button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Cast className="h-5 w-5 text-sky-400" /> Caster sur un appareil
                        </DialogTitle>
                        <DialogDescription>
                            La lecture passe par Jellyfin (transcodage à la volée) pour être compatible Chromecast.
                        </DialogDescription>
                    </DialogHeader>

                    {/* Casting controls */}
                    {castingOn && (
                        <div className="rounded-lg border border-sky-500/30 bg-sky-500/5 p-3 space-y-2">
                            <p className="text-sm font-medium flex items-center gap-2">
                                <Cast className="h-4 w-4 text-sky-400 animate-pulse" />
                                En cours sur {castingOn.name}
                            </p>
                            <div className="flex items-center gap-2">
                                <Button size="sm" variant="secondary" onClick={() => doControl("play")}>
                                    <Play className="h-4 w-4" />
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => doControl("pause")}>
                                    <Pause className="h-4 w-4" />
                                </Button>
                                <Button size="sm" variant="destructive" onClick={() => doControl("stop")}>
                                    <Square className="h-4 w-4 mr-1" /> Arrêter
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="space-y-3 max-h-[50vh] overflow-y-auto">
                        {isLoading ? (
                            <div className="h-16 rounded-lg bg-muted/15 animate-pulse" />
                        ) : (devices?.length ?? 0) === 0 ? (
                            <div className="text-center py-6 space-y-3">
                                <p className="text-sm text-muted-foreground">Aucun appareil Cast enregistré.</p>
                                <Button
                                    variant="outline"
                                    className="border-white/10"
                                    disabled={discover.isPending}
                                    onClick={() =>
                                        discover.mutate(undefined, {
                                            onSuccess: (list) =>
                                                toast.success(`${list.length} appareil(s) détecté(s).`),
                                            onError: (e) => toast.error("Scan échoué", { description: e.message }),
                                        })
                                    }
                                >
                                    {discover.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Radar className="h-4 w-4 mr-2" />}
                                    Scanner le réseau
                                </Button>
                            </div>
                        ) : (
                            <>
                                {video.map((d) => (
                                    <button
                                        key={d.id}
                                        onClick={() => castTo(d)}
                                        disabled={play.isPending}
                                        className="w-full flex items-center gap-3 rounded-lg border border-white/10 bg-card/40 p-3 text-left transition-colors hover:bg-white/5 disabled:opacity-60"
                                    >
                                        <Tv className="h-5 w-5 text-sky-400 shrink-0" />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium truncate">{d.name}</p>
                                            <p className="text-[11px] text-muted-foreground truncate">{d.model ?? "Cast"}</p>
                                        </div>
                                        {play.isPending ? (
                                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                        ) : (
                                            <Cast className="h-4 w-4 text-muted-foreground" />
                                        )}
                                    </button>
                                ))}
                                {audio.length > 0 && (
                                    <div className="pt-1">
                                        <p className="text-[11px] text-muted-foreground/60 mb-1.5 px-1">Audio uniquement (pas de vidéo)</p>
                                        {audio.map((d) => (
                                            <div key={d.id} className="flex items-center gap-3 rounded-lg border border-white/5 p-2.5 opacity-50">
                                                <Speaker className="h-4 w-4 shrink-0" />
                                                <span className="text-sm truncate">{d.name}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <div className="flex justify-end pt-1">
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="text-muted-foreground gap-1.5"
                                        disabled={discover.isPending}
                                        onClick={() =>
                                            discover.mutate(undefined, {
                                                onSuccess: (list) => toast.success(`${list.length} appareil(s).`),
                                            })
                                        }
                                    >
                                        {discover.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Radar className="h-3.5 w-3.5" />}
                                        Re-scanner
                                    </Button>
                                </div>
                            </>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}
