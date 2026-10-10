"use client";

/**
 * Dashboard — « passerelle de commandement » d'ArrMada.
 * ----------------------------------------------------------------
 * Ordre de lecture (du plus urgent au plus contemplatif) :
 *   1. Bandeau d'accueil + faits marquants (services KO, téléchargements…)
 *   2. Lecture en cours (si Kodi joue quelque chose)
 *   3. 4 indicateurs clés avec jauges animées
 *   4. État des services
 *   5. Ajouts récents (carrousel)
 *   6. Activité | Téléchargements + À venir
 *   7. Stockage + conformité TRaSH
 */
import { motion } from "framer-motion";
import { Film, Tv, HardDrive, Download } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { BridgeHero, type BridgeFact } from "@/components/dashboard/bridge-hero";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { NowPlayingCard } from "@/components/dashboard/now-playing";
import { ServicesStrip } from "@/components/dashboard/services-strip";
import { RecentAdditions } from "@/components/dashboard/recent-additions";
import { ActivityFeedCard } from "@/components/dashboard/activity-feed";
import { DownloadsWidget } from "@/components/dashboard/downloads-widget";
import { UpcomingWidget } from "@/components/dashboard/upcoming";
import { StoragePanel } from "@/components/dashboard/storage-panel";
import { TrashPanel } from "@/components/dashboard/trash-panel";
import { useDashboardStats } from "@/hooks/use-dashboard";
import { useDownloads } from "@/hooks/use-downloads";
import { useServices, useGlobalHealth } from "@/hooks/use-services";
import { useSystemOverview } from "@/hooks/use-system";
import { useCalendar } from "@/hooks/use-calendar";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { SERVICE_META } from "@/lib/constants";
import { formatBytes, percent, plural } from "@/lib/format";
import { stagger, fadeUp } from "@/lib/motion";

export default function DashboardPage() {
    const { data: stats } = useDashboardStats();
    const { data: downloads } = useDownloads();
    const { data: services } = useServices();
    const { data: health } = useGlobalHealth();
    const { data: system } = useSystemOverview();
    const { data: calendar } = useCalendar(14);
    const { missing } = useNavBadges();

    // ── Indicateurs dérivés ─────────────────────────────────────
    const dlItems = downloads?.items ?? [];
    const activeDownloads = downloads?.total ?? dlItems.length;
    const avgProgress = dlItems.length ? dlItems.reduce((s, d) => s + (d.progress || 0), 0) / dlItems.length : 0;

    const arrServices = (services ?? []).filter((s) => s.type in SERVICE_META);
    const offline = arrServices.filter((s) => (health?.find((h) => h.service_id === s.id)?.status ?? s.last_status) === "offline");

    // Occupation disque globale (dédoublonnée : plusieurs services voient le même FS).
    const disks = Array.from(new Map((system?.disks ?? []).map((d) => [`${d.total_bytes}-${d.free_bytes}`, d])).values());
    const diskTotal = disks.reduce((s, d) => s + d.total_bytes, 0);
    const diskUsed = disks.reduce((s, d) => s + d.used_bytes, 0);

    const weekLimit = Date.now() + 7 * 86_400_000;
    const upcomingCount = (calendar?.items ?? []).filter((e) => new Date(e.air_date).getTime() <= weekLimit).length;

    // ── Faits marquants du bandeau d'accueil ────────────────────
    const facts: BridgeFact[] = [];
    if (arrServices.length > 0) {
        facts.push(
            offline.length > 0
                ? { label: `${offline.map((s) => s.name).join(", ")} hors ligne`, tone: "danger" }
                : { label: `${arrServices.length}/${arrServices.length} services en ligne`, tone: "success" },
        );
    }
    if (activeDownloads > 0) facts.push({ label: plural(activeDownloads, "téléchargement") + " en cours", tone: "primary" });
    if (upcomingCount > 0) facts.push({ label: plural(upcomingCount, "sortie") + " cette semaine" });
    if (missing > 0) facts.push({ label: plural(missing, "média manquant", "médias manquants"), tone: "warning" });

    return (
        <>
            <Header title="Dashboard" />
            <PageContainer>
                <BridgeHero facts={facts} />

                <NowPlayingCard />

                {/* ── Indicateurs clés ─────────────────────────── */}
                <motion.div
                    variants={stagger(0.2, 0.08)}
                    initial="hidden"
                    animate="show"
                    className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
                >
                    <KpiCard
                        label="Films"
                        icon={Film}
                        tone="violet"
                        href="/media?type=movie"
                        value={<AnimatedNumber value={stats?.movies?.total} />}
                        sub={stats?.movies ? `${stats.movies.with_files} sur disque · ${stats.movies.monitored} surveillés` : "—"}
                        gauge={stats?.movies ? percent(stats.movies.with_files, stats.movies.total) : undefined}
                        gaugeLabel="dispo"
                    />
                    <KpiCard
                        label="Séries"
                        icon={Tv}
                        tone="brand"
                        href="/media?type=series"
                        value={<AnimatedNumber value={stats?.series?.total} />}
                        sub={stats?.series ? `${stats.series.have_episodes} / ${stats.series.total_episodes} épisodes` : "—"}
                        gauge={stats?.series ? percent(stats.series.have_episodes, stats.series.total_episodes) : undefined}
                        gaugeLabel="épisodes"
                    />
                    <KpiCard
                        label="Stockage"
                        icon={HardDrive}
                        tone={diskTotal && diskUsed / diskTotal > 0.9 ? "rose" : "emerald"}
                        href="/system"
                        value={<span className="tabular-nums">{stats ? formatBytes(stats.total_size_bytes) : "—"}</span>}
                        sub={stats ? `${stats.total_items} fichiers dans la bibliothèque` : "—"}
                        gauge={diskTotal ? percent(diskUsed, diskTotal) : undefined}
                        gaugeLabel="disque"
                    />
                    <KpiCard
                        label="Téléchargements"
                        icon={Download}
                        tone="primary"
                        href="/downloads"
                        value={<AnimatedNumber value={activeDownloads} />}
                        sub={activeDownloads > 0 ? "en cours dans la file" : "file d'attente vide"}
                        gauge={activeDownloads > 0 ? avgProgress : undefined}
                        gaugeLabel="moyenne"
                    />
                </motion.div>

                <ServicesStrip />

                <RecentAdditions />

                {/* ── Activité | Téléchargements + À venir ─────── */}
                {/* grid-cols-1 explicite : sans lui, la colonne implicite prend la
                    largeur du plus long texte non coupé (noms de releases) et la
                    page déborde horizontalement sur mobile. */}
                <motion.div variants={stagger(0.1, 0.1)} initial="hidden" animate="show" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                    <motion.div variants={fadeUp} className="lg:col-span-7">
                        <ActivityFeedCard />
                    </motion.div>
                    <motion.div variants={fadeUp} className="space-y-6 lg:col-span-5">
                        <DownloadsWidget />
                        <UpcomingWidget />
                    </motion.div>
                </motion.div>

                {/* ── Stockage + TRaSH ─────────────────────────── */}
                <motion.div variants={stagger(0.1, 0.1)} initial="hidden" animate="show" className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <motion.div variants={fadeUp}>
                        <StoragePanel />
                    </motion.div>
                    <motion.div variants={fadeUp}>
                        <TrashPanel />
                    </motion.div>
                </motion.div>
            </PageContainer>
        </>
    );
}
