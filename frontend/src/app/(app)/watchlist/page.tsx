"use client";

/**
 * Ma liste (« À voir ») : les films et séries que chaque profil veut voir.
 * ----------------------------------------------------------------
 * - Pastilles en haut : de qui est la liste (« Famille », « Tom »…).
 * - Chaque affiche dit où en est le titre : disponible (ouvre sa fiche),
 *   en attente de téléchargement, ou pas encore dans la médiathèque (bouton
 *   « Demander »). Le bouton ✕ le retire de la liste (pas de la médiathèque).
 * - Les TV affichent la même liste (rangée « Ma liste » du profil qui regarde).
 */
import { Bookmark, Download, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton } from "@/components/shared/loading-skeleton";
import { PosterCard } from "@/components/shared/poster-card";
import { Button } from "@/components/ui/button";
import { WatchlistProfilePicker } from "@/components/watchlist/profile-picker";
import {
    useAddToWatchlist,
    useRemoveFromWatchlist,
    useWatchlist,
    useWatchlistProfile,
    type WatchlistItem,
} from "@/hooks/use-watchlist";

const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";

export default function WatchlistPage() {
    const [profile] = useWatchlistProfile();
    const { data: items, isLoading, isError, error, refetch } = useWatchlist(profile);
    const ready = (items ?? []).filter((i) => i.has_file).length;

    return (
        <>
            <Header title="Ma liste" />
            <PageContainer>
                <PageHeader
                    title="Ma liste"
                    description="Les films et séries à voir, par profil. Les TV affichent la même liste dans leur rangée « Ma liste »."
                />
                <WatchlistProfilePicker className="-mt-3" />

                {items && items.length > 0 && (
                    <p className="-mb-3 text-[13px] text-muted-foreground">
                        {items.length} titre{items.length > 1 ? "s" : ""} · {ready} prêt{ready > 1 ? "s" : ""} à regarder
                    </p>
                )}

                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading ? (
                    <PosterGridSkeleton count={12} className={GRID} />
                ) : !items?.length ? (
                    <div className="rounded-2xl bg-card">
                        <EmptyState
                            icon={Bookmark}
                            title="Ta liste est vide"
                            description="Sur la fiche d'un film ou d'une série, ou dans les suggestions, touche « + Ma liste » pour le retrouver ici et sur la TV."
                            action={{ label: "Voir les suggestions", href: "/search?tab=discover" }}
                        />
                    </div>
                ) : (
                    <div className={GRID}>
                        {items.map((item) => (
                            <WatchlistCard key={item.key} item={item} profile={profile} />
                        ))}
                    </div>
                )}
            </PageContainer>
        </>
    );
}

function WatchlistCard({ item, profile }: { item: WatchlistItem; profile: number | null }) {
    const remove = useRemoveFromWatchlist(profile);
    const add = useAddToWatchlist(profile);
    const href = item.in_library && item.media_id ? `/media/${item.media_type}/${item.media_id}` : undefined;
    const state = item.has_file ? null : item.in_library ? "En attente" : "Pas sur le NAS";

    const request = () =>
        add.mutate(
            { ...item, request: true },
            {
                onSuccess: (r) =>
                    r.download?.status === "ok"
                        ? toast.success("Téléchargement demandé", { description: item.title })
                        : toast.error("Demande impossible", { description: r.download?.message ?? "Radarr / Sonarr a refusé" }),
                onError: (e) => toast.error("Demande impossible", { description: e.message }),
            },
        );

    return (
        <div className="relative">
            <PosterCard
                noEntrance
                title={item.title}
                // État sous le titre (pas en badge sur l'affiche : il y passerait sous le ✕ sur iPhone)
                subtitle={state ?? [item.year, item.media_type === "movie" ? "Film" : "Série"].filter(Boolean).join(" · ")}
                posterUrl={item.poster_url}
                type={item.media_type}
                href={href}
                dimmed={!item.has_file}
                action={
                    !item.in_library ? (
                        <Button size="icon-sm" onClick={request} disabled={add.isPending} aria-label={`Demander ${item.title}`} title="Demander le téléchargement">
                            {add.isPending ? <Loader2 className="animate-spin" /> : <Download />}
                        </Button>
                    ) : undefined
                }
            />
            <button
                type="button"
                onClick={() => remove.mutate(item, { onError: (e) => toast.error("Retrait impossible", { description: e.message }) })}
                aria-label={`Retirer ${item.title} de la liste`}
                title="Retirer de la liste"
                className="absolute right-1.5 top-1.5 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur transition-colors hover:bg-black/80"
            >
                <X className="h-3.5 w-3.5" strokeWidth={2.5} />
            </button>
        </div>
    );
}
