"use client";

/**
 * Rangée « Séries maison » de la médiathèque (types « Tout » et « Séries »).
 * ----------------------------------------------------------------
 * Les montages de fans (Naruto Kai, One Pace…) n'existent ni dans Sonarr ni
 * dans Jellyfin : la grille principale, paginée par le serveur à partir de
 * Radarr / Sonarr, ne peut pas les mêler. Ils ont donc leur propre rangée,
 * au-dessus (rangée défilante), avec leur pastille (« Kai ») ; un clic ouvre leur fiche.
 * Rien ne s'affiche s'il n'y en a aucune (déclarées dans Réglages › Dossiers vidéo).
 */
import Link from "next/link";
import { Section } from "@/components/shared/section";
import { Shelf } from "@/components/shared/shelf";
import { localImage, useLocalSeries } from "@/hooks/use-local-series";
import { plural } from "@/lib/format";

export function LocalSeriesRow() {
    const { data } = useLocalSeries();
    const series = (data ?? []).filter((s) => s.available);
    if (series.length === 0) return null;

    return (
        <Section title="Séries maison" href="/settings/dossiers" hrefLabel="Gérer">
            <Shelf>
                {series.map((s) => {
                    const poster = localImage(s.poster_url);
                    return (
                        <Link key={s.id} href={`/media/local/${s.id}`} className="group block w-[112px] shrink-0 sm:w-[140px]">
                            <div className="relative aspect-[2/3] overflow-hidden rounded-[10px] bg-white/[0.06] transition-transform duration-300 ease-smooth group-hover:scale-[1.03] group-active:scale-[0.98]">
                                {poster ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={poster} alt="" loading="lazy" className="h-full w-full object-cover" />
                                ) : (
                                    <div className="flex h-full items-center justify-center p-2 text-center text-[13px] text-muted-foreground">{s.title}</div>
                                )}
                                {s.badge && (
                                    <span className="absolute left-1.5 top-1.5 rounded-[5px] bg-primary px-1.5 py-[3px] text-[10px] font-semibold uppercase leading-none text-white">
                                        {s.badge}
                                    </span>
                                )}
                            </div>
                            <p className="mt-2 truncate px-0.5 text-[13px] font-medium">{s.title}</p>
                            <p className="truncate px-0.5 text-[12px] text-muted-foreground">
                                {plural(s.seasons, "arc", "arcs")} · {plural(s.episodes, "épisode", "épisodes")}
                            </p>
                        </Link>
                    );
                })}
            </Shelf>
        </Section>
    );
}
