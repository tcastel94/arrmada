"use client";

/**
 * Rangée « Reprendre » de l'Accueil (nouveau).
 * ----------------------------------------------------------------
 * Les films et épisodes commencés sur les TV, en vignettes paysage
 * (image du film, barre de progression, temps restant) comme la rangée
 * « À suivre » de l'app TV d'Apple. Toucher la vignette ouvre la fiche ;
 * le bouton ▶ relance la lecture à l'endroit exact sur une TV appairée.
 * Masquée s'il n'y a rien en cours (pas de section vide sur l'Accueil).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { Film } from "lucide-react";
import { Section } from "@/components/shared/section";
import { Shelf } from "@/components/shared/shelf";
import { PlayOnTvButton } from "@/components/media/play-on-tv";
import { episodeCode, useWatchSummary, type ContinueRow } from "@/hooks/use-watch";

/** « 23 min restantes » / « 1 h 12 restantes ». */
function leftLabel(row: ContinueRow): string {
    const left = Math.max(0, row.total - row.position);
    if (!row.total || left < 60) return "";
    const min = Math.round(left / 60);
    if (min < 60) return `${min} min restantes`;
    return `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} restantes`;
}

export function ContinueShelf() {
    const { data } = useWatchSummary();
    const rows = (data?.continue ?? []).slice(0, 12);
    if (rows.length === 0) return null;

    return (
        <Section title="Reprendre" href="/media/continue">
            <Shelf>
                {rows.map((row) => {
                    const isMovie = row.media_type === "movie";
                    const image = row.fanart_url ?? row.poster_url;
                    const href = row.media_kind && row.media_id ? `/media/${row.media_kind}/${row.media_id}` : "/media/continue";
                    const pct = row.progress ?? (row.total ? (row.position / row.total) * 100 : 0);
                    return (
                        <div key={`${row.media_type}:${row.id}:${row.season ?? ""}:${row.episode ?? ""}`} className="w-[260px] shrink-0 sm:w-[300px]">
                            <div className="relative">
                                <Link href={href} className="pressable block overflow-hidden rounded-[12px] bg-white/[0.06]">
                                    <div className="relative aspect-video">
                                        {image ? (
                                            <img src={image} alt="" loading="lazy" className={row.fanart_url ? "h-full w-full object-cover" : "h-full w-full object-cover object-top"} />
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
                })}
            </Shelf>
        </Section>
    );
}
