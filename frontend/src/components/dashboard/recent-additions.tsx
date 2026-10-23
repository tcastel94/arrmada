"use client";

/**
 * Rangée « Ajoutés récemment » de l'Accueil : les derniers titres entrés
 * dans la médiathèque, en affiches défilantes (style app TV d'Apple).
 */
import { Clapperboard } from "lucide-react";
import { useMedia } from "@/hooks/use-media";
import { PosterCard, PosterBadge } from "@/components/shared/poster-card";
import { Section } from "@/components/shared/section";
import { Shelf } from "@/components/shared/shelf";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { timeAgo } from "@/lib/format";

const CARD = "w-[112px] shrink-0 sm:w-[140px]";

export function RecentAdditions() {
    const { data, isLoading } = useMedia({ sort: "added", order: "desc", per_page: 18, page: 1 });
    const items = data?.items ?? [];

    return (
        <Section title="Ajoutés récemment" href="/media">
            {isLoading ? (
                <Shelf>
                    {Array.from({ length: 8 }).map((_, i) => (
                        <div key={i} className={CARD}>
                            <Shimmer className="aspect-[2/3] w-full rounded-[10px]" />
                            <Shimmer className="mt-2 h-3 w-3/4 rounded" />
                        </div>
                    ))}
                </Shelf>
            ) : items.length === 0 ? (
                <div className="rounded-2xl bg-card">
                    <EmptyState compact icon={Clapperboard} title="Rien de neuf" description="Les derniers ajouts apparaîtront ici." />
                </div>
            ) : (
                <Shelf>
                    {items.map((m) => (
                        <PosterCard
                            key={`${m.type}-${m.external_id}`}
                            noEntrance
                            className={CARD}
                            title={m.title}
                            subtitle={m.added ? `Ajouté ${timeAgo(m.added)}` : m.year ?? undefined}
                            posterUrl={m.poster_url}
                            type={m.type}
                            href={`/media/${m.type}/${m.external_id}`}
                            dimmed={!m.has_file}
                            badges={!m.has_file ? <PosterBadge tone="warning">Manquant</PosterBadge> : undefined}
                            progress={m.type === "series" && m.episodes_total ? ((m.episodes_have ?? 0) / m.episodes_total) * 100 : undefined}
                        />
                    ))}
                </Shelf>
            )}
        </Section>
    );
}
