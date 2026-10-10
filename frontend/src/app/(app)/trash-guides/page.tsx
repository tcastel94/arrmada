"use client";

/**
 * TRaSH Guides (/trash-guides) — trois onglets synchronisés à l'URL :
 *  - ?tab=wizard    : assistant de profils selon ton matériel ;
 *  - ?tab=overrides : profils forcés par média (ex-/settings/profile-overrides) ;
 *  - ?tab=sabnzbd   : audit SABnzbd (ex-/settings/sabnzbd-config).
 * Le héros montre l'état des données TRaSH (fraîcheur, nombre de
 * formats/profils) et permet de les resynchroniser.
 */
import { BookMarked, Clock, Database, Loader2, RefreshCw, Target, Wand2, Newspaper } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTrashStatus, useTrashSync } from "@/hooks/use-trash-guides";
import { useUrlState } from "@/hooks/use-url-state";
import { formatNumber, timeAgo } from "@/lib/format";
import { TrashWizard } from "@/components/trash/wizard";
import { OverridesPanel } from "@/components/trash/overrides-panel";
import { SabnzbdPanel } from "@/components/trash/sabnzbd-panel";

type TrashTab = "wizard" | "overrides" | "sabnzbd";

const TABS: { value: TrashTab; label: string; icon: typeof Wand2 }[] = [
    { value: "wizard", label: "Assistant", icon: Wand2 },
    { value: "overrides", label: "Profils par média", icon: Target },
    { value: "sabnzbd", label: "SABnzbd", icon: Newspaper },
];

export default function TrashGuidesPage() {
    const [tab, setTab] = useUrlState<TrashTab>("tab", "wizard");
    const status = useTrashStatus();
    const sync = useTrashSync();
    const activeTab: TrashTab = TABS.some((t) => t.value === tab) ? tab : "wizard";

    const handleSync = () => {
        toast.promise(sync.mutateAsync(true), {
            loading: "Synchronisation avec GitHub…",
            success: "Données TRaSH Guides à jour",
            error: (e: unknown) => `Synchronisation impossible : ${e instanceof Error ? e.message : "erreur inconnue"}`,
        });
    };

    const s = status.data;
    const neverSynced = s && !s.last_sync;

    return (
        <>
            <Header title="TRaSH Guides" />
            <PageContainer>
                <PageHeader
                    icon={BookMarked}
                    accent="orange"
                    eyebrow="Maintenance"
                    title="TRaSH Guides"
                    description="Les réglages recommandés par la communauté TRaSH, appliqués à Sonarr, Radarr et SABnzbd en quelques clics."
                    actions={
                        <Button variant="outline" onClick={handleSync} disabled={sync.isPending}>
                            {sync.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                            Synchroniser
                        </Button>
                    }
                >
                    {status.isLoading ? (
                        <StatPill label="données TRaSH" value="…" />
                    ) : status.isError || !s ? (
                        <StatPill label="statut indisponible" value="—" tone="danger" />
                    ) : (
                        <>
                            <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-background/40 px-3 py-1.5 backdrop-blur">
                                <StatusDot tone={neverSynced ? "offline" : s.is_stale ? "warning" : "online"} />
                                <span className="text-sm font-semibold">
                                    {neverSynced ? "Jamais synchronisé" : s.is_stale ? "Données à rafraîchir" : "Données à jour"}
                                </span>
                            </div>
                            {s.last_sync && (
                                <StatPill icon={Clock} label="dernière synchro" value={timeAgo(s.last_sync)} />
                            )}
                            <StatPill
                                icon={Database}
                                label="formats Sonarr / Radarr"
                                value={`${formatNumber(s.sonarr_cf_count)} / ${formatNumber(s.radarr_cf_count)}`}
                            />
                            <StatPill
                                icon={Target}
                                label="profils Sonarr / Radarr"
                                value={`${formatNumber(s.sonarr_qp_count)} / ${formatNumber(s.radarr_qp_count)}`}
                            />
                        </>
                    )}
                </PageHeader>

                <Tabs value={activeTab} onValueChange={(v) => setTab(v as TrashTab)}>
                    <TabsList aria-label="Sections TRaSH Guides">
                        {TABS.map((t) => (
                            <TabsTrigger key={t.value} value={t.value}>
                                <t.icon className="h-3.5 w-3.5" />
                                {t.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    <TabsContent value="wizard" className="mt-5">
                        <TrashWizard />
                    </TabsContent>
                    <TabsContent value="overrides" className="mt-5">
                        <OverridesPanel />
                    </TabsContent>
                    <TabsContent value="sabnzbd" className="mt-5">
                        <SabnzbdPanel />
                    </TabsContent>
                </Tabs>
            </PageContainer>
        </>
    );
}
