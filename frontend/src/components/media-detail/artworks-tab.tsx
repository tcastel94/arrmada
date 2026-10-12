"use client";

/**
 * Onglet « Artworks » de la fiche : le boîtier et son disque, puis toutes les
 * images connues du titre (logo, disque, clearart, bannière, vignette,
 * affiche, fond), avec leur source et un bouton « Actualiser les artworks ».
 * ----------------------------------------------------------------
 * Les images viennent du serveur (fanart.tv / TMDB, récupérées par le bouton
 * de la Médiathèque ou par la tâche quotidienne) : rien n'est demandé aux
 * sites externes depuis le navigateur, sauf le téléchargement des images.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Disc3, ExternalLink, ImageOff, RefreshCw } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { Button } from "@/components/ui/button";
import { DiscCase, caseFormat } from "@/components/media/disc-art";
import { useArtworkRefreshOne, useArtworkStatus } from "@/hooks/use-artwork";
import type { MediaDetail } from "@/hooks/use-media";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Slot = {
    key: string;
    label: string;
    hint: string;
    url: string | null | undefined;
    /** Image transparente : damier sombre derrière pour voir ses contours. */
    transparent?: boolean;
};

/** « assets.fanart.tv » → « fanart.tv », « image.tmdb.org » → « TMDB »… */
function sourceOf(url: string): string {
    try {
        const host = new URL(url).hostname;
        if (host.includes("fanart.tv")) return "fanart.tv";
        if (host.includes("tmdb")) return "TMDB";
        if (host.includes("thetvdb")) return "TheTVDB";
        return host.replace(/^www\./, "");
    } catch {
        return "";
    }
}

function ArtworkCard({ slot }: { slot: Slot }) {
    const [failed, setFailed] = useState(false);
    const ok = !!slot.url && !failed;
    return (
        <motion.figure variants={fadeUp} className="group min-w-0">
            {/* Cadre identique pour toutes les images (grille régulière), image entière dedans */}
            <div
                className={cn(
                    "relative aspect-[4/3] overflow-hidden rounded-xl ring-1 ring-white/[0.07]",
                    ok && slot.transparent
                        ? "bg-[conic-gradient(#1b2230_25%,#141a25_0_50%,#1b2230_0_75%,#141a25_0)] bg-[length:20px_20px]"
                        : "bg-white/[0.03]",
                )}
            >
                {ok ? (
                    <img
                        src={slot.url!}
                        alt={slot.label}
                        loading="lazy"
                        onError={() => setFailed(true)}
                        className={cn(
                            "h-full w-full transition-transform duration-500 ease-smooth group-hover:scale-[1.03]",
                            "object-contain",
                            slot.transparent && "p-3",
                        )}
                    />
                ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 border border-dashed border-white/10 text-muted-foreground/60">
                        <ImageOff className="h-5 w-5" aria-hidden />
                        <span className="text-[11px]">{failed ? "Image inaccessible" : "Pas encore trouvée"}</span>
                    </div>
                )}
            </div>
            <figcaption className="mt-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                    <p className="text-sm font-medium">{slot.label}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{slot.hint}</p>
                </div>
                {ok && (
                    <a
                        href={slot.url!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="chip shrink-0 hover:text-primary"
                        aria-label={`Ouvrir ${slot.label} en grand (nouvel onglet)`}
                    >
                        {sourceOf(slot.url!)}
                        <ExternalLink className="h-3 w-3" aria-hidden />
                    </a>
                )}
            </figcaption>
        </motion.figure>
    );
}

export function ArtworksTab({ media }: { media: MediaDetail }) {
    const images = media.images ?? { poster: null, fanart: null, banner: null };
    const isMovie = media.type === "movie";
    const refresh = useArtworkRefreshOne();
    const { data: status } = useArtworkStatus();
    const noSource = status && !status.sources.fanart && !status.sources.tmdb;

    const resolution = isMovie ? media.file?.resolution : null;
    const format = isMovie ? caseFormat(resolution, !!media.has_file) : "bluray";

    const slots: Slot[] = [
        { key: "clearlogo", label: "Logo", hint: "Titre détouré, à la place du texte", url: images.clearlogo || images.logo, transparent: true },
        ...(isMovie
            ? [
                  {
                      key: "discart",
                      label: "Disque",
                      hint: images.disc_type ? `Rond imprimé ${images.disc_type === "dvd" ? "DVD" : images.disc_type === "3d" ? "Blu-ray 3D" : "Blu-ray"}` : "Rond imprimé du Blu-ray",
                      url: images.discart,
                      transparent: true,
                  },
              ]
            : []),
        { key: "clearart", label: "Clearart", hint: "Personnages détourés", url: images.clearart, transparent: true },
        { key: "landscape", label: "Vignette", hint: "Image paysage avec le titre", url: images.landscape },
        { key: "banner", label: "Bannière", hint: "Bandeau horizontal", url: images.banner },
        { key: "poster", label: "Affiche", hint: "Choisie dans Radarr / Sonarr", url: images.poster },
        { key: "fanart", label: "Fond", hint: "Image de fond de la fiche", url: images.fanart },
    ];

    const run = () =>
        refresh.mutate(
            { type: media.type, id: media.id },
            {
                onSuccess: (res) => {
                    if (res.status === "ok") toast.success("Artworks actualisés", { description: media.title });
                    else if (res.status === "empty")
                        toast.info("Rien de nouveau", { description: "fanart.tv et TMDB n'ont pas d'image pour ce titre." });
                    else toast.error("Sites injoignables", { description: "fanart.tv / TMDB n'ont pas répondu, réessaie plus tard." });
                },
                onError: (e) => toast.error("Actualisation impossible", { description: e.message }),
            },
        );

    return (
        <motion.div variants={stagger(0.04, 0.05)} initial="hidden" animate="show" className="space-y-4">
            <Panel
                title="Le boîtier"
                icon={Disc3}
                action={
                    <Button variant="outline" size="sm" onClick={run} disabled={refresh.isPending || !!noSource}>
                        <RefreshCw className={cn(refresh.isPending && "animate-spin")} />
                        Actualiser les artworks
                    </Button>
                }
                bodyClassName="p-5"
            >
                <div className="grid items-center gap-6 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
                    <DiscCase
                        poster={images.poster}
                        discart={images.discart}
                        format={format}
                        title={media.title}
                        className="max-w-[340px]"
                    />
                    <div className="space-y-2 text-sm text-muted-foreground">
                        <p>
                            {images.discart
                                ? "Le disque est le rond imprimé du vrai Blu-ray, trouvé sur fanart.tv."
                                : isMovie
                                  ? "Pas encore de rond imprimé pour ce film : le disque est dessiné à partir de l'affiche."
                                  : "Les séries n'ont pas de rond imprimé : le disque est dessiné à partir de l'affiche."}
                        </p>
                        <p>Même animation dans l&apos;appli Kodi : le disque sort du boîtier à l&apos;ouverture de la fiche et y rentre à la fermeture.</p>
                        {noSource && (
                            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-200">
                                Aucune source d&apos;artworks configurée : ajoute <code>FANART_API_KEY</code> (clé gratuite sur fanart.tv) dans
                                le fichier <code>.env</code> du serveur, puis redémarre-le.
                            </p>
                        )}
                    </div>
                </div>
            </Panel>

            <Panel title="Toutes les images" bodyClassName="p-5">
                <motion.div variants={stagger(0.03, 0.04)} className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
                    {slots.map((slot) => (
                        <ArtworkCard key={slot.key} slot={slot} />
                    ))}
                </motion.div>
            </Panel>
        </motion.div>
    );
}
