"use client";

/**
 * Affichage d'une sortie du calendrier, en deux formats :
 *  - `EntryPill` : pastille compacte dans une case de la grille du mois
 *    (série + SxxEyy, ou titre du film) ;
 *  - `EntryRow`  : ligne détaillée (affiche, titre, épisode, heure, badges)
 *    pour la vue Agenda, le panneau d'un jour et « Prochaines sorties ».
 * Les deux mènent à la fiche du média quand l'id Sonarr/Radarr est connu.
 *
 * Code couleur (rappelé par la légende) : séries = bleu ciel, films =
 * violet, ✓ vert = déjà téléchargé, pointillés = non surveillé.
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Check, Clapperboard, Disc3, Eye, EyeOff, Film, MonitorDown, Tv } from "lucide-react";
import type { CalendarEntry } from "@/hooks/use-calendar";
import { cn } from "@/lib/utils";
import { RELEASE_LABELS, entryCode, entryHref, entryTime } from "./calendar-utils";

const RELEASE_ICONS = { digital: MonitorDown, physical: Disc3, cinema: Clapperboard } as const;

export const TYPE_TONES = {
    episode: {
        pill: "bg-sky-500/10 text-sky-100 ring-sky-400/20 hover:bg-sky-500/20 hover:ring-sky-400/40",
        dot: "bg-sky-400",
        text: "text-sky-300",
        label: "Série",
    },
    movie: {
        pill: "bg-violet-500/10 text-violet-100 ring-violet-400/20 hover:bg-violet-500/20 hover:ring-violet-400/40",
        dot: "bg-violet-400",
        text: "text-violet-300",
        label: "Film",
    },
} as const;

/** Lien si l'id est connu, sinon simple bloc (même apparence). */
function MaybeLink({ href, className, children, title }: { href: string | null; className: string; children: ReactNode; title?: string }) {
    return href ? (
        <Link href={href} className={className} title={title}>
            {children}
        </Link>
    ) : (
        <div className={className} title={title}>
            {children}
        </div>
    );
}

export function EntryPill({ entry, past }: { entry: CalendarEntry; past?: boolean }) {
    const tone = TYPE_TONES[entry.type] ?? TYPE_TONES.episode;
    const isEpisode = entry.type === "episode";
    const time = entryTime(entry);
    const tooltip = [
        entry.title,
        isEpisode ? `${entryCode(entry)}${entry.subtitle ? ` — ${entry.subtitle}` : ""}` : RELEASE_LABELS[entry.release_type ?? ""],
        time ? `à ${time}` : null,
        entry.has_file ? "Déjà téléchargé" : null,
        !entry.monitored ? "Non surveillé" : null,
    ]
        .filter(Boolean)
        .join(" · ");

    return (
        <MaybeLink
            href={entryHref(entry)}
            title={tooltip}
            className={cn(
                "flex w-full min-w-0 items-center gap-1 rounded-md px-1.5 py-[3px] text-[11px] leading-tight ring-1 ring-inset transition-all duration-200",
                tone.pill,
                entry.has_file && "ring-emerald-400/40",
                !entry.monitored && "border border-dashed border-white/20 opacity-60 ring-0",
                past && "opacity-60 hover:opacity-100",
            )}
        >
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", entry.has_file ? "bg-emerald-400" : tone.dot)} />
            <span className="min-w-0 flex-1 truncate font-medium">{entry.title}</span>
            {isEpisode && <span className="shrink-0 text-[10px] tabular-nums opacity-70">{entryCode(entry)}</span>}
            {entry.has_file && <Check className="h-3 w-3 shrink-0 text-emerald-300" strokeWidth={3} />}
        </MaybeLink>
    );
}

export function EntryRow({
    entry,
    aside,
    className,
}: {
    entry: CalendarEntry;
    /** Contenu à droite (heure, date relative…). Par défaut : l'heure de diffusion. */
    aside?: ReactNode;
    className?: string;
}) {
    const [imgFailed, setImgFailed] = useState(false);
    const tone = TYPE_TONES[entry.type] ?? TYPE_TONES.episode;
    const isEpisode = entry.type === "episode";
    const Placeholder = isEpisode ? Tv : Film;
    const time = entryTime(entry);
    const ReleaseIcon = entry.release_type ? RELEASE_ICONS[entry.release_type] : null;
    const href = entryHref(entry);

    return (
        <MaybeLink
            href={href}
            className={cn(
                "group flex items-center gap-3 rounded-xl p-2 transition-colors",
                href && "hover:bg-white/[0.04] focus-visible:bg-white/[0.05] focus-visible:outline-none",
                className,
            )}
        >
            <div className="relative h-[60px] w-10 shrink-0 overflow-hidden rounded-lg bg-muted/40 ring-1 ring-white/[0.08]">
                {entry.poster_url && !imgFailed ? (
                    <img
                        src={entry.poster_url}
                        alt={entry.title}
                        loading="lazy"
                        onError={() => setImgFailed(true)}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/60 to-sky-500/10">
                        <Placeholder className="h-4 w-4 text-muted-foreground/50" />
                    </div>
                )}
                <span className={cn("absolute inset-x-0 bottom-0 h-0.5", tone.dot)} />
            </div>

            <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold tracking-tight transition-colors group-hover:text-sky-200">{entry.title}</p>
                <p className="truncate text-xs text-muted-foreground">
                    {isEpisode ? (
                        <>
                            <span className="font-medium tabular-nums text-foreground/80">{entryCode(entry)}</span>
                            {entry.subtitle && <> · {entry.subtitle}</>}
                        </>
                    ) : (
                        <>
                            {entry.label && <span className="tabular-nums">{entry.label}</span>}
                            {entry.release_type && (
                                <>
                                    {entry.label ? " · " : ""}
                                    {RELEASE_LABELS[entry.release_type]}
                                </>
                            )}
                        </>
                    )}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                    <span className={cn("inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-1.5 py-px text-[10px] font-semibold ring-1 ring-inset ring-white/[0.07]", tone.text)}>
                        {isEpisode ? <Tv className="h-2.5 w-2.5" /> : ReleaseIcon ? <ReleaseIcon className="h-2.5 w-2.5" /> : <Film className="h-2.5 w-2.5" />}
                        {tone.label}
                    </span>
                    {entry.has_file ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 px-1.5 py-px text-[10px] font-semibold text-emerald-300">
                            <Check className="h-2.5 w-2.5" strokeWidth={3} /> Téléchargé
                        </span>
                    ) : entry.monitored ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-1.5 py-px text-[10px] font-medium text-muted-foreground">
                            <Eye className="h-2.5 w-2.5" /> Surveillé
                        </span>
                    ) : (
                        <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-white/15 px-1.5 py-px text-[10px] font-medium text-muted-foreground/80">
                            <EyeOff className="h-2.5 w-2.5" /> Non surveillé
                        </span>
                    )}
                    {entry.network && <span className="text-[10px] text-muted-foreground/70">{entry.network}</span>}
                </div>
            </div>

            <div className="shrink-0 text-right text-xs tabular-nums text-muted-foreground">{aside ?? time}</div>
        </MaybeLink>
    );
}
