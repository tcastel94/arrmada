"use client";

/**
 * Téléchargements — hub à onglets synchronisés à l'URL :
 *   /downloads              → « File » : file Radarr + Sonarr en direct
 *   /downloads?tab=imports  → « Imports » : imports bloqués, chemins NAS,
 *                             historiques SABnzbd et auto-import
 *                             (ex-page /fichiers, qui redirige ici).
 *
 * Le héros résume la file : éléments actifs, débit estimé (sinon volume
 * restant), fin estimée du plus long et répartition par client.
 */
import { RefreshCw, Download, ArrowDownToLine, Gauge, HardDriveDownload, Timer, ListOrdered, FolderInput } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { getClientMeta } from "@/components/shared/download-client";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDownloads } from "@/hooks/use-downloads";
import { useStuckDownloads } from "@/hooks/use-files";
import { useUrlState } from "@/hooks/use-url-state";
import { QueueTab } from "@/components/downloads/queue-tab";
import { ImportsTab } from "@/components/downloads/imports-tab";
import { bucketOf, parseTimeLeft } from "@/components/downloads/queue-meta";
import { useCachedPosters, useThroughput } from "@/components/downloads/use-queue-insights";
import { formatBytes, formatDuration, formatSpeed } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMemo } from "react";

type Tab = "queue" | "imports";

export default function DownloadsPage() {
    const [tab, setTab] = useUrlState<Tab>("tab", "queue");
    const downloads = useDownloads();
    // Compteur du badge « Imports » (même clé de cache que l'onglet : pas de double requête).
    const stuck = useStuckDownloads();

    const items = downloads.data?.items;
    const throughput = useThroughput(items, downloads.dataUpdatedAt);
    const posters = useCachedPosters(items);

    const summary = useMemo(() => {
        const list = items ?? [];
        let left = 0;
        let longest = 0;
        let active = 0;
        const clients = new Map<string, number>();
        for (const it of list) {
            left += it.size_left_bytes || 0;
            if (bucketOf(it) === "downloading") active += 1;
            const eta = parseTimeLeft(it.time_left);
            if (eta && eta > longest) longest = eta;
            const c = it.download_client || "?";
            clients.set(c, (clients.get(c) ?? 0) + 1);
        }
        return {
            total: list.length,
            active,
            left,
            longest,
            clients: Array.from(clients.entries()).sort((a, b) => b[1] - a[1]),
        };
    }, [items]);

    const stuckCount = stuck.data?.total ?? stuck.data?.items?.length ?? 0;
    const currentTab: Tab = tab === "imports" ? "imports" : "queue";

    return (
        <>
            <Header title="Téléchargements" />
            <PageContainer>
                <PageHeader
                    icon={Download}
                    accent="primary"
                    title="Téléchargements"
                    description="La file Radarr & Sonarr en direct, et les imports à débloquer quand un téléchargement reste coincé."
                    actions={
                        <Button
                            variant="outline"
                            size="icon"
                            aria-label="Rafraîchir la file"
                            onClick={() => {
                                downloads.refetch();
                                stuck.refetch();
                            }}
                        >
                            <RefreshCw className={cn(downloads.isFetching && "animate-spin")} />
                        </Button>
                    }
                >
                    <StatPill
                        label={summary.active > 1 ? "actifs" : "actif"}
                        value={<AnimatedNumber value={summary.active} />}
                        icon={ArrowDownToLine}
                        tone="primary"
                    />
                    <StatPill label="dans la file" value={<AnimatedNumber value={summary.total} />} icon={ListOrdered} />
                    {throughput.total > 0 ? (
                        <StatPill label="débit estimé" value={formatSpeed(throughput.total)} icon={Gauge} tone="success" />
                    ) : (
                        summary.left > 0 && <StatPill label="restants" value={formatBytes(summary.left)} icon={HardDriveDownload} />
                    )}
                    {summary.longest > 0 && (
                        <StatPill label="avant la fin" value={formatDuration(summary.longest)} icon={Timer} />
                    )}
                    {summary.clients.map(([client, count]) => {
                        const m = getClientMeta(client === "?" ? null : client);
                        return <StatPill key={client} label={m.label} value={count} icon={m.icon} />;
                    })}
                    {stuckCount > 0 && (
                        <StatPill label={stuckCount > 1 ? "imports bloqués" : "import bloqué"} value={stuckCount} icon={FolderInput} tone="warning" />
                    )}
                </PageHeader>

                <Tabs value={currentTab} onValueChange={(v) => setTab(v as Tab)}>
                    <TabsList aria-label="Sections des téléchargements">
                        <TabsTrigger value="queue">
                            <ArrowDownToLine className="h-4 w-4" />
                            File
                            {summary.total > 0 && (
                                <span className="rounded-md bg-white/[0.08] px-1.5 text-[10px] tabular-nums leading-4">{summary.total}</span>
                            )}
                        </TabsTrigger>
                        <TabsTrigger value="imports">
                            <FolderInput className="h-4 w-4" />
                            Imports
                            {stuckCount > 0 && (
                                <span className="rounded-md bg-warning/20 px-1.5 text-[10px] tabular-nums leading-4 text-warning">
                                    {stuckCount}
                                </span>
                            )}
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="queue" className="mt-4">
                        <QueueTab
                            data={downloads.data}
                            isLoading={downloads.isLoading}
                            isError={downloads.isError}
                            error={downloads.error}
                            refetch={() => downloads.refetch()}
                            throughput={throughput}
                            posters={posters}
                            onShowImports={() => setTab("imports")}
                        />
                    </TabsContent>
                    <TabsContent value="imports" className="mt-4">
                        <ImportsTab />
                    </TabsContent>
                </Tabs>
            </PageContainer>
        </>
    );
}
