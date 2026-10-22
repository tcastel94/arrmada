"use client";

/**
 * Rangée « Séries maison » de la médiathèque (types « Tout » et « Séries »).
 * ----------------------------------------------------------------
 * Les montages de fans (Naruto Kai, One Pace…) n'existent ni dans Sonarr ni
 * dans Jellyfin : la grille principale, paginée par le serveur à partir de
 * Radarr / Sonarr, ne peut pas les mêler. Ils ont donc leur propre rangée,
 * au-dessus, avec leur pastille (« Kai ») ; un clic ouvre leur fiche.
 * Rien ne s'affiche s'il n'y en a aucune (déclarées dans Réglages › Dossiers vidéo).
 */
import Link from "next/link";
import { FolderOpen } from "lucide-react";
import { localImage, useLocalSeries } from "@/hooks/use-local-series";
import { plural } from "@/lib/format";

export function LocalSeriesRow() {
    const { data } = useLocalSeries();
    const series = (data ?? []).filter((s) => s.available);
    if (series.length === 0) return null;

    return (
        <section className="mb-6">
            <div className="mb-3 flex items-baseline justify-between gap-3">
                <h2 className="eyebrow flex items-center gap-2">
                    <FolderOpen className="h-4 w-4" /> Séries maison
                </h2>
                <Link href="/settings/dossiers" className="text-xs text-muted-foreground hover:text-foreground">
                    Gérer
                </Link>
            </div>
            <ul className="flex gap-4 overflow-x-auto pb-2">
                {series.map((s) => {
                    const poster = localImage(s.poster_url);
                    return (
                        <li key={s.id} className="w-32 shrink-0 sm:w-36">
                            <Link href={`/media/local/${s.id}`} className="group block">
                                <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-muted ring-1 ring-white/5 transition group-hover:ring-[#4A9EFF]/60">
                                    {poster ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img src={poster} alt="" loading="lazy" className="h-full w-full object-cover transition group-hover:scale-[1.03]" />
                                    ) : (
                                        <div className="flex h-full items-center justify-center p-2 text-center text-sm text-muted-foreground">{s.title}</div>
                                    )}
                                    {s.badge && (
                                        <span className="absolute left-1.5 top-1.5 rounded bg-[#4A9EFF] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#0b1220]">
                                            {s.badge}
                                        </span>
                                    )}
                                </div>
                                <p className="mt-1.5 truncate text-sm font-medium">{s.title}</p>
                                <p className="truncate text-xs text-muted-foreground">
                                    {plural(s.seasons, "arc", "arcs")} · {plural(s.episodes, "épisode", "épisodes")}
                                </p>
                            </Link>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}
