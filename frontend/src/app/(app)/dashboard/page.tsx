"use client";

/**
 * Accueil.
 * ----------------------------------------------------------------
 * Pensé comme l'onglet « Accueil » de l'app TV d'Apple : d'abord ce que
 * l'on regarde, ensuite l'état des choses. Ordre de lecture :
 *   1. Grand titre (« Bonsoir ») + date
 *   2. Alertes, seulement s'il y en a (service hors ligne, disque plein)
 *   3. À l'écran (lecture en cours sur une TV)
 *   4. Reprendre (films / épisodes commencés)
 *   5. Ma liste (titres à voir du profil choisi)
 *   6. Ajoutés récemment
 *   7. À venir | Transferts
 *   8. Chiffres clés (films, séries, stockage, services)
 *   9. Activité récente
 * Les anciens blocs « techniques » (conformité TRaSH, détail des disques,
 * bandeau radar) ont quitté l'Accueil : ils restent dans Santé, TRaSH
 * Guides et Serveur (onglet « Plus »), où on les cherche quand on en a besoin.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ChevronRight, Film, HardDrive, Server, Tv } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { StatTile } from "@/components/shared/stat-tile";
import { NowPlayingCard } from "@/components/dashboard/now-playing";
import { ContinueShelf } from "@/components/dashboard/continue-shelf";
import { WatchlistShelf } from "@/components/dashboard/watchlist-shelf";
import { RecentAdditions } from "@/components/dashboard/recent-additions";
import { ActivityFeedCard } from "@/components/dashboard/activity-feed";
import { DownloadsWidget } from "@/components/dashboard/downloads-widget";
import { UpcomingWidget } from "@/components/dashboard/upcoming";
import { useDashboardStats } from "@/hooks/use-dashboard";
import { useServices, useGlobalHealth } from "@/hooks/use-services";
import { useSystemOverview } from "@/hooks/use-system";
import { SERVICE_META } from "@/lib/constants";
import { formatBytes, greeting, percent } from "@/lib/format";

export default function DashboardPage() {
    const { data: stats } = useDashboardStats();
    const { data: services } = useServices();
    const { data: health } = useGlobalHealth();
    const { data: system } = useSystemOverview();

    // L'heure n'est calculée que dans le navigateur (évite un écart serveur / client).
    const [now, setNow] = useState<Date | null>(null);
    useEffect(() => {
        setNow(new Date());
        const t = setInterval(() => setNow(new Date()), 60_000);
        return () => clearInterval(t);
    }, []);

    // ── Services ────────────────────────────────────────────────
    const arrServices = (services ?? []).filter((s) => s.type in SERVICE_META);
    const statusOf = (id: number, fallback: string) => health?.find((h) => h.service_id === id)?.status ?? fallback;
    const offline = arrServices.filter((s) => statusOf(s.id, s.last_status) === "offline");
    const online = arrServices.filter((s) => statusOf(s.id, s.last_status) === "online").length;

    // ── Disques (dédoublonnés : plusieurs services voient le même volume) ──
    const disks = Array.from(new Map((system?.disks ?? []).map((d) => [`${d.total_bytes}-${d.free_bytes}`, d])).values());
    const diskTotal = disks.reduce((s, d) => s + d.total_bytes, 0);
    const diskUsed = disks.reduce((s, d) => s + d.used_bytes, 0);
    const diskPct = diskTotal ? percent(diskUsed, diskTotal) : undefined;

    // ── Alertes (affichées seulement si utiles) ─────────────────
    const alerts: { label: string; href: string }[] = [];
    if (offline.length > 0)
        alerts.push({
            label: offline.length === 1 ? `${offline[0].name} ne répond plus` : `${offline.map((s) => s.name).join(", ")} ne répondent plus`,
            href: "/settings/services",
        });
    if (diskPct !== undefined && diskPct >= 90) alerts.push({ label: `Stockage presque plein (${Math.round(diskPct)} %)`, href: "/system" });

    const dateLabel = now?.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }) ?? "";

    return (
        <>
            <Header title="Accueil" />
            <PageContainer>
                <PageHeader eyebrow={dateLabel ? dateLabel.charAt(0).toUpperCase() + dateLabel.slice(1) : undefined} title={now ? greeting(now) : "Bonjour"} />

                {alerts.length > 0 && (
                    <div className="space-y-2">
                        {alerts.map((a) => (
                            <Link
                                key={a.label}
                                href={a.href}
                                className="pressable flex items-center gap-3 rounded-xl bg-destructive/[0.12] px-4 py-3 text-[15px]"
                            >
                                <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" />
                                <span className="min-w-0 flex-1 truncate">{a.label}</span>
                                <ChevronRight className="h-4 w-4 shrink-0 text-white/30" />
                            </Link>
                        ))}
                    </div>
                )}

                <NowPlayingCard />
                <ContinueShelf />
                <WatchlistShelf />
                <RecentAdditions />

                <div className="grid grid-cols-1 gap-7 lg:grid-cols-2 lg:gap-6">
                    <UpcomingWidget />
                    <DownloadsWidget />
                </div>

                {/* ── Chiffres clés ─────────────────────────────── */}
                <section>
                    <h2 className="mb-2.5 text-[20px] font-bold tracking-tight">En un coup d&apos;œil</h2>
                    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                        <StatTile
                            label="Films"
                            icon={Film}
                            href="/media?type=movie"
                            value={stats?.movies?.total ?? "—"}
                            detail={stats?.movies ? `${stats.movies.with_files} disponibles` : undefined}
                            gauge={stats?.movies?.total ? percent(stats.movies.with_files, stats.movies.total) : undefined}
                        />
                        <StatTile
                            label="Séries"
                            icon={Tv}
                            href="/media?type=series"
                            value={stats?.series?.total ?? "—"}
                            detail={stats?.series ? `${stats.series.have_episodes} / ${stats.series.total_episodes} épisodes` : undefined}
                            gauge={stats?.series?.total_episodes ? percent(stats.series.have_episodes, stats.series.total_episodes) : undefined}
                        />
                        <StatTile
                            label="Stockage"
                            icon={HardDrive}
                            href="/system"
                            value={diskTotal ? formatBytes(diskTotal - diskUsed) : stats ? formatBytes(stats.total_size_bytes) : "—"}
                            detail={diskTotal ? `libres sur ${formatBytes(diskTotal)}` : stats ? "dans la médiathèque" : undefined}
                            gauge={diskPct}
                            tone={diskPct !== undefined && diskPct >= 90 ? "rose" : diskPct !== undefined && diskPct >= 75 ? "amber" : "emerald"}
                        />
                        <StatTile
                            label="Services"
                            icon={Server}
                            href="/settings/services"
                            value={arrServices.length ? `${online}/${arrServices.length}` : "—"}
                            detail={arrServices.length ? (offline.length ? `${offline.length} hors ligne` : "Tous en ligne") : "Aucun service"}
                            gauge={arrServices.length ? percent(online, arrServices.length) : undefined}
                            tone={offline.length ? "rose" : "emerald"}
                        />
                    </div>
                </section>

                <ActivityFeedCard />
            </PageContainer>
        </>
    );
}
