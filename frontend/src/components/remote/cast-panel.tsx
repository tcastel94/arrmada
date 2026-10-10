"use client";

/**
 * Appareils Cast du Salon (Chromecast, Google TV, enceintes Nest).
 * ----------------------------------------------------------------
 * Liste des appareils connus + nouveau scan du réseau. Chaque appareil a
 * un bouton « Arrêter la diffusion » (commande `quit` : ferme l'appli en
 * cours sur le Chromecast, sans effet s'il ne diffuse rien).
 * On caste un film depuis sa fiche (bouton « Caster ») ; ici on supervise.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, Cast, Loader2, Radar, Settings2, Speaker, Square, Tv } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ScanPulse } from "@/components/settings/discovery-results";
import { useCastControl, useCastDevices, useCastDiscover, useJellyfinConfig, type CastDevice } from "@/hooks/use-cast";
import { plural } from "@/lib/format";
import { scaleIn, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function CastPanel() {
    const { data: devices, isLoading, isError, error, refetch } = useCastDevices();
    const { data: jellyfin } = useJellyfinConfig();
    const discover = useCastDiscover();

    const scan = () =>
        discover.mutate(undefined, {
            onSuccess: (list) =>
                list.length > 0
                    ? toast.success(plural(list.length, "appareil détecté", "appareils détectés"))
                    : toast.info("Aucun appareil Cast trouvé", { description: "Vérifie qu'ils sont allumés et sur le même réseau." }),
            onError: (e) => toast.error("Scan impossible", { description: e.message }),
        });

    return (
        <Panel
            title="Appareils Cast"
            icon={Cast}
            iconClassName="text-sky-300"
            action={
                <Button variant="outline" size="sm" onClick={scan} disabled={discover.isPending}>
                    {discover.isPending ? <Loader2 className="animate-spin" /> : <Radar />}
                    <span className="hidden sm:inline">{discover.isPending ? "Recherche…" : "Rechercher"}</span>
                </Button>
            }
            bodyClassName="space-y-3"
        >
            {jellyfin && !jellyfin.configured && (
                <Link
                    href="/settings/cast"
                    className="flex items-center gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-3.5 py-2.5 text-xs text-amber-200 transition-colors hover:bg-amber-500/[0.12]"
                >
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                    <span className="flex-1">Jellyfin n&apos;est pas configuré : impossible de caster un film pour l&apos;instant.</span>
                    <span className="shrink-0 font-semibold underline-offset-2 hover:underline">Configurer</span>
                </Link>
            )}

            {discover.isPending && (
                <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/[0.06] px-4 py-3 text-sm text-primary">
                    <ScanPulse /> Recherche des appareils sur ton réseau…
                </div>
            )}

            {isLoading ? (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {[0, 1, 2].map((i) => (
                        <Shimmer key={i} className="h-[68px]" />
                    ))}
                </div>
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} />
            ) : !devices || devices.length === 0 ? (
                <EmptyState
                    compact
                    icon={Cast}
                    title="Aucun appareil Cast"
                    description="Lance une recherche pour trouver tes Chromecast et Google TV."
                    action={{ label: "Rechercher sur le réseau", onClick: scan }}
                />
            ) : (
                <motion.ul variants={stagger(0, 0.05)} initial="hidden" animate="show" className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {devices.map((d) => (
                        <CastTile key={d.id} device={d} />
                    ))}
                </motion.ul>
            )}

            <div className="flex justify-end">
                <Button asChild variant="link" size="sm" className="h-auto px-0 text-xs text-muted-foreground">
                    <Link href="/settings/cast">
                        <Settings2 className="!size-3.5" /> Gérer les appareils
                    </Link>
                </Button>
            </div>
        </Panel>
    );
}

function CastTile({ device }: { device: CastDevice }) {
    const control = useCastControl();
    const Icon = device.video_capable ? Tv : Speaker;

    const stop = () =>
        control.mutate(
            { device_id: device.id, action: "quit" },
            {
                onSuccess: (r) =>
                    r?.status === "error"
                        ? toast.error(`${device.name} : arrêt refusé`, { description: r.detail })
                        : toast.success(`Diffusion arrêtée sur ${device.name}`),
                onError: (e) => toast.error(`${device.name} injoignable`, { description: e.message }),
            },
        );

    return (
        <motion.li variants={scaleIn} className="glass glass-hover flex items-center gap-3 rounded-xl p-3">
            <span
                className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ring-1",
                    device.video_capable ? "bg-sky-500/15 text-sky-300 ring-sky-400/20" : "bg-white/[0.05] text-muted-foreground ring-white/10",
                )}
            >
                <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{device.name}</p>
                <p className="truncate text-[11px] text-muted-foreground">
                    {device.model ?? (device.video_capable ? "Vidéo" : "Audio")} · <span className="font-mono">{device.ip}</span>
                </p>
            </div>
            <Button
                size="icon-sm"
                variant="ghost"
                onClick={stop}
                disabled={control.isPending}
                aria-label={`Arrêter la diffusion sur ${device.name}`}
                title="Arrêter la diffusion"
                className="text-muted-foreground hover:text-red-300"
            >
                {control.isPending ? <Loader2 className="animate-spin" /> : <Square className="fill-current" />}
            </Button>
        </motion.li>
    );
}
