"use client";

/**
 * Réglages → Kodi → « Caméras Eufy » : pop-up « Personne détectée » sur la TV.
 * ----------------------------------------------------------------
 * Le serveur s'abonne au conteneur eufy-security-ws (variable EUFY_WS_URL du
 * fichier .env, voir kodi-addon/README.md § 19). Ce panneau montre seulement
 * l'état : connecté ou non, caméras vues, dernière détection. Le bouton
 * « Tester la pop-up » publie une fausse détection : lance un film sur la TV
 * pour voir la pop-up sans passer devant une caméra.
 *
 * Pas de formulaire ici : l'adresse et les identifiants Eufy vivent dans
 * `.env` (comme les autres secrets du serveur), pas en base.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { BellRing, Camera, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { apiFetch } from "@/lib/api-client";
import { timeAgo } from "@/lib/format";

interface CameraStatus {
    configured: boolean;
    url: string;
    connected: boolean;
    detections: string[];
    cameras: string[];
    last_event: { camera: string; label: string; at: string } | null;
}

const DETECTION_LABELS: Record<string, string> = {
    person: "personne",
    ring: "sonnette",
    motion: "mouvement",
    pet: "animal",
    vehicle: "véhicule",
    package: "colis",
};

export function CamerasPanel() {
    const { data, isLoading } = useQuery<CameraStatus>({
        queryKey: ["cameras", "status"],
        queryFn: () => apiFetch("/api/cameras/status"),
        refetchInterval: 30_000,
        retry: false,
    });
    const test = useMutation({
        mutationFn: () => apiFetch("/api/cameras/test", { method: "POST" }),
        onSuccess: () =>
            toast.success("Fausse détection envoyée", {
                description: "Pendant un film, la pop-up s'affiche sur la TV d'ici 5 à 10 s.",
            }),
        onError: (e: Error) => toast.error("Test impossible", { description: e.message }),
    });

    const badge = !data
        ? null
        : !data.configured
          ? { text: "Non configuré", tone: "bg-white/5 text-muted-foreground" }
          : data.connected
            ? { text: "Connecté", tone: "bg-emerald-500/10 text-emerald-300" }
            : { text: "Déconnecté", tone: "bg-amber-500/10 text-amber-300" };

    return (
        <Panel
            title="Caméras Eufy"
            icon={Camera}
            iconClassName="text-rose-300"
            action={
                badge ? (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.tone}`}>{badge.text}</span>
                ) : undefined
            }
            bodyClassName="space-y-3"
        >
            <p className="text-xs leading-relaxed text-muted-foreground">
                Une caméra détecte une personne pendant un film : pop-up avec la photo en bas de la TV (15 s, toute touche la
                ferme). Hors lecture : une simple notification. Passe par le conteneur{" "}
                <span className="font-mono text-foreground">eufy-security-ws</span> (variable{" "}
                <span className="font-mono text-foreground">EUFY_WS_URL</span> du fichier .env).
            </p>
            {isLoading ? (
                <Shimmer className="h-10 w-full rounded-xl" />
            ) : data?.configured ? (
                <div className="space-y-1.5 text-xs">
                    <p>
                        <span className="text-muted-foreground">Pont : </span>
                        <span className="font-mono">{data.url}</span>
                    </p>
                    <p>
                        <span className="text-muted-foreground">Alertes : </span>
                        {data.detections.map((d) => DETECTION_LABELS[d] ?? d).join(", ") || "aucune"}
                    </p>
                    <p>
                        <span className="text-muted-foreground">Caméras : </span>
                        {data.cameras.length ? data.cameras.join(", ") : "aucune vue pour l'instant"}
                    </p>
                    {data.last_event && (
                        <p>
                            <span className="text-muted-foreground">Dernière alerte : </span>
                            {data.last_event.label} · {data.last_event.camera} · {timeAgo(data.last_event.at)}
                        </p>
                    )}
                </div>
            ) : (
                <p className="text-xs text-muted-foreground">
                    Pas encore configuré : voir <span className="font-mono text-foreground">kodi-addon/README.md</span> § 19.
                </p>
            )}
            <div className="flex justify-end">
                <Button type="button" variant="ghost" size="sm" disabled={test.isPending} onClick={() => test.mutate()}>
                    {test.isPending ? <Loader2 className="animate-spin" /> : <BellRing />}
                    Tester la pop-up
                </Button>
            </div>
        </Panel>
    );
}
