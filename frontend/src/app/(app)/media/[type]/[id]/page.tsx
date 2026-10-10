"use client";

/**
 * Fiche détail d'un film ou d'une série : /media/movie/12, /media/series/7.
 * ----------------------------------------------------------------
 * Cette page ne fait qu'ASSEMBLER les briques de src/components/media-detail :
 *   HeroBackdrop   → fanart plein cadre derrière l'en-tête (parallaxe)
 *   MediaHero      → affiche, titre, méta, notes, synopsis, liens
 *   ActionBar      → Lire / Recherche auto / menu « ⋯ »
 *   PlaybackRemote → télécommande Kodi (+ ampli) si CE média est en lecture
 *   DetailTabs     → onglets synchronisés à l'URL (?tab=…)
 *   Edit/Move/DeleteMediaDialog → boîtes de dialogue
 *
 * États gérés : chargement (squelette qui imite le hero), erreur (message
 * réel + Réessayer), type d'URL invalide.
 */
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Clapperboard } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { useMediaDetail } from "@/hooks/use-media";
import { useUrlState } from "@/hooks/use-url-state";
import { HeroBackdrop, MediaHero } from "@/components/media-detail/hero";
import { ActionBar } from "@/components/media-detail/action-bar";
import { PlaybackRemote } from "@/components/media-detail/playback-remote";
import { DetailTabs, defaultTab, type DetailTab } from "@/components/media-detail/detail-tabs";
import { DetailSkeleton } from "@/components/media-detail/detail-skeleton";
import { EditMediaDialog } from "@/components/media-detail/edit-dialog";
import { MoveMediaDialog } from "@/components/media-detail/move-dialog";
import { DeleteMediaDialog } from "@/components/media-detail/delete-dialog";

/** Lien de retour fiable (router.back() casse quand on arrive par un lien direct). */
function BackLink() {
    return (
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground hover:text-foreground">
            <Link href="/media">
                <ArrowLeft /> Médiathèque
            </Link>
        </Button>
    );
}

export default function MediaDetailPage() {
    const params = useParams<{ type: string; id: string }>();
    const type = params.type === "movie" || params.type === "series" ? params.type : null;
    const id = params.id ?? "";

    // Un id vide désactive la requête quand le type d'URL est invalide.
    const { data: media, isLoading, isError, error, refetch, isFetching } = useMediaDetail(type ?? "movie", type ? id : "");
    const [tab, setTab] = useUrlState<string>("tab", defaultTab(type ?? "movie"));

    // Boîtes de dialogue. La clé est incrémentée à chaque ouverture : le
    // formulaire est remonté et repart des valeurs actuelles du média.
    const [dialog, setDialog] = useState<null | "edit" | "move" | "delete">(null);
    const [dialogKey, setDialogKey] = useState(0);
    const open = (d: "edit" | "move" | "delete") => {
        setDialogKey((k) => k + 1);
        setDialog(d);
    };
    const close = (o: boolean) => !o && setDialog(null);

    const goToReleases = () => {
        setTab("releases" satisfies DetailTab);
        document.getElementById("media-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    return (
        // `isolate` : le fond (z-index négatif) reste au-dessus de l'aurora globale.
        <div className="relative isolate min-h-[calc(100dvh-6rem)]">
            <HeroBackdrop src={media?.images?.fanart ?? media?.images?.poster ?? null} />
            <Header title={media?.title ?? (isLoading ? "Chargement…" : "Fiche média")} />

            <PageContainer>
                {!type ? (
                    <EmptyState
                        icon={Clapperboard}
                        title="Type de média inconnu"
                        description={`« ${params.type} » n'est ni un film ni une série.`}
                        action={{ label: "Retour à la médiathèque", href: "/media" }}
                    />
                ) : isLoading ? (
                    <DetailSkeleton />
                ) : isError || !media ? (
                    <div className="pt-10">
                        <ErrorState
                            error={error ?? "Ce média est introuvable."}
                            title={`Impossible de charger ${type === "movie" ? "ce film" : "cette série"}`}
                            onRetry={isFetching ? undefined : () => refetch()}
                        />
                        <div className="flex justify-center">
                            <BackLink />
                        </div>
                    </div>
                ) : (
                    <>
                        <MediaHero
                            media={media}
                            actions={
                                <ActionBar
                                    media={media}
                                    onEdit={() => open("edit")}
                                    onMove={() => open("move")}
                                    onDelete={() => open("delete")}
                                    onManualSearch={goToReleases}
                                />
                            }
                        />
                        <PlaybackRemote media={media} />
                        <DetailTabs media={media} tab={tab} onTabChange={setTab} onMove={() => open("move")} />

                        <EditMediaDialog key={`edit-${dialogKey}`} media={media} open={dialog === "edit"} onOpenChange={close} />
                        <MoveMediaDialog key={`move-${dialogKey}`} media={media} open={dialog === "move"} onOpenChange={close} />
                        <DeleteMediaDialog key={`delete-${dialogKey}`} media={media} open={dialog === "delete"} onOpenChange={close} />
                    </>
                )}
            </PageContainer>
        </div>
    );
}
