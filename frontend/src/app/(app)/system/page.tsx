"use client";

/**
 * Serveur & Docker (/system) — deux onglets synchronisés à l'URL :
 *  - ?tab=resources : RAM, CPU, charge, disques (rafraîchis en direct) ;
 *  - ?tab=docker    : conteneurs Unraid (ex-page /docker), puis leurs
 *                    journaux en direct et le diagnostic IA de ces journaux.
 * Le héros résume l'essentiel : RAM, CPU, disques en alerte et
 * conteneurs en marche.
 */
import { Box, Cpu, HardDrive, MemoryStick, AlertTriangle } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { groupDisks, useDiskSpace, useSystemResources } from "@/hooks/use-system";
import { useDockerContainers } from "@/hooks/use-docker";
import { useUrlState } from "@/hooks/use-url-state";
import { ResourcesPanel, useCpuPercent } from "@/components/system/resources-panel";
import { DockerPanel } from "@/components/system/docker-panel";
import { DockerLogsSection } from "@/components/system/docker-logs";

type SystemTab = "resources" | "docker";

/** Ton de pastille selon un taux d'occupation. */
function usagePillTone(pct: number): "success" | "warning" | "danger" {
    if (pct > 90) return "danger";
    if (pct > 75) return "warning";
    return "success";
}

export default function SystemPage() {
    const [tab, setTab] = useUrlState<SystemTab>("tab", "resources");
    const activeTab: SystemTab = tab === "docker" ? "docker" : "resources";
    const resources = useSystemResources();
    const disks = useDiskSpace();
    // Sur l'onglet Ressources, une seule lecture suffit pour la pastille du
    // héros ; l'onglet Docker active le rafraîchissement toutes les 15 s.
    const docker = useDockerContainers({ poll: activeTab === "docker" });
    const { pct: cpuPct } = useCpuPercent(resources.data?.cpu);

    const mem = resources.data?.memory;
    const groups = groupDisks(disks.data?.disks ?? []);
    const fullDisks = groups.filter((g) => g.usage_percent > 90).length;

    return (
        <>
            <Header title="Serveur & Docker" />
            <PageContainer>
                <PageHeader
                    icon={HardDrive}
                    accent="sky"
                    title="Serveur & Docker"
                    description="Ressources du serveur, espace disque et conteneurs de tes services, en direct."
                >
                    {mem && (
                        <StatPill
                            icon={MemoryStick}
                            label="RAM utilisée"
                            value={<AnimatedNumber value={Math.round(mem.usage_percent)} suffix=" %" />}
                            tone={usagePillTone(mem.usage_percent)}
                        />
                    )}
                    {cpuPct !== null && (
                        <StatPill icon={Cpu} label="CPU" value={`${Math.round(cpuPct)} %`} tone={usagePillTone(cpuPct)} />
                    )}
                    {groups.length > 0 && (
                        <StatPill
                            icon={fullDisks > 0 ? AlertTriangle : HardDrive}
                            label={fullDisks > 0 ? `disque${fullDisks > 1 ? "s" : ""} presque plein${fullDisks > 1 ? "s" : ""}` : `disque${groups.length > 1 ? "s" : ""} OK`}
                            value={fullDisks > 0 ? fullDisks : groups.length}
                            tone={fullDisks > 0 ? "danger" : "success"}
                        />
                    )}
                    {docker.data && (
                        <StatPill
                            icon={Box}
                            label="conteneurs en marche"
                            value={`${docker.data.running}/${docker.data.total}`}
                            tone={docker.data.running === docker.data.total ? "success" : "warning"}
                        />
                    )}
                </PageHeader>

                <Tabs value={activeTab} onValueChange={(v) => setTab(v as SystemTab)}>
                    <TabsList aria-label="Sections serveur">
                        <TabsTrigger value="resources">
                            <Cpu className="h-3.5 w-3.5" />
                            Ressources
                        </TabsTrigger>
                        <TabsTrigger value="docker">
                            <Box className="h-3.5 w-3.5" />
                            Docker
                            {docker.data && (
                                <span className="rounded-md bg-white/[0.08] px-1.5 text-[10px] font-semibold tabular-nums">
                                    {docker.data.running}/{docker.data.total}
                                </span>
                            )}
                        </TabsTrigger>
                    </TabsList>
                    <TabsContent value="resources" className="mt-5">
                        <ResourcesPanel />
                    </TabsContent>
                    {/* Radix ne monte que l'onglet actif : les journaux ne sont donc
                        interrogés (toutes les 10 s) que pendant que tu les regardes. */}
                    <TabsContent value="docker" className="mt-5 space-y-6">
                        <DockerPanel />
                        <DockerLogsSection />
                    </TabsContent>
                </Tabs>
            </PageContainer>
        </>
    );
}
