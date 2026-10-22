"use client";

/**
 * Notifications — alertes de services, synchros TRaSH, imports…
 * ----------------------------------------------------------------
 * - Regroupées par jour (« Aujourd'hui », « Hier », date), filtres
 *   Toutes / Non lues / Erreurs / Avertissements (?filtre=… dans l'URL).
 * - Types techniques traduits (« service_down » → « Service hors ligne »).
 * - « Marquer comme lue » / « Tout marquer lu » : effet immédiat (mise à
 *   jour optimiste, y compris la cloche du header), toast si l'API échoue.
 */
import { useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { AlertCircle, AlertTriangle, Bell, BellDot, CheckCheck, FilterX, Inbox, Layers, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import { useMarkAllRead, useMarkRead, useNotifications, type NotificationItem } from "@/hooks/use-notifications";
import { useUrlState } from "@/hooks/use-url-state";
import { Segmented } from "@/components/activity/segmented";
import { NotificationCard } from "@/components/activity/notification-card";
import { groupByDay } from "@/components/activity/day-groups";
import { parseApiDate, plural } from "@/lib/format";
import { cn } from "@/lib/utils";

type Filter = "all" | "unread" | "error" | "warning";

const PAGE = 100;

/** Compteur compact, aligné sur la cloche du header (« 99+ »). */
function capCount(n: number): string {
    return n > 99 ? "99+" : String(n);
}

export default function NotificationsPage() {
    const [filter, setFilter] = useUrlState<Filter>("filtre", "all");
    const [limit, setLimit] = useState(PAGE);
    const { data, isLoading, isError, error, refetch, isFetching } = useNotifications(limit);
    const markRead = useMarkRead();
    const markAllRead = useMarkAllRead();

    const all = useMemo(() => data?.items ?? [], [data]);
    const unreadCount = data?.unread_count ?? 0;

    const counts = useMemo(
        () => ({
            unread: all.filter((n) => !n.is_read).length,
            error: all.filter((n) => n.severity === "error").length,
            warning: all.filter((n) => n.severity === "warning").length,
        }),
        [all],
    );

    const filtered = useMemo(() => {
        const keep = (n: NotificationItem) => {
            switch (filter) {
                case "unread":
                    return !n.is_read;
                case "error":
                    return n.severity === "error";
                case "warning":
                    return n.severity === "warning";
                default:
                    return true;
            }
        };
        return all.filter(keep);
    }, [all, filter]);

    const groups = useMemo(() => groupByDay(filtered, (n) => parseApiDate(n.created_at)), [filtered]);

    const handleMarkRead = (id: number) =>
        markRead.mutate(id, {
            onError: (e) => toast.error("Impossible de marquer la notification comme lue", { description: e.message }),
        });

    const handleMarkAll = () =>
        markAllRead.mutate(undefined, {
            onSuccess: () => toast.success("Toutes les notifications sont lues"),
            onError: (e) => toast.error("Impossible de tout marquer comme lu", { description: e.message }),
        });

    const canLoadMore = all.length >= limit;

    // Index global (cascade d'entrée limitée aux premières cartes).
    let running = 0;

    return (
        <>
            <Header title="Notifications" />
            <PageContainer size="narrow">
                <PageHeader
                    icon={Bell}
                    accent="rose"
                    eyebrow="Activité"
                    title="Notifications"
                    description={
                        unreadCount > 0
                            ? `${plural(unreadCount, "notification non lue", "notifications non lues")} : alertes de services, synchros, imports…`
                            : "Tout est lu. Les alertes de services, synchros TRaSH et imports apparaîtront ici."
                    }
                    actions={
                        <>
                            <Button variant="outline" size="icon" aria-label="Rafraîchir les notifications" onClick={() => refetch()}>
                                <RefreshCw className={cn(isFetching && "animate-spin")} />
                            </Button>
                            {unreadCount > 0 && (
                                <Button variant="glow" onClick={handleMarkAll} disabled={markAllRead.isPending}>
                                    {markAllRead.isPending ? <Loader2 className="animate-spin" /> : <CheckCheck />}
                                    Tout marquer lu
                                </Button>
                            )}
                        </>
                    }
                >
                    <StatPill
                        label={unreadCount > 1 ? "non lues" : "non lue"}
                        value={unreadCount > 99 ? capCount(unreadCount) : <AnimatedNumber value={unreadCount} />}
                        icon={BellDot}
                        tone={unreadCount > 0 ? "primary" : "default"}
                    />
                    <StatPill
                        label={counts.error > 1 ? "erreurs" : "erreur"}
                        value={<AnimatedNumber value={counts.error} />}
                        icon={AlertCircle}
                        tone={counts.error > 0 ? "danger" : "default"}
                    />
                    <StatPill
                        label={counts.warning > 1 ? "avertissements" : "avertissement"}
                        value={<AnimatedNumber value={counts.warning} />}
                        icon={AlertTriangle}
                        tone={counts.warning > 0 ? "warning" : "default"}
                    />
                    <StatPill label="au total" value={<AnimatedNumber value={all.length} />} icon={Layers} />
                </PageHeader>

                <Segmented<Filter>
                    ariaLabel="Filtrer les notifications"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: "all", label: "Toutes", count: all.length },
                        { value: "unread", label: "Non lues", count: counts.unread, icon: BellDot, tone: "text-rose-300" },
                        { value: "error", label: "Erreurs", count: counts.error, icon: AlertCircle, tone: "text-destructive" },
                        {
                            value: "warning",
                            // Libellé court sur mobile : les 4 options tiennent sans défilement.
                            label: (
                                <>
                                    <span className="sm:hidden">Avert.</span>
                                    <span className="hidden sm:inline">Avertissements</span>
                                </>
                            ),
                            count: counts.warning,
                            icon: AlertTriangle,
                            tone: "text-warning",
                        },
                    ]}
                />

                {isLoading ? (
                    <NotificationsSkeleton />
                ) : isError ? (
                    <SpotlightCard interactive={false}>
                        <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger les notifications" />
                    </SpotlightCard>
                ) : all.length === 0 ? (
                    <SpotlightCard interactive={false}>
                        <EmptyState
                            icon={Inbox}
                            title="Aucune notification"
                            description="Les alertes de services, synchros TRaSH et autres évènements apparaîtront ici."
                        />
                    </SpotlightCard>
                ) : filtered.length === 0 ? (
                    <SpotlightCard interactive={false}>
                        <EmptyState
                            compact
                            tone={filter === "unread" ? "success" : "default"}
                            icon={filter === "unread" ? CheckCheck : FilterX}
                            title={
                                filter === "unread"
                                    ? "Tout est lu"
                                    : filter === "error"
                                      ? "Aucune erreur"
                                      : "Aucun avertissement"
                            }
                            description="Rien ne correspond à ce filtre parmi les notifications récentes."
                            action={{ label: "Voir toutes les notifications", onClick: () => setFilter("all") }}
                        />
                    </SpotlightCard>
                ) : (
                    <div className="space-y-6">
                        {groups.map((g) => (
                            <section key={g.key} aria-label={g.label}>
                                <div className="mb-2.5 flex items-center gap-3 px-1">
                                    <h2 className="text-sm font-semibold tracking-tight">{g.label}</h2>
                                    <span className="text-[11px] tabular-nums text-muted-foreground">{plural(g.items.length, "notification")}</span>
                                    <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
                                </div>
                                <ul className="space-y-2">
                                    <AnimatePresence initial={true} mode="popLayout">
                                        {g.items.map((n) => {
                                            const index = running++;
                                            return (
                                                <NotificationCard
                                                    key={n.id}
                                                    notif={n}
                                                    index={index}
                                                    pending={markRead.isPending && markRead.variables === n.id}
                                                    onMarkRead={() => handleMarkRead(n.id)}
                                                />
                                            );
                                        })}
                                    </AnimatePresence>
                                </ul>
                            </section>
                        ))}

                        {canLoadMore && (
                            <div className="flex justify-center">
                                <Button variant="outline" onClick={() => setLimit((l) => l + PAGE)} disabled={isFetching}>
                                    {isFetching && <Loader2 className="animate-spin" />}
                                    Charger plus
                                </Button>
                            </div>
                        )}
                    </div>
                )}
            </PageContainer>
        </>
    );
}

function NotificationsSkeleton() {
    return (
        <div className="space-y-2" aria-busy aria-label="Chargement des notifications">
            <Shimmer className="mb-3 h-4 w-28 rounded-md" />
            {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="glass flex items-start gap-3 rounded-2xl p-4">
                    <Shimmer className="h-10 w-10 rounded-xl" />
                    <div className="flex-1 space-y-2">
                        <Shimmer className="h-3.5 w-2/3 rounded-md" />
                        <Shimmer className="h-3 w-full rounded-md" />
                        <Shimmer className="h-3 w-1/3 rounded-md" />
                    </div>
                </div>
            ))}
        </div>
    );
}
