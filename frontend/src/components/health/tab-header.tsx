"use client";

/**
 * En-tête d'onglet du hub Santé + indicateur « N affichés sur total ».
 * ----------------------------------------------------------------
 * - Bouton « Rescanner » qui relance l'analyse (spinner pendant le calcul)
 *   et date de la dernière analyse (« analysé il y a 3 min »).
 * - `ShownCount` : le backend tronque certaines listes (30, 20, 50…) mais
 *   renvoie le vrai total ; on l'affiche explicitement pour ne plus
 *   laisser croire que la liste est complète.
 */
import type { ReactNode } from "react";
import { Info, RefreshCw, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatNumber, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

interface HealthTabHeaderProps {
    icon: LucideIcon;
    iconClassName?: string;
    title: string;
    description?: ReactNode;
    /** `dataUpdatedAt` de React Query (ms). */
    updatedAt?: number;
    isFetching?: boolean;
    onRescan?: () => void;
    /** Éléments supplémentaires à droite (filtres, badges…). */
    children?: ReactNode;
}

export function HealthTabHeader({
    icon: Icon,
    iconClassName = "text-primary",
    title,
    description,
    updatedAt,
    isFetching,
    onRescan,
    children,
}: HealthTabHeaderProps) {
    return (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.04] ring-1 ring-white/[0.08]">
                    <Icon className={cn("h-4 w-4", iconClassName)} />
                </span>
                <div className="min-w-0">
                    <h2 className="text-base font-semibold tracking-tight">{title}</h2>
                    {description && <p className="text-xs text-muted-foreground text-balance">{description}</p>}
                </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
                {children}
                {updatedAt ? (
                    <span className="text-[11px] text-muted-foreground/80" title={new Date(updatedAt).toLocaleString("fr-FR")}>
                        Analysé {timeAgo(updatedAt).toLowerCase()}
                    </span>
                ) : null}
                {onRescan && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button variant="outline" size="sm" onClick={onRescan} disabled={isFetching}>
                                <RefreshCw className={cn(isFetching && "animate-spin")} />
                                {isFetching ? "Analyse…" : "Rescanner"}
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64 text-xs">
                            Relit les résultats du serveur. ArrMada garde une analyse jusqu&apos;à 10 min en cache pour
                            ne pas surcharger Radarr/Sonarr.
                        </TooltipContent>
                    </Tooltip>
                )}
            </div>
        </div>
    );
}

/** « 30 affichés sur 142 » (rien si la liste est complète). */
export function ShownCount({
    shown,
    total,
    sortHint,
    className,
}: {
    shown: number;
    total: number;
    /** Ex: « les plus volumineux d'abord ». */
    sortHint?: string;
    className?: string;
}) {
    if (total <= shown) {
        return (
            <span className={cn("text-xs text-muted-foreground tabular-nums", className)}>
                {formatNumber(total)} élément{total > 1 ? "s" : ""}
            </span>
        );
    }
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <span
                    tabIndex={0}
                    className={cn(
                        "inline-flex cursor-help items-center gap-1.5 rounded-lg border border-warning/25 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning tabular-nums",
                        className,
                    )}
                >
                    <Info className="h-3 w-3" />
                    {formatNumber(shown)} affichés sur {formatNumber(total)}
                </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-64 text-xs">
                Le serveur ne renvoie que les {formatNumber(shown)} premiers{sortHint ? ` (${sortHint})` : ""}. Traite-les
                puis relance un scan pour voir la suite.
            </TooltipContent>
        </Tooltip>
    );
}
