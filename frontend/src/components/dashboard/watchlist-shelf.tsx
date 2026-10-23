"use client";

/**
 * Rangée « Ma liste » de l'Accueil : les titres à voir du profil choisi,
 * ceux prêts à regarder en premier. Masquée si la liste est vide.
 */
import { Section } from "@/components/shared/section";
import { Shelf } from "@/components/shared/shelf";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { useWatchlist, useWatchlistProfile } from "@/hooks/use-watchlist";

export function WatchlistShelf() {
    const [profile] = useWatchlistProfile();
    const { data } = useWatchlist(profile);
    // Prêts à regarder d'abord, puis l'ordre d'ajout
    const items = [...(data ?? [])].sort((a, b) => Number(b.has_file) - Number(a.has_file)).slice(0, 18);
    if (items.length === 0) return null;

    return (
        <Section title="Ma liste" href="/watchlist">
            <Shelf>
                {items.map((item) => (
                    <PosterCard
                        key={item.key}
                        noEntrance
                        className="w-[112px] shrink-0 sm:w-[140px]"
                        title={item.title}
                        subtitle={item.has_file ? "Prêt à regarder" : item.in_library ? "En attente" : "Pas sur le NAS"}
                        posterUrl={item.poster_url}
                        type={item.media_type}
                        href={item.in_library && item.media_id ? `/media/${item.media_type}/${item.media_id}` : "/watchlist"}
                        dimmed={!item.has_file}
                        badges={!item.in_library ? <PosterBadge tone="warning">À demander</PosterBadge> : undefined}
                    />
                ))}
            </Shelf>
        </Section>
    );
}
