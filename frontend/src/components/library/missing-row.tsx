"use client";

/**
 * Ligne de la page « Manquants » : miniature, titre, type, surveillance,
 * statut de sortie, date d'ajout, et bouton Rechercher avec état par ligne.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertCircle, CalendarPlus, Check, CheckCircle2, Eye, EyeOff, Film, Loader2, RotateCcw, Search, Tv } from "lucide-react";
import type { MediaItem } from "@/hooks/use-media";
import { Button } from "@/components/ui/button";
import { formatShortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";
import { MediaThumb } from "./media-thumb";
import { mediaHref } from "./media-card";
import type { RowSearchState } from "./use-bulk-search";

/** Libellé FR + couleur d'un statut Radarr/Sonarr. */
export function releaseStatus(item: MediaItem): { label: string; className: string } | null {
    const s = (item.status || "").toLowerCase();
    const map: Record<string, { label: string; className: string }> = {
        released: { label: "Sorti", className: "bg-success/10 text-success ring-success/25" },
        incinemas: { label: "Au cinéma", className: "bg-primary/10 text-primary ring-primary/25" },
        announced: { label: "Annoncé", className: "bg-warning/10 text-warning ring-warning/25" },
        tba: { label: "À venir", className: "bg-white/[0.04] text-muted-foreground ring-white/10" },
        continuing: { label: "En cours", className: "bg-success/10 text-success ring-success/25" },
        upcoming: { label: "À venir", className: "bg-warning/10 text-warning ring-warning/25" },
        ended: { label: "Terminée", className: "bg-white/[0.04] text-muted-foreground ring-white/10" },
    };
    return map[s] ?? (s ? { label: item.status, className: "bg-white/[0.04] text-muted-foreground ring-white/10" } : null);
}

/** Bouton de recherche d'une ligne, avec ses 4 états. */
export function RowSearchButton({
    state,
    onSearch,
    disabled,
    compact,
    title,
}: {
    state?: RowSearchState;
    onSearch: () => void;
    disabled?: boolean;
    /** Version ronde, icône seule (vue grille). */
    compact?: boolean;
    title: string;
}) {
    const busy = state === "searching";
    const launched = state === "launched";
    const failed = state === "failed";
    const Icon = busy ? Loader2 : launched ? CheckCircle2 : failed ? RotateCcw : Search;
    const label = busy ? "Recherche…" : launched ? "Lancée" : failed ? "Réessayer" : "Rechercher";

    if (compact) {
        return (
            <button
                type="button"
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onSearch();
                }}
                disabled={disabled || busy || launched}
                aria-label={`${label} : ${title}`}
                title={label}
                className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full shadow-lg ring-1 backdrop-blur-md transition-all hover:scale-110 disabled:hover:scale-100",
                    launched
                        ? "bg-success text-white ring-success/40"
                        : failed
                          ? "bg-destructive/90 text-white ring-destructive/40"
                          : "bg-black/60 text-white ring-white/20 hover:bg-primary",
                )}
            >
                <Icon className={cn("h-4 w-4", busy && "animate-spin")} />
            </button>
        );
    }

    return (
        <Button
            size="sm"
            variant={launched ? "outline" : failed ? "destructive" : "glow"}
            onClick={onSearch}
            disabled={disabled || busy || launched}
            aria-label={`${label} : ${title}`}
            // Mobile : bouton carré (icône seule) pour laisser la place au titre.
            className={cn("w-9 shrink-0 px-0 sm:w-[7.5rem] sm:px-3", launched && "border-success/40 text-success disabled:opacity-100")}
        >
            <Icon className={cn(busy && "animate-spin")} />
            <span className="hidden sm:inline">{label}</span>
        </Button>
    );
}

export function MissingRow({
    item,
    selected,
    onToggle,
    onSearch,
    state,
    disabled,
}: {
    item: MediaItem;
    selected: boolean;
    onToggle: () => void;
    onSearch: () => void;
    state?: RowSearchState;
    /** Recherche groupée en cours : les boutons individuels sont bloqués. */
    disabled?: boolean;
}) {
    const st = releaseStatus(item);
    const added = formatShortDate(item.added);
    const TypeIcon = item.type === "series" ? Tv : Film;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: 60, transition: { duration: 0.3, ease: EASE_OUT } }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className={cn(
                "group flex items-center gap-3 rounded-xl p-2 pr-2.5 ring-1 transition-colors duration-300",
                selected ? "bg-primary/10 ring-primary/40" : "ring-transparent hover:bg-white/[0.04] hover:ring-white/[0.08]",
                state === "launched" && !selected && "bg-success/[0.04]",
                state === "failed" && !selected && "bg-destructive/[0.05]",
            )}
        >
            <button
                type="button"
                onClick={onToggle}
                aria-pressed={selected}
                aria-label={selected ? `Désélectionner ${item.title}` : `Sélectionner ${item.title}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-white/[0.06]"
            >
                <span
                    className={cn(
                        "flex h-5 w-5 items-center justify-center rounded-md border-2 transition-all duration-200",
                        selected ? "scale-100 border-primary bg-primary text-primary-foreground" : "border-white/30 group-hover:border-white/50",
                    )}
                >
                    {selected && <Check className="h-3 w-3" strokeWidth={3} />}
                </span>
            </button>

            <Link href={mediaHref(item)} className="shrink-0" tabIndex={-1} aria-hidden>
                <MediaThumb src={item.poster_url} alt="" type={item.type} className="h-16 w-11 grayscale-[40%] transition-all group-hover:grayscale-0" />
            </Link>

            <div className="min-w-0 flex-1">
                <Link href={mediaHref(item)} className="block truncate text-sm font-semibold transition-colors hover:text-primary">
                    {item.title}
                    {item.year && <span className="ml-1.5 font-normal text-muted-foreground">{item.year}</span>}
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                    <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.05] px-2 py-0.5 text-muted-foreground ring-1 ring-white/[0.08]">
                        <TypeIcon className="h-3 w-3" />
                        {item.type === "movie" ? "Film" : "Série"}
                    </span>
                    {item.monitored ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-success ring-1 ring-success/25">
                            <Eye className="h-3 w-3" /> Surveillé
                        </span>
                    ) : (
                        <span
                            className="inline-flex items-center gap-1 rounded-full bg-white/[0.04] px-2 py-0.5 text-muted-foreground ring-1 ring-white/10"
                            title="Non surveillé : la recherche peut ne rien récupérer"
                        >
                            <EyeOff className="h-3 w-3" /> Non surveillé
                        </span>
                    )}
                    {st && <span className={cn("hidden rounded-full px-2 py-0.5 ring-1 sm:inline", st.className)}>{st.label}</span>}
                    {added && (
                        <span className="hidden items-center gap-1 text-muted-foreground/70 sm:inline-flex">
                            <CalendarPlus className="h-3 w-3" /> ajouté le {added}
                        </span>
                    )}
                    {state === "failed" && (
                        <span className="inline-flex items-center gap-1 text-destructive">
                            <AlertCircle className="h-3 w-3" /> échec
                        </span>
                    )}
                </div>
            </div>

            <RowSearchButton state={state} onSearch={onSearch} disabled={disabled} title={item.title} />
        </motion.div>
    );
}
