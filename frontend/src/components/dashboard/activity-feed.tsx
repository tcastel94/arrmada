"use client";

/**
 * « Activité récente » de l'Accueil : les derniers évènements de la
 * timeline unifiée (téléchargements, imports, sous-titres, lectures…) en
 * liste groupée iOS, avec lien vers le Journal complet.
 */
import {
    Activity,
    Download,
    CheckCircle2,
    XCircle,
    Captions,
    Play,
    Library,
    Send,
    Cpu,
    type LucideIcon,
} from "lucide-react";
import { useActivityTimeline, type TimelineItem } from "@/hooks/use-activity";
import { Section } from "@/components/shared/section";
import { GroupedList, ListRow } from "@/components/shared/grouped-list";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { timeAgo, formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

// Vignette de chaque catégorie : couleurs système iOS, icône blanche.
const CATEGORY: Record<string, { icon: LucideIcon; tint: string }> = {
    download: { icon: Download, tint: "bg-[#0A84FF]" },
    subtitle: { icon: Captions, tint: "bg-[#5E5CE6]" },
    playback: { icon: Play, tint: "bg-[#BF5AF2]" },
    library: { icon: Library, tint: "bg-[#FF9F0A]" },
    telegram: { icon: Send, tint: "bg-[#64D2FF]" },
    system: { icon: Cpu, tint: "bg-[#8E8E93]" },
};

const ACTION_LABELS: Record<string, string> = {
    grabbed: "Téléchargement lancé",
    grab: "Téléchargement lancé",
    imported: "Importé",
    downloadFolderImported: "Importé",
    downloadFailed: "Échec du téléchargement",
    failed: "Échec",
    sub_download: "Sous-titre téléchargé",
    sub_sync: "Sous-titre synchronisé",
    kodi_play: "Lecture Kodi",
    cast_play: "Lecture Cast",
    search: "Recherche lancée",
    delete: "Supprimé",
    add: "Ajouté",
    episodeFileDeleted: "Fichier supprimé",
    movieFileDeleted: "Fichier supprimé",
    movieDeleted: "Film supprimé",
    seriesDeleted: "Série supprimée",
    episodeFileRenamed: "Renommé",
    movieFileRenamed: "Renommé",
};

function hrefOf(it: TimelineItem) {
    return it.media_type && it.media_id ? `/media/${it.media_type}/${it.media_id}` : undefined;
}

export function ActivityFeedCard({ limit = 6 }: { limit?: number }) {
    const { data, isLoading, isError, error, refetch } = useActivityTimeline({ limit });
    const items = data?.items ?? [];

    return (
        <Section title="Activité récente" href="/activity" hrefLabel="Journal">
            {isLoading ? (
                <Shimmer className="h-[260px] rounded-xl" />
            ) : isError ? (
                <div className="rounded-xl bg-card">
                    <ErrorState compact error={error} onRetry={() => refetch()} />
                </div>
            ) : items.length === 0 ? (
                <div className="rounded-xl bg-card">
                    <EmptyState compact icon={Activity} title="Calme plat" description="Les téléchargements, imports et lectures apparaîtront ici." />
                </div>
            ) : (
                <GroupedList>
                    {items.map((it) => {
                        const cat = CATEGORY[it.category] ?? CATEGORY.system;
                        const label = ACTION_LABELS[it.action] ?? it.action;
                        return (
                            <ListRow
                                key={it.id}
                                href={hrefOf(it)}
                                chevron={false}
                                icon={cat.icon}
                                tint={cat.tint}
                                title={it.title ?? label}
                                subtitle={
                                    <>
                                        <span className={cn(it.status === "ko" && "text-destructive")}>{label}</span>
                                        {it.subtitle ? ` · ${it.subtitle}` : ""}
                                        {it.size_bytes ? ` · ${formatBytes(it.size_bytes)}` : ""}
                                        {it.device ? ` · ${it.device}` : ""}
                                    </>
                                }
                                detail={<span className="text-[13px] tabular-nums">{timeAgo(it.ts * 1000, { short: true })}</span>}
                                accessory={
                                    it.status === "ok" ? (
                                        <CheckCircle2 className="h-4 w-4 text-success" aria-label="Réussi" />
                                    ) : it.status === "ko" ? (
                                        <XCircle className="h-4 w-4 text-destructive" aria-label="Échec" />
                                    ) : undefined
                                }
                            />
                        );
                    })}
                </GroupedList>
            )}
        </Section>
    );
}
