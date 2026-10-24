"use client";

/**
 * Section « Transferts » de l'Accueil : les 5 éléments les plus avancés de
 * la file de téléchargement, en liste groupée avec barre fine et temps
 * restant (comme les téléchargements de l'App Store).
 */
import { ArrowDownToLine } from "lucide-react";
import { useDownloads } from "@/hooks/use-downloads";
import { Section } from "@/components/shared/section";
import { GroupedList } from "@/components/shared/grouped-list";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { GradientProgress } from "@/components/fx/gradient-progress";

export function DownloadsWidget() {
    const { data, isLoading } = useDownloads();
    const items = [...(data?.items ?? [])].sort((a, b) => b.progress - a.progress).slice(0, 5);
    const total = data?.total ?? data?.items?.length ?? 0;

    return (
        <Section title="Transferts" subtitle={total > 0 ? `${total} en cours` : undefined} href="/downloads">
            {isLoading ? (
                <Shimmer className="h-[220px] rounded-xl" />
            ) : items.length === 0 ? (
                <div className="rounded-xl bg-card">
                    <EmptyState compact icon={ArrowDownToLine} title="Aucun transfert" description="Rien ne télécharge pour le moment." />
                </div>
            ) : (
                <GroupedList>
                    {items.map((dl) => {
                        const downloading = dl.status?.toLowerCase() === "downloading";
                        return (
                            <div key={`${dl.service_type}-${dl.id}`} className="px-4 py-3">
                                <div className="flex items-baseline justify-between gap-3">
                                    <p className="truncate text-[15px]" title={dl.title}>
                                        {dl.title}
                                    </p>
                                    <span className="shrink-0 text-[13px] font-medium tabular-nums text-muted-foreground">{dl.progress.toFixed(0)} %</span>
                                </div>
                                <GradientProgress className="mt-2" value={dl.progress} active={downloading} tone={downloading ? "primary" : "slate"} />
                                <p className="mt-1.5 truncate text-[12px] text-muted-foreground">
                                    {[dl.quality, dl.download_client, dl.time_left ? `${dl.time_left} restantes` : downloading ? null : dl.status].filter(Boolean).join(" · ")}
                                </p>
                            </div>
                        );
                    })}
                </GroupedList>
            )}
        </Section>
    );
}
