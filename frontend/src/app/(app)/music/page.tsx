"use client";

/**
 * Musique : les artistes suivis par Lidarr (docs/adr/015-musique-lidarr.md).
 * ----------------------------------------------------------------
 * - Bandeau d'aide si quelque chose manque (Lidarr non déclaré, pas de
 *   bibliothèque « Musique » dans Jellyfin pour écouter).
 * - « Ajouter un artiste » : recherche MusicBrainz via Lidarr ; « Suivre »
 *   l'ajoute et lance la recherche de ses albums.
 * - Albums en téléchargement, puis la grille des artistes (pochettes carrées),
 *   chacun ouvrant sa fiche avec ses albums.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import Link from "next/link";
import { Check, Disc3, FolderDown, Info, Loader2, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton } from "@/components/shared/loading-skeleton";
import { PosterCard } from "@/components/shared/poster-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { useDebounce } from "@/hooks/use-debounce";
import {
    useAddArtist,
    useArtistLookup,
    useArtists,
    useImportDownload,
    useMusicDownloads,
    useMusicQueue,
    useMusicStatus,
    type Artist,
    type ArtistHit,
    type MusicDownloadAlbum,
} from "@/hooks/use-music";
import { formatBytes } from "@/lib/format";

const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";

export default function MusicPage() {
    const status = useMusicStatus();
    const lidarr = status.data?.lidarr ?? false;
    const { data, isLoading, isError, error, refetch } = useArtists(lidarr);
    const artists = data?.artists ?? [];

    return (
        <>
            <Header title="Musique" />
            <PageContainer>
                <PageHeader
                    title="Musique"
                    description="Les artistes suivis par Lidarr. L'écoute passe par Jellyfin, sur la TV comme ici."
                />

                {status.data?.hint && <StatusHint hint={status.data.hint} lidarr={lidarr} />}

                {lidarr && <AddArtist />}
                {lidarr && <Downloads />}
                {lidarr && <PendingImports />}

                {status.isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={status.error} onRetry={() => status.refetch()} />
                    </div>
                ) : !status.isLoading && !lidarr ? null : isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} />
                    </div>
                ) : isLoading || status.isLoading ? (
                    <PosterGridSkeleton count={12} className={GRID} square />
                ) : !artists.length ? (
                    <div className="rounded-2xl bg-card">
                        <EmptyState
                            icon={Disc3}
                            title="Aucun artiste suivi"
                            description="Cherche un artiste ci-dessus et touche « Suivre » : Lidarr télécharge ses albums."
                        />
                    </div>
                ) : (
                    <>
                        <p className="-mb-3 text-[13px] text-muted-foreground">
                            {artists.length} artiste{artists.length > 1 ? "s" : ""}
                        </p>
                        <div className={GRID}>
                            {artists.map((artist) => (
                                <ArtistCard key={artist.id} artist={artist} />
                            ))}
                        </div>
                    </>
                )}
            </PageContainer>
        </>
    );
}

/** Ce qui manque (Lidarr, bibliothèque Jellyfin), dit en clair. */
function StatusHint({ hint, lidarr }: { hint: string; lidarr: boolean }) {
    return (
        <div className="flex items-start gap-3 rounded-2xl bg-warning/10 p-4 text-[14px] text-warning">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 space-y-2">
                <p className="text-foreground/90">{hint}</p>
                {!lidarr && (
                    <Button size="sm" variant="tinted" asChild>
                        <Link href="/settings">Ouvrir les services</Link>
                    </Button>
                )}
            </div>
        </div>
    );
}

function ArtistCard({ artist }: { artist: Artist }) {
    const albums = `${artist.albums} album${artist.albums > 1 ? "s" : ""}`;
    const tracks = artist.tracks_total ? `${artist.tracks_have}/${artist.tracks_total} pistes` : null;
    return (
        <PosterCard
            noEntrance
            square
            type="music"
            title={artist.name}
            subtitle={[albums, tracks].filter(Boolean).join(" · ")}
            posterUrl={artist.poster}
            href={`/music/${artist.id}`}
            dimmed={artist.tracks_have === 0}
        />
    );
}

/** « Ajouter un artiste » : recherche puis « Suivre ». */
function AddArtist() {
    const [term, setTerm] = useState("");
    const debounced = useDebounce(term, 400);
    const lookup = useArtistLookup(debounced);
    const results = lookup.data?.results ?? [];
    const searching = debounced.trim().length >= 2;

    return (
        <Panel title="Ajouter un artiste">
            <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                    id="music-lookup"
                    value={term}
                    onChange={(e) => setTerm(e.target.value)}
                    placeholder="Nom d'un artiste ou d'un groupe"
                    className="pl-9"
                    autoComplete="off"
                />
            </div>
            {searching && (
                <div className="mt-3">
                    {lookup.isLoading ? (
                        <p className="flex items-center gap-2 text-[14px] text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" /> Recherche sur MusicBrainz…
                        </p>
                    ) : lookup.isError ? (
                        <p className="text-[14px] text-destructive">{lookup.error.message}</p>
                    ) : !results.length ? (
                        <p className="text-[14px] text-muted-foreground">Aucun artiste trouvé pour « {debounced.trim()} ».</p>
                    ) : (
                        <ul className="divide-y divide-white/[0.06]">
                            {results.map((hit) => (
                                <LookupRow key={hit.mbid} hit={hit} />
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </Panel>
    );
}

function LookupRow({ hit }: { hit: ArtistHit }) {
    const add = useAddArtist();
    const follow = () =>
        add.mutate(hit.mbid, {
            onSuccess: () => toast.success("Artiste suivi", { description: `${hit.name} : Lidarr cherche ses albums` }),
            onError: (e) => toast.error("Ajout impossible", { description: e.message }),
        });
    const kind = hit.type === "Group" ? "Groupe" : hit.type === "Person" ? "Artiste" : null;

    return (
        <li className="flex items-center gap-3 py-2.5">
            <div className="h-11 w-11 shrink-0 overflow-hidden rounded-lg bg-white/[0.06]">
                {hit.poster ? (
                    <img src={hit.poster} alt="" loading="lazy" className="h-full w-full object-cover" />
                ) : (
                    <Disc3 className="m-3 h-5 w-5 text-white/25" />
                )}
            </div>
            <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-medium">{hit.name}</p>
                <p className="truncate text-[13px] text-muted-foreground">
                    {[kind, ...hit.genres].filter(Boolean).join(" · ") || "MusicBrainz"}
                </p>
            </div>
            {hit.in_library || add.isSuccess ? (
                <span className="flex items-center gap-1 text-[13px] font-medium text-success">
                    <Check className="h-4 w-4" /> Suivi
                </span>
            ) : (
                <Button size="sm" variant="tinted" onClick={follow} disabled={add.isPending}>
                    {add.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
                    Suivre
                </Button>
            )}
        </li>
    );
}

/** Albums en téléchargement (rien affiché quand la file est vide). */
function Downloads() {
    const { data } = useMusicQueue();
    const items = data?.items ?? [];
    if (!items.length) return null;
    return (
        <Panel title="En téléchargement">
            <ul className="space-y-3">
                {items.map((item) => (
                    <li key={item.id} className="space-y-1.5">
                        <div className="flex items-baseline justify-between gap-3 text-[14px]">
                            <span className="truncate font-medium">{item.title}</span>
                            <span className="shrink-0 tabular-nums text-muted-foreground">
                                {Math.round(item.progress * 100)} %{item.time_left ? ` · ${item.time_left}` : ""}
                            </span>
                        </div>
                        <Progress value={item.progress * 100} />
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

/**
 * Musique restée dans le dossier de téléchargements (SABnzbd) et ses
 * sous-dossiers : Lidarr dit, pour chaque album, s'il le reconnaît.
 * « Importer » le range dans la bibliothèque (rien affiché s'il n'y a rien).
 */
function PendingImports() {
    const { data } = useMusicDownloads();
    const albums = data?.albums ?? [];
    if (!albums.length) return null;
    const ready = albums.filter((a) => a.ready).length;
    const ignored = data?.ignored ?? 0;
    return (
        <Panel title="Dans les téléchargements">
            <p className="mb-3 text-[13px] text-muted-foreground">
                {albums.length} album{albums.length > 1 ? "s" : ""} pas encore dans la bibliothèque · {ready} prêt{ready > 1 ? "s" : ""} à
                importer
                {ignored > 0 && ` · ${ignored} bonus de film${ignored > 1 ? "s" : ""} ignoré${ignored > 1 ? "s" : ""}`}
            </p>
            <ul className="divide-y divide-white/[0.06]">
                {albums.map((album) => (
                    <PendingRow key={album.folder} album={album} />
                ))}
            </ul>
        </Panel>
    );
}

function PendingRow({ album }: { album: MusicDownloadAlbum }) {
    const run = useImportDownload();
    const title = [album.artist, album.album].filter(Boolean).join(" – ") || album.name;
    const importIt = () =>
        run.mutate(album.folder, {
            onSuccess: (r) => toast.success("Import lancé", { description: r.message }),
            onError: (e) => toast.error("Import impossible", { description: e.message }),
        });
    return (
        <li className="flex items-center gap-3 py-2.5">
            <FolderDown className="h-5 w-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-medium">{title}</p>
                <p className={album.ready ? "truncate text-[13px] text-muted-foreground" : "truncate text-[13px] text-warning"}>
                    {album.ready
                        ? `${album.tracks} piste${album.tracks > 1 ? "s" : ""} · ${formatBytes(album.size_bytes)} · ${album.name}`
                        : album.reason ?? "Non reconnu par Lidarr"}
                </p>
            </div>
            {album.ready &&
                (run.isSuccess ? (
                    <span className="flex items-center gap-1 text-[13px] font-medium text-success">
                        <Check className="h-4 w-4" /> Lancé
                    </span>
                ) : (
                    <Button size="sm" variant="tinted" onClick={importIt} disabled={run.isPending}>
                        {run.isPending ? <Loader2 className="animate-spin" /> : <FolderDown />}
                        Importer
                    </Button>
                ))}
        </li>
    );
}
