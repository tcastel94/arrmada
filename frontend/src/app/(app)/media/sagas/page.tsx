"use client";

/**
 * Sagas de films (/media/sagas), sous « Médiathèque » dans le menu.
 * ----------------------------------------------------------------
 * Les sagas viennent de Radarr (collections TMDB) : une saga apparaît dès
 * qu'un de ses films est dans la bibliothèque. Chaque carte montre trois
 * affiches (en éventail au survol), où on en est (« 6/8 films ») et ce qui
 * manque. Filtres : incomplètes, complètes, films annoncés.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { Library, LibraryBig, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SAGA_TONE as TONE, SagaStack } from "@/components/sagas/saga-stack";
import { sagaBadge, useJellyfinCollection, useSagas, type Saga } from "@/hooks/use-sagas";
import { cn } from "@/lib/utils";

type Filter = "all" | "incomplete" | "complete" | "upcoming";

const FILTERS: { value: Filter; label: string; match: (s: Saga) => boolean }[] = [
    { value: "all", label: "Toutes", match: () => true },
    { value: "incomplete", label: "Incomplètes", match: (s) => !s.complete },
    { value: "complete", label: "Complètes", match: (s) => s.complete },
    { value: "upcoming", label: "Films annoncés", match: (s) => s.upcoming > 0 },
];

const GRID = "grid grid-cols-2 gap-x-5 gap-y-7 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6";

export default function SagasPage() {
    const { data, isLoading, isError, error, refetch } = useSagas();
    const [filter, setFilter] = useState<Filter>("all");
    const jellyfin = useJellyfinCollection();
    const syncJellyfin = () =>
        jellyfin.mutate(undefined, {
            onSuccess: (r) => toast.success("Collections Jellyfin", { description: r.message }),
            onError: (e) => toast.error("Collections impossibles", { description: e.message }),
        });
    const shown = useMemo(
        () => (data?.sagas ?? []).filter(FILTERS.find((f) => f.value === filter)!.match),
        [data, filter],
    );

    return (
        <>
            <Header title="Sagas" />
            <PageContainer>
                <PageHeader
                    eyebrow="Médiathèque"
                    title="Sagas"
                    description={
                        data
                            ? `${data.total} saga${data.total > 1 ? "s" : ""} dans ta bibliothèque · ${data.incomplete} incomplète${data.incomplete > 1 ? "s" : ""} · ${data.upcoming} film${data.upcoming > 1 ? "s" : ""} annoncé${data.upcoming > 1 ? "s" : ""}`
                            : "Les films regroupés par saga, d'après Radarr."
                    }
                    actions={
                        <Button size="sm" variant="secondary" onClick={syncJellyfin} disabled={jellyfin.isPending}>
                            {jellyfin.isPending ? <Loader2 className="animate-spin" /> : <LibraryBig />}
                            Collections Jellyfin
                        </Button>
                    }
                />

                <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrer les sagas">
                    {FILTERS.map((f) => (
                        <button
                            key={f.value}
                            type="button"
                            onClick={() => setFilter(f.value)}
                            aria-pressed={filter === f.value}
                            className={cn(
                                "h-8 rounded-full px-3.5 text-[13px] font-medium transition-colors",
                                filter === f.value ? "bg-foreground text-background" : "bg-secondary text-muted-foreground hover:text-foreground",
                            )}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>

                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading ? (
                    <div className={GRID}>
                        {Array.from({ length: 12 }).map((_, i) => (
                            <Shimmer key={i} className="aspect-[1/1.3] rounded-2xl" />
                        ))}
                    </div>
                ) : shown.length === 0 ? (
                    <div className="rounded-2xl bg-card">
                        <EmptyState
                            icon={Library}
                            title={data?.total ? "Aucune saga pour ce filtre" : "Aucune saga pour l'instant"}
                            description={
                                data?.total
                                    ? "Change de filtre pour voir les autres sagas."
                                    : "Une saga apparaît dès qu'un de ses films est dans Radarr."
                            }
                        />
                    </div>
                ) : (
                    <div className={GRID}>
                        {shown.map((saga) => (
                            <SagaCard key={saga.id} saga={saga} />
                        ))}
                    </div>
                )}
            </PageContainer>
        </>
    );
}

function SagaCard({ saga }: { saga: Saga }) {
    const have = saga.available;
    const pct = saga.total ? Math.round((have / saga.total) * 100) : 0;
    const badge = sagaBadge(saga);
    return (
        <Link
            href={`/media/sagas/${saga.id}`}
            className="group grid gap-2.5 rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
            <SagaStack posters={saga.posters} title={saga.title} />
            <div className="min-w-0 space-y-1.5">
                <p className="truncate text-[15px] font-semibold">{saga.title}</p>
                <div className="flex items-center gap-2 text-[12.5px] tabular-nums text-muted-foreground">
                    <span className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.1]">
                        <span
                            className={cn("block h-full rounded-full", pct === 100 ? "bg-success" : "bg-primary")}
                            style={{ width: `${pct}%` }}
                        />
                    </span>
                    {have}/{saga.total}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className={cn("inline-block rounded-md px-1.5 py-1 text-[11px] font-semibold leading-none", TONE[badge.tone])}>
                        {badge.label}
                    </span>
                    {saga.seen > 0 && (
                        <span className="text-[11.5px] text-muted-foreground">
                            {saga.seen} vu{saga.seen > 1 ? "s" : ""}
                        </span>
                    )}
                </div>
            </div>
        </Link>
    );
}
