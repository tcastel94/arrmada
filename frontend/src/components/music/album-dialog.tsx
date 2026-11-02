"use client";

/**
 * Fenêtre d'un album (clic sur une pochette de la fiche artiste).
 * ----------------------------------------------------------------
 * Mêmes possibilités que pour un film :
 *  - « Recherche automatique » : Lidarr cherche et prend la meilleure
 *    release selon son profil de qualité (album absent, pistes manquantes,
 *    ou meilleure version d'un album complet) ;
 *  - « Recherche manuelle » : la liste des releases des indexeurs (qualité,
 *    taille, âge, raisons de refus), et « Télécharger » sur celle choisie.
 * La recherche manuelle n'est lancée qu'à la demande : elle interroge tous
 * les indexeurs et peut durer jusqu'à 2 minutes.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { Check, Disc3, Download, Loader2, Search, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ageLabel } from "@/components/media-detail/labels";
import { formatBytes } from "@/lib/format";
import {
    useAlbumReleases,
    useGrabAlbumRelease,
    useSearchAlbum,
    type Album,
    type AlbumRelease,
} from "@/hooks/use-music";

/** Libellé de la recherche automatique selon l'état de l'album. */
export function autoSearchLabel(album: Album): string {
    if (album.status === "complete") return "Chercher une meilleure version";
    if (album.status === "partial") return "Récupérer les pistes manquantes";
    return "Récupérer cet album";
}

/** « 10/12 pistes sur le NAS », « Complet sur le NAS »… */
function stateLine(album: Album): string {
    if (album.status === "complete") return `Complet sur le NAS · ${album.tracks_total} pistes`;
    if (album.status === "partial") return `${album.tracks_have}/${album.tracks_total} pistes sur le NAS`;
    return album.monitored ? "Pas encore sur le NAS (suivi par Lidarr)" : "Pas sur le NAS (non suivi)";
}

export function AlbumDialog({ album, onClose }: { album: Album | null; onClose: () => void }) {
    return (
        <Dialog open={album !== null} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-2xl">
                {/* key : on repart d'une fenêtre vierge pour chaque album */}
                {album && <AlbumBody key={album.id} album={album} />}
            </DialogContent>
        </Dialog>
    );
}

function AlbumBody({ album }: { album: Album }) {
    const [manual, setManual] = useState(false);
    const auto = useSearchAlbum();
    const runAuto = () =>
        auto.mutate(album.id, {
            onSuccess: (r) => toast.success("Recherche lancée", { description: r.message }),
            onError: (e) => toast.error("Recherche impossible", { description: e.message }),
        });

    return (
        <>
            <DialogHeader>
                <div className="flex items-center gap-4">
                    <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-white/[0.06]">
                        {album.cover ? (
                            <img src={album.cover} alt="" className="h-full w-full object-cover" />
                        ) : (
                            <Disc3 className="m-6 h-8 w-8 text-white/20" />
                        )}
                    </div>
                    <div className="min-w-0 text-left">
                        <DialogTitle className="truncate">{album.title}</DialogTitle>
                        <DialogDescription>
                            {[album.type, album.year].filter(Boolean).join(" · ")} — {stateLine(album)}
                        </DialogDescription>
                    </div>
                </div>
            </DialogHeader>

            <div className="flex flex-wrap gap-2">
                <Button variant="tinted" onClick={runAuto} disabled={auto.isPending || auto.isSuccess}>
                    {auto.isPending ? <Loader2 className="animate-spin" /> : auto.isSuccess ? <Check /> : <Download />}
                    {auto.isSuccess ? "Recherche lancée" : autoSearchLabel(album)}
                </Button>
                <Button variant="secondary" onClick={() => setManual(true)} disabled={manual}>
                    <Search />
                    Recherche manuelle
                </Button>
            </div>

            {manual && <ManualSearch albumId={album.id} />}
        </>
    );
}

/** Liste des releases des indexeurs ; les refusées par le profil sont repliées. */
function ManualSearch({ albumId }: { albumId: number }) {
    const { data, isLoading, isError, error, refetch } = useAlbumReleases(albumId, true);
    const grab = useGrabAlbumRelease();
    const [sent, setSent] = useState<string | null>(null);
    const [showRejected, setShowRejected] = useState(false);

    if (isLoading) {
        return (
            <p className="flex items-center gap-2 text-[14px] text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Lidarr interroge les indexeurs (jusqu&apos;à 2 minutes)…
            </p>
        );
    }
    if (isError) {
        return (
            <div className="space-y-2 text-[14px]">
                <p className="text-warning">{error.message}</p>
                <Button size="sm" variant="secondary" onClick={() => refetch()}>
                    Réessayer
                </Button>
            </div>
        );
    }
    const items = data?.items ?? [];
    const accepted = items.filter((r) => !r.rejected);
    const rejected = items.filter((r) => r.rejected);
    if (!items.length) {
        return <p className="text-[14px] text-muted-foreground">Aucune release trouvée sur les indexeurs.</p>;
    }

    const send = (r: AlbumRelease) =>
        grab.mutate(
            { albumId, guid: r.guid, indexerId: r.indexer_id },
            {
                onSuccess: (res) => {
                    setSent(r.guid);
                    toast.success("Téléchargement lancé", { description: res.message });
                },
                onError: (e) => toast.error("Envoi impossible", { description: e.message }),
            },
        );
    const rows = showRejected ? [...accepted, ...rejected] : accepted;

    return (
        <div className="space-y-2">
            <p className="text-[13px] text-muted-foreground">
                {accepted.length} release{accepted.length > 1 ? "s" : ""} acceptée{accepted.length > 1 ? "s" : ""}
                {rejected.length > 0 && (
                    <>
                        {" · "}
                        <button type="button" className="underline" onClick={() => setShowRejected((v) => !v)}>
                            {showRejected ? "masquer" : "voir"} les {rejected.length} refusée{rejected.length > 1 ? "s" : ""}
                        </button>
                    </>
                )}
            </p>
            <ul className="max-h-[50dvh] divide-y divide-white/[0.06] overflow-y-auto rounded-xl bg-white/[0.03]">
                {rows.map((r) => (
                    <li key={r.guid} className="flex items-center gap-3 px-3 py-2.5">
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-[14px] font-medium" title={r.title}>
                                {r.title}
                            </p>
                            <p className="flex flex-wrap items-center gap-x-2 text-[12px] text-muted-foreground">
                                <Badge variant="secondary">{r.quality}</Badge>
                                <span>{formatBytes(r.size_bytes)}</span>
                                <span>{ageLabel(r.age_days)}</span>
                                <span>{r.indexer}</span>
                                {r.seeders !== null && <span>{r.seeders} seeders</span>}
                            </p>
                            {r.rejected && (
                                <p className="mt-0.5 flex items-center gap-1 text-[12px] text-warning">
                                    <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                                    <span className="truncate">{r.rejections.join(" · ")}</span>
                                </p>
                            )}
                        </div>
                        {sent === r.guid ? (
                            <span className="flex items-center gap-1 text-[13px] font-medium text-success">
                                <Check className="h-4 w-4" /> Envoyé
                            </span>
                        ) : (
                            <Button
                                size="sm"
                                variant={r.rejected ? "secondary" : "tinted"}
                                onClick={() => send(r)}
                                disabled={grab.isPending || sent !== null}
                                aria-label={`Télécharger ${r.title}`}
                            >
                                {grab.isPending && grab.variables?.guid === r.guid ? (
                                    <Loader2 className="animate-spin" />
                                ) : (
                                    <Download />
                                )}
                                Télécharger
                            </Button>
                        )}
                    </li>
                ))}
            </ul>
        </div>
    );
}
