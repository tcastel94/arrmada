"use client";

/**
 * Widget « Téléchargements » : les 5 éléments les plus avancés de la file,
 * barres animées pour ceux qui progressent.
 */
import { AnimatePresence, motion } from "framer-motion";
import { Download, Clock } from "lucide-react";
import { useDownloads } from "@/hooks/use-downloads";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { ClientBadge } from "@/components/shared/download-client";
import { EASE_OUT } from "@/lib/motion";

export function DownloadsWidget() {
    const { data, isLoading } = useDownloads();
    const items = [...(data?.items ?? [])].sort((a, b) => b.progress - a.progress).slice(0, 5);
    const total = data?.total ?? data?.items?.length ?? 0;

    return (
        <Panel
            title="Téléchargements"
            icon={Download}
            iconClassName="text-primary"
            href="/downloads"
            action={
                total > 0 && (
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-primary">
                        {total} actif{total > 1 ? "s" : ""}
                    </span>
                )
            }
        >
            {isLoading ? (
                <div className="space-y-4">
                    {[0, 1, 2].map((i) => (
                        <Shimmer key={i} className="h-10" />
                    ))}
                </div>
            ) : items.length === 0 ? (
                <EmptyState compact icon={Download} title="File d'attente vide" description="Rien ne télécharge pour le moment." />
            ) : (
                <ul className="space-y-4">
                    <AnimatePresence initial={false}>
                        {items.map((dl, i) => {
                            const downloading = dl.status?.toLowerCase() === "downloading";
                            return (
                                <motion.li
                                    key={`${dl.service_type}-${dl.id}`}
                                    layout
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0, transition: { delay: i * 0.05, duration: 0.4, ease: EASE_OUT } }}
                                    exit={{ opacity: 0, x: 10 }}
                                    className="space-y-1.5"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <p className="truncate text-sm font-medium" title={dl.title}>
                                            {dl.title}
                                        </p>
                                        <span className="shrink-0 text-xs font-bold tabular-nums text-primary">{dl.progress.toFixed(0)}%</span>
                                    </div>
                                    <GradientProgress value={dl.progress} active={downloading} tone={downloading ? "primary" : "slate"} />
                                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                        <ClientBadge client={dl.download_client} protocol={dl.protocol} />
                                        {dl.quality && <span className="truncate">{dl.quality}</span>}
                                        {dl.time_left && (
                                            <span className="ml-auto flex shrink-0 items-center gap-1 tabular-nums">
                                                <Clock className="h-2.5 w-2.5" /> {dl.time_left}
                                            </span>
                                        )}
                                    </div>
                                </motion.li>
                            );
                        })}
                    </AnimatePresence>
                </ul>
            )}
        </Panel>
    );
}
