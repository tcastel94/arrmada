"use client";

/**
 * Résultats de la recherche manuelle de sous-titres chez les providers
 * Bazarr (OpenSubtitles, Addic7ed…), avec chargement / erreur / vide.
 */
import { Download, Loader2, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import type { ProviderSubtitle } from "@/hooks/use-subtitles";
import { cn } from "@/lib/utils";

export const providerKey = (s: ProviderSubtitle) => `${s.provider}:${s.subtitle}`;

export function ProviderResults({
    items,
    isLoading,
    error,
    onRetry,
    onDownload,
    downloadingKey,
}: {
    items?: ProviderSubtitle[];
    isLoading: boolean;
    error: unknown;
    onRetry: () => void;
    onDownload: (s: ProviderSubtitle) => void;
    downloadingKey: string | null;
}) {
    if (isLoading) {
        return (
            <div className="space-y-2" aria-live="polite">
                <p className="text-xs text-muted-foreground">Interrogation des providers…</p>
                {Array.from({ length: 3 }).map((_, i) => (
                    <Shimmer key={i} className="h-16 w-full" />
                ))}
            </div>
        );
    }
    if (error) return <ErrorState compact error={error} onRetry={onRetry} title="Recherche de sous-titres impossible" />;
    if (!items) return null;
    if (items.length === 0) {
        return <EmptyState compact icon={SearchX} title="Aucun sous-titre trouvé" description="Aucun provider n'a de sous-titre pour cette release." />;
    }

    // Meilleur score en premier.
    const sorted = [...items].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

    return (
        <ul className="space-y-2">
            {sorted.map((s) => {
                const key = providerKey(s);
                const busy = downloadingKey === key;
                return (
                    <li key={key} className="glass glass-hover flex flex-col gap-3 rounded-xl p-3 sm:flex-row sm:items-center">
                        <div className="min-w-0 flex-1 space-y-1.5">
                            <p className="line-clamp-2 text-sm font-medium [overflow-wrap:anywhere]" title={s.release_info}>
                                {s.release_info || "(release sans nom)"}
                            </p>
                            <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                                <span className="rounded-md bg-white/[0.06] px-1.5 py-px font-medium">{s.provider}</span>
                                <span className="rounded-md border border-white/10 px-1.5 py-px font-semibold uppercase">{s.language}</span>
                                {s.hi && (
                                    <abbr title="Sous-titres pour sourds et malentendants" className="rounded-md border border-white/10 px-1.5 py-px no-underline">
                                        SDH
                                    </abbr>
                                )}
                                {s.forced && <span className="rounded-md border border-white/10 px-1.5 py-px">forcés</span>}
                                {s.uploader && <span className="text-muted-foreground">par {s.uploader}</span>}
                                {s.score != null && (
                                    <span
                                        className={cn(
                                            "rounded-md border px-1.5 py-px font-bold tabular-nums",
                                            s.score >= 80
                                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                                                : s.score >= 50
                                                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                                                  : "border-white/10 text-muted-foreground",
                                        )}
                                        title="Correspondance avec ton fichier (sur 100)"
                                    >
                                        Correspondance {Math.round(s.score)} %
                                    </span>
                                )}
                            </div>
                        </div>
                        <Button size="sm" className="w-full shrink-0 sm:w-auto" disabled={busy} onClick={() => onDownload(s)}>
                            {busy ? <Loader2 className="animate-spin" /> : <Download />}
                            Télécharger
                        </Button>
                    </li>
                );
            })}
        </ul>
    );
}
