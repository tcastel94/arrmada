"use client";

/**
 * Cast (Chromecast / Google Cast) d'un film ou d'un épisode via Jellyfin.
 * ----------------------------------------------------------------
 * - `CastDialog` : la boîte de choix d'appareil, contrôlable de l'extérieur
 *   (utilisée par le bouton « Lire » scindé de la fiche média).
 * - `CastButton` : bouton autonome « Caster » + boîte (rétro-compatible).
 *
 * Corrigé : avant, `play.isPending` était partagé par tous les appareils →
 * un spinner tournait sur CHAQUE ligne. L'état « en cours » est maintenant
 * suivi par appareil, et chaque commande affiche un toast en cas d'échec.
 */
import { useState } from "react";
import { toast } from "sonner";
import { AnimatePresence, motion } from "framer-motion";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Cast, Tv, Speaker, Loader2, Radar, Pause, Play, Square, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { StatusDot } from "@/components/fx/status-dot";
import { EASE_OUT } from "@/lib/motion";
import {
    useCastDevices,
    useCastDiscover,
    useCastPlay,
    useCastControl,
    type CastDevice,
} from "@/hooks/use-cast";

/** Épisode à caster : TVDB de la série + numéros (Jellyfin retrouve le fichier). */
export interface CastEpisode {
    tvdbId: number;
    season: number;
    episode: number;
}

interface CastTarget {
    /** Film (TMDB). Ignoré quand `episode` est donné. */
    tmdbId?: number;
    episode?: CastEpisode;
    mediaId?: string;
    title?: string;
}

export function CastDialog({
    open,
    onOpenChange,
    tmdbId,
    episode,
    mediaId,
    title,
}: CastTarget & { open: boolean; onOpenChange: (open: boolean) => void }) {
    const [castingOn, setCastingOn] = useState<CastDevice | null>(null);
    // Appareil sur lequel un lancement est en cours (spinner sur CETTE ligne seulement).
    const [pendingId, setPendingId] = useState<number | null>(null);
    const { data: devices, isLoading, isError, error, refetch } = useCastDevices();
    const discover = useCastDiscover();
    const play = useCastPlay();
    const control = useCastControl();

    const video = (devices ?? []).filter((d) => d.video_capable);
    const audio = (devices ?? []).filter((d) => !d.video_capable);

    const castTo = (d: CastDevice) => {
        // Épisode : la série (TVDB) et les numéros ; film : son TMDB
        const target = episode
            ? { tvdb_id: episode.tvdbId, season: episode.season, episode: episode.episode }
            : tmdbId
              ? { tmdb_id: tmdbId }
              : null;
        if (!target) return;
        setPendingId(d.id);
        play.mutate(
            { ...target, device_id: d.id, media_id: mediaId, title },
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
                onSettled: () => setPendingId(null),
            },
        );
    };

    const doControl = (action: "pause" | "play" | "stop") => {
        if (!castingOn) return;
        control.mutate(
            { device_id: castingOn.id, action },
            {
                onSuccess: (r) => {
                    if (r.status === "error") {
                        toast.error("Commande refusée", { description: r.detail });
                        return;
                    }
                    if (action === "stop") setCastingOn(null);
                },
                onError: (e) => toast.error("Commande échouée", { description: e.message }),
            },
        );
    };

    const scan = () =>
        discover.mutate(undefined, {
            onSuccess: (list) =>
                toast.success(
                    list.length > 0 ? `${list.length} appareil${list.length > 1 ? "s" : ""} détecté${list.length > 1 ? "s" : ""}` : "Aucun appareil détecté",
                ),
            onError: (e) => toast.error("Scan du réseau échoué", { description: e.message }),
        });

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <Cast className="h-4 w-4" />
                        </span>
                        Caster sur un appareil
                    </DialogTitle>
                    <DialogDescription>
                        {title && <span className="block truncate font-medium text-foreground">{title}</span>}
                        La lecture passe par Jellyfin (transcodage à la volée) pour rester compatible Chromecast.
                    </DialogDescription>
                </DialogHeader>

                {/* Télécommande du cast en cours */}
                <AnimatePresence initial={false}>
                    {castingOn && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3, ease: EASE_OUT }}
                            className="overflow-hidden"
                        >
                            <div className="glass rounded-2xl p-3">
                                <p className="flex items-center gap-2 text-sm font-medium">
                                    <StatusDot tone="brand" />
                                    En cours sur {castingOn.name}
                                </p>
                                <div className="mt-2.5 flex items-center gap-2">
                                    <Button size="icon-sm" variant="outline" aria-label="Reprendre la lecture" onClick={() => doControl("play")}>
                                        <Play />
                                    </Button>
                                    <Button size="icon-sm" variant="outline" aria-label="Mettre en pause" onClick={() => doControl("pause")}>
                                        <Pause />
                                    </Button>
                                    <Button size="sm" variant="destructive" onClick={() => doControl("stop")}>
                                        <Square /> Arrêter
                                    </Button>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <div className="max-h-[50vh] space-y-2 overflow-y-auto">
                    {isLoading ? (
                        <div className="space-y-2">
                            <Shimmer className="h-14 w-full" />
                            <Shimmer className="h-14 w-full" />
                        </div>
                    ) : isError ? (
                        <ErrorState compact error={error} onRetry={() => refetch()} title="Appareils indisponibles" />
                    ) : (devices?.length ?? 0) === 0 ? (
                        <EmptyState
                            compact
                            icon={Radar}
                            title="Aucun appareil Cast enregistré"
                            description="Lance un scan : les Chromecast et TV compatibles de ton réseau seront détectés."
                            action={{ label: discover.isPending ? "Scan en cours…" : "Scanner le réseau", onClick: scan }}
                        />
                    ) : (
                        <>
                            {video.map((d) => {
                                const pending = pendingId === d.id;
                                const active = castingOn?.id === d.id;
                                return (
                                    <button
                                        key={d.id}
                                        type="button"
                                        onClick={() => castTo(d)}
                                        disabled={pendingId !== null}
                                        className={cn(
                                            "glass glass-hover flex w-full items-center gap-3 rounded-xl p-3 text-left transition-opacity disabled:opacity-60",
                                            active && "border-sky-400/40",
                                        )}
                                    >
                                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                            <Tv className="h-4 w-4" />
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <span className="block truncate text-sm font-medium">{d.name}</span>
                                            <span className="block truncate text-[11px] text-muted-foreground">{d.model ?? "Google Cast"}</span>
                                        </span>
                                        {pending ? (
                                            <Loader2 className="h-4 w-4 animate-spin text-primary" aria-label="Lancement en cours" />
                                        ) : active ? (
                                            <Check className="h-4 w-4 text-success" aria-label="Cast en cours" />
                                        ) : (
                                            <Cast className="h-4 w-4 text-muted-foreground" aria-hidden />
                                        )}
                                    </button>
                                );
                            })}
                            {audio.length > 0 && (
                                <div className="pt-1">
                                    <p className="eyebrow mb-1.5 px-1">Audio uniquement (pas de vidéo)</p>
                                    {audio.map((d) => (
                                        <div key={d.id} className="flex items-center gap-3 rounded-xl px-3 py-2 text-muted-foreground/70">
                                            <Speaker className="h-4 w-4 shrink-0" aria-hidden />
                                            <span className="truncate text-sm">{d.name}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div className="flex justify-end pt-1">
                                <Button size="sm" variant="ghost" className="text-muted-foreground" disabled={discover.isPending} onClick={scan}>
                                    {discover.isPending ? <Loader2 className="animate-spin" /> : <Radar />}
                                    Re-scanner
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

export function CastButton({
    tmdbId,
    mediaId,
    title,
    className,
    variant = "outline",
    size,
}: CastTarget & {
    className?: string;
    variant?: ButtonProps["variant"];
    size?: ButtonProps["size"];
}) {
    const [open, setOpen] = useState(false);
    return (
        <>
            <Button variant={variant} size={size} className={className} onClick={() => setOpen(true)}>
                <Cast />
                Caster
            </Button>
            <CastDialog open={open} onOpenChange={setOpen} tmdbId={tmdbId} mediaId={mediaId} title={title} />
        </>
    );
}
