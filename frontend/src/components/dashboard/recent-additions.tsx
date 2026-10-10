"use client";

/**
 * Carrousel « Ajouts récents » : les derniers titres entrés dans la
 * bibliothèque, défilement horizontal avec accroche (scroll-snap) et
 * flèches sur desktop.
 */
import { useRef } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Clapperboard } from "lucide-react";
import { useMedia } from "@/hooks/use-media";
import { PosterCard, PosterBadge } from "@/components/shared/poster-card";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { stagger } from "@/lib/motion";
import { timeAgo } from "@/lib/format";

export function RecentAdditions() {
    const { data, isLoading } = useMedia({ sort: "added", order: "desc", per_page: 18, page: 1 });
    const scroller = useRef<HTMLDivElement>(null);
    const items = data?.items ?? [];

    const scrollBy = (dir: 1 | -1) => scroller.current?.scrollBy({ left: dir * scroller.current.clientWidth * 0.8, behavior: "smooth" });

    return (
        <Panel
            title="Ajouts récents"
            icon={Clapperboard}
            iconClassName="text-violet-300"
            href="/media"
            hrefLabel="Médiathèque"
            bodyClassName="px-0 py-4"
            action={
                <div className="hidden items-center gap-1 md:flex">
                    <button onClick={() => scrollBy(-1)} className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground" aria-label="Défiler à gauche">
                        <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button onClick={() => scrollBy(1)} className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground" aria-label="Défiler à droite">
                        <ChevronRight className="h-4 w-4" />
                    </button>
                </div>
            }
        >
            {isLoading ? (
                <div className="flex gap-4 overflow-hidden px-5">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <Shimmer key={i} className="aspect-[2/3] w-[140px] shrink-0 rounded-2xl" />
                    ))}
                </div>
            ) : items.length === 0 ? (
                <EmptyState compact icon={Clapperboard} title="Rien de neuf à bord" description="Les derniers ajouts apparaîtront ici." />
            ) : (
                <motion.div
                    ref={scroller}
                    variants={stagger(0.1, 0.04)}
                    initial="hidden"
                    animate="show"
                    className="scrollbar-none mask-fade-x flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-5 pb-2 pt-1"
                >
                    {items.map((m) => (
                        <PosterCard
                            key={`${m.type}-${m.external_id}`}
                            className="w-[132px] shrink-0 snap-start sm:w-[150px]"
                            title={m.title}
                            subtitle={m.added ? `Ajouté ${timeAgo(m.added)}` : m.year ?? undefined}
                            posterUrl={m.poster_url}
                            type={m.type}
                            href={`/media/${m.type}/${m.external_id}`}
                            dimmed={!m.has_file}
                            badges={
                                <>
                                    {m.quality && <PosterBadge>{m.quality}</PosterBadge>}
                                    {!m.has_file && <PosterBadge tone="warning">Manquant</PosterBadge>}
                                </>
                            }
                            progress={
                                m.type === "series" && m.episodes_total
                                    ? ((m.episodes_have ?? 0) / m.episodes_total) * 100
                                    : undefined
                            }
                        />
                    ))}
                </motion.div>
            )}
        </Panel>
    );
}
