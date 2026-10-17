"use client";

/**
 * Bandeau « Radarr ne répond pas » de la Médiathèque.
 * ----------------------------------------------------------------
 * Quand un Radarr / Sonarr est injoignable (conteneur arrêté, réseau Docker
 * cassé…), le serveur sert sa DERNIÈRE LISTE CONNUE au lieu d'une médiathèque
 * vide, et réessaie toutes les 30 s (backend/app/services/media_aggregator.py).
 * Ce bandeau dit lequel, depuis quand, et ce qui est affiché à sa place.
 * Au retour du service, la liste et les compteurs sont relus tout seuls.
 */
import { useEffect, useRef } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { useLibrarySources, type LibrarySource } from "@/hooks/use-media";
import { formatNumber, timeAgo } from "@/lib/format";

function sourceLine(source: LibrarySource): string {
    const since = timeAgo(source.down_since);
    const head = `${source.name} ne répond pas${since ? ` (${since.toLowerCase()})` : ""}`;
    if (source.stale) {
        const received = timeAgo(source.last_ok_at);
        return `${head} : tu vois sa dernière liste connue, ${formatNumber(source.count)} titres${
            received ? `, reçue ${received.toLowerCase()}` : ""
        }.`;
    }
    return `${head} : ses titres ne s'affichent pas (aucune liste connue).`;
}

export function LibrarySourcesBanner() {
    const { data } = useLibrarySources();
    const qc = useQueryClient();
    const down = data?.sources.filter((s) => !s.ok) ?? [];

    // Service revenu : on relit la médiathèque (liste, compteurs, facettes).
    const wasDegraded = useRef(false);
    const degraded = !!data?.degraded;
    useEffect(() => {
        if (wasDegraded.current && !degraded) qc.invalidateQueries({ queryKey: ["media"] });
        wasDegraded.current = degraded;
    }, [degraded, qc]);

    if (!down.length) return null;
    return (
        <div
            role="status"
            className="flex gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3 text-xs leading-relaxed text-amber-200"
        >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1 space-y-1">
                {down.map((source) => (
                    <p key={source.id} className="font-medium">
                        {sourceLine(source)}
                    </p>
                ))}
                <p className="text-amber-200/75">
                    ArrMada réessaie toutes les 30&nbsp;s. Vérifie que le conteneur tourne et que son port répond.
                </p>
            </div>
            <Link
                href="/settings/services"
                className="inline-flex shrink-0 items-center gap-1 self-start rounded-lg px-2 py-1 font-semibold text-amber-100 transition-colors hover:bg-amber-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
            >
                Services <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
        </div>
    );
}
