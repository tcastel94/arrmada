"use client";

/**
 * Hub « Santé médiathèque » (/health).
 * ----------------------------------------------------------------
 * Regroupe les anciennes pages Qualité, Doublons et Nettoyage (qui
 * redirigent ici : /quality → ?tab=quality, etc.). Le héros agrège les
 * trois analyses : score de santé global, espace récupérable, nombre de
 * doublons et d'upgrades possibles. L'onglet actif est dans l'URL
 * (?tab=quality|duplicates|cleanup) pour être partageable.
 */
import { HeartPulse, Copy, Gauge, Recycle, RefreshCw } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useQualityOverview } from "@/hooks/use-quality";
import { useDuplicates } from "@/hooks/use-duplicates";
import { reclaimableBytes, useCleanupScan } from "@/hooks/use-cleanup";
import { useUrlState } from "@/hooks/use-url-state";
import { cn } from "@/lib/utils";
import { HealthHero, type HealthTab } from "@/components/health/health-hero";
import { computeHealth } from "@/components/health/health-score";
import { QualityTab } from "@/components/health/quality-tab";
import { DuplicatesTab } from "@/components/health/duplicates-tab";
import { CleanupTab } from "@/components/health/cleanup-tab";

const TABS: { value: HealthTab; label: string; icon: typeof Gauge }[] = [
    { value: "quality", label: "Qualité", icon: Gauge },
    { value: "duplicates", label: "Doublons", icon: Copy },
    { value: "cleanup", label: "Nettoyage", icon: Recycle },
];

export default function HealthPage() {
    const [tab, setTab] = useUrlState<HealthTab>("tab", "quality");
    // Les trois analyses sont lues ici pour le héros ; les onglets
    // réutilisent les mêmes requêtes (React Query les partage, pas de
    // double appel réseau).
    const quality = useQualityOverview();
    const duplicates = useDuplicates();
    const cleanup = useCleanupScan();

    const health = computeHealth(quality.data, duplicates.data, cleanup.data);
    const anyFetching = quality.isFetching || duplicates.isFetching || cleanup.isFetching;
    const activeTab: HealthTab = TABS.some((t) => t.value === tab) ? tab : "quality";

    const counts: Record<HealthTab, number | undefined> = {
        quality: quality.data?.upgradeable.count,
        duplicates: duplicates.data ? duplicates.data.stats.total_duplicates + duplicates.data.stats.total_upgrades : undefined,
        cleanup: cleanup.data
            ? cleanup.data.unmonitored.total +
              cleanup.data.low_quality.total +
              cleanup.data.oversized.total +
              cleanup.data.incomplete_ended.total
            : undefined,
    };

    const rescanAll = () => {
        quality.refetch();
        duplicates.refetch();
        cleanup.refetch();
    };

    return (
        <>
            <Header title="Santé médiathèque" />
            <PageContainer>
                <PageHeader
                    icon={HeartPulse}
                    accent="fuchsia"
                    title="Santé médiathèque"
                    description="Qualité des fichiers, doublons et place perdue : tout ce qui mérite un coup de propre dans ta collection."
                    actions={
                        <Button variant="outline" onClick={rescanAll} disabled={anyFetching}>
                            <RefreshCw className={cn(anyFetching && "animate-spin")} />
                            {anyFetching ? "Analyse…" : "Tout rescanner"}
                        </Button>
                    }
                >
                    <HealthHero
                        health={health}
                        scoreLoading={quality.isLoading || (duplicates.isLoading && cleanup.isLoading)}
                        reclaimable={cleanup.data ? reclaimableBytes(cleanup.data) : undefined}
                        reclaimableLoading={cleanup.isLoading}
                        duplicates={duplicates.data?.stats.total_duplicates}
                        duplicatesLoading={duplicates.isLoading}
                        upgrades={quality.data?.upgradeable.count}
                        upgradesLoading={quality.isLoading}
                        onOpen={setTab}
                    />
                </PageHeader>

                <Tabs value={activeTab} onValueChange={(v) => setTab(v as HealthTab)}>
                    <TabsList aria-label="Sections de la santé médiathèque">
                        {TABS.map((t) => (
                            <TabsTrigger key={t.value} value={t.value}>
                                <t.icon className="h-3.5 w-3.5" />
                                {t.label}
                                {counts[t.value] !== undefined && counts[t.value]! > 0 && (
                                    <span className="rounded-md bg-white/[0.08] px-1.5 text-[10px] font-semibold tabular-nums">
                                        {counts[t.value]!.toLocaleString("fr-FR")}
                                    </span>
                                )}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    <TabsContent value="quality" className="mt-5">
                        <QualityTab />
                    </TabsContent>
                    <TabsContent value="duplicates" className="mt-5">
                        <DuplicatesTab />
                    </TabsContent>
                    <TabsContent value="cleanup" className="mt-5">
                        <CleanupTab />
                    </TabsContent>
                </Tabs>
            </PageContainer>
        </>
    );
}
