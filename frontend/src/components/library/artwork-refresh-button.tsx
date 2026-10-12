"use client";

/**
 * Bouton « Artworks » de la Médiathèque : récupère logos, disques, clearart…
 * pour toute la médiathèque (fanart.tv / TMDB, côté serveur).
 * ----------------------------------------------------------------
 * - Clic → menu : « Récupérer les manquants » (titres jamais servis ou servis
 *   il y a longtemps : presque gratuit à relancer) ou « Tout redemander ».
 * - Pendant le travail : le bouton affiche la progression (120 / 850) et un
 *   anneau ; à la fin, un toast résume (« 640 titres avec des artworks »).
 * - Le travail tourne sur le serveur : fermer l'onglet ne l'interrompt pas.
 */
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { Disc3, Images, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RingGauge } from "@/components/fx/ring-gauge";
import { useArtworkRefresh, useArtworkStatus } from "@/hooks/use-artwork";

export function ArtworkRefreshButton() {
    const { data: status } = useArtworkStatus();
    const refresh = useArtworkRefresh();
    const running = !!status?.running;
    const pct = status && status.total > 0 ? Math.round((status.done / status.total) * 100) : 0;
    const noSource = status && !status.sources.fanart && !status.sources.tmdb;

    // Toast de fin (seulement si on a vu le travail tourner dans cet onglet)
    const sawRunning = useRef(false);
    useEffect(() => {
        if (running) sawRunning.current = true;
        else if (sawRunning.current && status) {
            sawRunning.current = false;
            if (status.errors && !status.found) toast.error("Artworks : sites injoignables", { description: status.message });
            else toast.success("Artworks récupérés", { description: status.message });
        }
    }, [running, status]);

    const start = (force: boolean) =>
        refresh.mutate(
            { force },
            {
                onSuccess: () =>
                    toast.info(force ? "Récupération complète lancée" : "Récupération des artworks lancée", {
                        description: "Le serveur travaille en arrière-plan, tu peux changer de page.",
                    }),
                onError: (e) => toast.error("Récupération impossible", { description: e.message }),
            },
        );

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline" aria-label="Artworks : logos, disques, clearart">
                    {running ? (
                        <RingGauge value={pct} size={18} stroke={3} tone="primary" />
                    ) : (
                        <Images />
                    )}
                    {running ? (
                        <span className="tabular-nums">
                            {status?.done ?? 0} / {status?.total ?? 0}
                        </span>
                    ) : (
                        "Artworks"
                    )}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72">
                <DropdownMenuLabel className="eyebrow">Logos, disques, clearart</DropdownMenuLabel>
                {status && (
                    <p className="px-2 pb-2 text-xs text-muted-foreground">
                        {status.stored.titles > 0 ? (
                            <>
                                {status.stored.logos} logos · {status.stored.discs} disques · {status.stored.clearart} clearart
                                <br />
                                pour {status.stored.titles} titres déjà interrogés.
                            </>
                        ) : (
                            "Aucun artwork récupéré pour l'instant."
                        )}
                    </p>
                )}
                {noSource && (
                    <p className="mx-2 mb-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-200">
                        Aucune source : ajoute FANART_API_KEY (ou TMDB_API_KEY) dans le .env du serveur.
                    </p>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => start(false)} disabled={running || refresh.isPending || !!noSource}>
                    <Sparkles />
                    Récupérer les manquants
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => start(true)} disabled={running || refresh.isPending || !!noSource}>
                    <RefreshCw />
                    Tout redemander
                </DropdownMenuItem>
                {running && (
                    <p className="flex items-center gap-1.5 px-2 pt-2 text-xs text-muted-foreground">
                        <Disc3 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                        {status?.found ?? 0} trouvés · {status?.message}
                    </p>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
