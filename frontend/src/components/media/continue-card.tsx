"use client";

/**
 * Vignette « Reprendre » (film ou épisode commencé sur une TV), style
 * « À suivre » de l'app TV d'Apple : image paysage, barre de progression,
 * titre et temps restant dessous, bouton ▶ pour relancer sur une TV.
 * Partagée par l'Accueil (rangée) et la page Reprendre (grille).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { Film } from "lucide-react";
import { PlayOnTvButton } from "@/components/media/play-on-tv";
import { episodeCode, type ContinueRow } from "@/hooks/use-watch";
import { cn } from "@/lib/utils";

/** « 23 min restantes » / « 1 h 12 restantes ». */
export function leftLabel(row: Pick<ContinueRow, "total" | "position">): string {
    const left = Math.max(0, row.total - row.position);
    if (!row.total || left < 60) return "";
    const min = Math.round(left / 60);
    if (min < 60) return `${min} min restantes`;
    return `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} restantes`;
}

export function continueKey(row: ContinueRow): string {
    return `${row.media_type}:${row.id}:${row.season ?? ""}:${row.episode ?? ""}`;
}

export function ContinueCard({ row, className }: { row: ContinueRow; className?: string }) {
    const isMovie = row.media_type === "movie";
    const image = row.fanart_url ?? row.poster_url;
    const href = row.media_kind && row.media_id ? `/media/${row.media_kind}/${row.media_id}` : "/media/continue";
    const pct = row.progress ?? (row.total ? (row.position / row.total) * 100 : 0);
    return (
        <div className={cn("min-w-0", className)}>
            <div className="relative">
                <Link href={href} className="pressable block overflow-hidden rounded-[12px] bg-white/[0.06]">
                    <div className="relative aspect-video">
                        {image ? (
                            <img src={image} alt="" loading="lazy" className={cn("h-full w-full object-cover", !row.fanart_url && "object-top")} />
                        ) : (
                            <Film className="absolute inset-0 m-auto h-8 w-8 text-white/20" />
                        )}
                        {/* Voile bas pour la barre de progression */}
                        <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/70 to-transparent" />
                        <div className="absolute inset-x-3 bottom-2.5 h-1 overflow-hidden rounded-full bg-white/30">
                            <div className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, Math.max(2, pct))}%` }} />
                        </div>
                    </div>
                </Link>
                <div className="absolute right-2 top-2">
                    <PlayOnTvButton
                        target={{ media_type: row.media_type, id: row.id, season: row.season, episode: row.episode, title: row.title }}
                        resumeAt={row.position}
                        label=""
                        size="icon-sm"
                        variant="secondary"
                        className="bg-black/55 backdrop-blur hover:bg-black/70"
                    />
                </div>
            </div>
            <Link href={href} className="mt-2 block px-0.5">
                <p className="truncate text-[14px] font-medium">{row.title}</p>
                <p className="truncate text-[12px] text-muted-foreground">
                    {[isMovie ? row.year : episodeCode(row.season, row.episode), leftLabel(row), row.device].filter(Boolean).join(" · ")}
                </p>
            </Link>
        </div>
    );
}
