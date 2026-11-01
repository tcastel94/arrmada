"use client";

/**
 * Fiche d'un artiste : /music/2.
 * ----------------------------------------------------------------
 * Fond flou tiré de son image, photo, genres, présentation, puis ses albums
 * en pochettes carrées : albums studio d'abord, puis EP et singles, chacun
 * marqué complet, partiel (« 10/12 pistes ») ou manquant (grisé).
 *
 * Actions, comme pour un film ou une série :
 *  - « Chercher les albums manquants » (albums studio absents ou incomplets) ;
 *  - « Actualiser » (discographie relue sur MusicBrainz) ;
 *  - clic sur un album : recherche automatique ou manuelle (AlbumDialog).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeft, Disc3, Download, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton } from "@/components/shared/loading-skeleton";
import { PosterCard } from "@/components/shared/poster-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/format";
import { AlbumDialog } from "@/components/music/album-dialog";
import { useArtist, useRefreshArtist, useSearchArtist, type Album } from "@/hooks/use-music";

const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7";

/** Section d'albums par type, dans l'ordre où l'API les range. */
const SECTIONS: { title: string; match: (a: Album) => boolean }[] = [
    { title: "Albums", match: (a) => a.type === "Album" },
    { title: "EP", match: (a) => a.type === "EP" },
    { title: "Singles", match: (a) => a.type === "Single" },
    { title: "Autres", match: (a) => !["Album", "EP", "Single"].includes(a.type) },
];

function BackLink() {
    return (
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground hover:text-foreground">
            <Link href="/music">
                <ArrowLeft />
                Musique
            </Link>
        </Button>
    );
}

export default function ArtistPage() {
    const params = useParams<{ id: string }>();
    const id = Number(params.id);
    const { data: artist, isLoading, isError, error, refetch } = useArtist(id);
    const [opened, setOpened] = useState<Album | null>(null);

    return (
        <>
            <Header title={artist?.name ?? "Artiste"} />
            <PageContainer>
                <BackLink />
                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading || !artist ? (
                    <PosterGridSkeleton count={6} className={GRID} square />
                ) : (
                    <>
                        <ArtistHero
                            name={artist.name}
                            image={artist.poster}
                            backdrop={artist.fanart ?? artist.poster}
                            genres={artist.genres}
                            overview={artist.overview}
                            facts={[
                                `${artist.albums} album${artist.albums > 1 ? "s" : ""}`,
                                artist.tracks_total ? `${artist.tracks_have}/${artist.tracks_total} pistes sur le NAS` : null,
                                artist.size_bytes ? formatBytes(artist.size_bytes) : null,
                            ]}
                            action={
                                <div className="flex flex-wrap gap-2 pt-1">
                                    <SearchMissing artistId={artist.id} />
                                    <RefreshArtist artistId={artist.id} />
                                </div>
                            }
                        />
                        {artist.album_list.length === 0 ? (
                            <div className="rounded-2xl bg-card">
                                <EmptyState
                                    icon={Disc3}
                                    title="Aucun album pour l'instant"
                                    description="Lidarr récupère la discographie sur MusicBrainz : reviens dans quelques minutes, ou « Actualiser »."
                                />
                            </div>
                        ) : (
                            SECTIONS.map(({ title, match }) => {
                                const albums = artist.album_list.filter(match);
                                if (!albums.length) return null;
                                return (
                                    <Panel key={title} title={title} bodyClassName="p-3 md:p-4">
                                        <div className={GRID}>
                                            {albums.map((album) => (
                                                <AlbumCard key={album.id} album={album} onOpen={() => setOpened(album)} />
                                            ))}
                                        </div>
                                    </Panel>
                                );
                            })
                        )}
                        <AlbumDialog album={opened} onClose={() => setOpened(null)} />
                    </>
                )}
            </PageContainer>
        </>
    );
}

function ArtistHero({
    name,
    image,
    backdrop,
    genres,
    overview,
    facts,
    action,
}: {
    name: string;
    image: string | null;
    backdrop: string | null;
    genres: string[];
    overview: string | null;
    facts: (string | null)[];
    action?: ReactNode;
}) {
    return (
        <section className="relative overflow-hidden rounded-2xl bg-card">
            {backdrop && (
                <img
                    src={backdrop}
                    alt=""
                    aria-hidden
                    className="absolute inset-0 h-full w-full scale-110 object-cover opacity-25 blur-2xl"
                />
            )}
            <div className="relative flex flex-col gap-4 p-4 sm:flex-row sm:items-end md:p-6">
                <div className="h-36 w-36 shrink-0 overflow-hidden rounded-2xl bg-white/[0.06] shadow-xl md:h-44 md:w-44">
                    {image ? (
                        <img src={image} alt={name} className="h-full w-full object-cover" />
                    ) : (
                        <Disc3 className="m-12 h-12 w-12 text-white/20 md:m-16" />
                    )}
                </div>
                <div className="min-w-0 space-y-2">
                    <h1 className="break-words text-ios-large md:text-[2rem] md:leading-[2.375rem]">{name}</h1>
                    <p className="text-[14px] text-muted-foreground">{facts.filter(Boolean).join(" · ")}</p>
                    {genres.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                            {genres.map((g) => (
                                <Badge key={g} variant="secondary">
                                    {g}
                                </Badge>
                            ))}
                        </div>
                    )}
                    {overview && <p className="line-clamp-4 max-w-2xl text-[14px] leading-snug text-foreground/80">{overview}</p>}
                    {action}
                </div>
            </div>
        </section>
    );
}

/**
 * « Chercher les albums manquants » : albums studio absents ou incomplets,
 * suivis au passage s'ils ne l'étaient pas (EP et singles : album par album).
 */
function SearchMissing({ artistId }: { artistId: number }) {
    const run = useSearchArtist();
    return (
        <Button
            size="sm"
            variant="tinted"
            disabled={run.isPending}
            onClick={() =>
                run.mutate(artistId, {
                    onSuccess: (r) =>
                        r.status === "empty"
                            ? toast.info("Rien à chercher", { description: r.message })
                            : toast.success("Recherche lancée", { description: r.message }),
                    onError: (e) => toast.error("Recherche impossible", { description: e.message }),
                })
            }
        >
            {run.isPending ? <Loader2 className="animate-spin" /> : <Download />}
            Chercher les albums manquants
        </Button>
    );
}

/** « Actualiser » : Lidarr relit la discographie (nouveaux albums) et le dossier de l'artiste. */
function RefreshArtist({ artistId }: { artistId: number }) {
    const run = useRefreshArtist();
    return (
        <Button
            size="sm"
            variant="secondary"
            disabled={run.isPending || run.isSuccess}
            onClick={() =>
                run.mutate(artistId, {
                    onSuccess: (r) => toast.success("Actualisation lancée", { description: r.message }),
                    onError: (e) => toast.error("Actualisation impossible", { description: e.message }),
                })
            }
        >
            {run.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Actualiser
        </Button>
    );
}

/** Pochette d'un album : un clic ouvre ses recherches (AlbumDialog). */
function AlbumCard({ album, onOpen }: { album: Album; onOpen: () => void }) {
    const state =
        album.status === "complete"
            ? null
            : album.status === "partial"
              ? `${album.tracks_have}/${album.tracks_total} pistes`
              : album.monitored
                ? "Recherché"
                : "Non suivi";
    return (
        <PosterCard
            noEntrance
            square
            type="music"
            title={album.title}
            subtitle={state ?? (album.year ? String(album.year) : album.type)}
            posterUrl={album.cover}
            dimmed={album.status === "missing"}
            onClick={onOpen}
            badges={
                album.status === "complete" ? (
                    <Badge variant="success">Complet</Badge>
                ) : album.status === "partial" ? (
                    <Badge variant="warning">Partiel</Badge>
                ) : undefined
            }
        />
    );
}
