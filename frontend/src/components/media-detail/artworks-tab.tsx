"use client";

/**
 * Onglet « Artworks » de la fiche : TOUTES les images connues du titre.
 * ----------------------------------------------------------------
 * Logos, disques, clearart, personnages, affiches, fonds, vignettes,
 * bannières, images de saisons — chaque variante, groupée par type, avec sa
 * source :
 *   - Dossier : fichier rangé à côté du film / de la série (poster.jpg,
 *     disc.png, clearlogo.png…), servi par ArrMada ;
 *   - fanart.tv / TMDB : récupérées par le serveur (bouton « Artworks » de la
 *     Médiathèque, tâche quotidienne, ou « Actualiser » ici) ;
 *   - Radarr / Sonarr : l'affiche, le fond et le logo choisis là-bas.
 * Un clic ouvre l'image en grand. Le boîtier et son disque sont dans le haut
 * de la fiche, pas ici.
 */
/* eslint-disable @next/next/no-img-element */
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ExternalLink, Heart, ImageOff, Images, RefreshCw } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
    useArtworkGallery,
    useArtworkRefreshOne,
    useArtworkStatus,
    type ArtworkItem,
    type ArtworkKind,
    type ArtworkSource,
} from "@/hooks/use-artwork";
import type { MediaDetail } from "@/hooks/use-media";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Présentation de chaque type : titre, explication, forme de la vignette. */
const KINDS: Record<
    ArtworkKind,
    { label: string; hint: string; frame: string; grid: string; transparent?: boolean }
> = {
    clearlogo: {
        label: "Logos",
        hint: "Titre détouré, affiché à la place du texte",
        frame: "aspect-[16/7]",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
        transparent: true,
    },
    discart: {
        label: "Disques",
        hint: "Rond imprimé du Blu-ray / DVD",
        frame: "aspect-square",
        grid: "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6",
        transparent: true,
    },
    clearart: {
        label: "Clearart",
        hint: "Personnages et titre détourés",
        frame: "aspect-video",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
        transparent: true,
    },
    characterart: {
        label: "Personnages",
        hint: "Un personnage détouré",
        frame: "aspect-square",
        grid: "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6",
        transparent: true,
    },
    poster: {
        label: "Affiches",
        hint: "Toutes les affiches connues",
        frame: "aspect-[2/3]",
        grid: "grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-7",
    },
    keyart: {
        label: "Affiches sans texte",
        hint: "Key art : l'image de l'affiche, sans titre",
        frame: "aspect-[2/3]",
        grid: "grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-7",
    },
    fanart: {
        label: "Fonds",
        hint: "Images de fond (fanart)",
        frame: "aspect-video",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
    },
    landscape: {
        label: "Vignettes",
        hint: "Image paysage avec le titre",
        frame: "aspect-video",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
    },
    banner: {
        label: "Bannières",
        hint: "Bandeau horizontal",
        frame: "aspect-[27/5]",
        grid: "grid-cols-1 md:grid-cols-2",
    },
    seasonposter: {
        label: "Affiches de saisons",
        hint: "Une par saison",
        frame: "aspect-[2/3]",
        grid: "grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-7",
    },
    seasonlandscape: {
        label: "Vignettes de saisons",
        hint: "Image paysage d'une saison",
        frame: "aspect-video",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
    },
    seasonbanner: {
        label: "Bannières de saisons",
        hint: "Bandeau d'une saison",
        frame: "aspect-[27/5]",
        grid: "grid-cols-1 md:grid-cols-2",
    },
    seasonfanart: {
        label: "Fonds de saisons",
        hint: "Image de fond d'une saison",
        frame: "aspect-video",
        grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
    },
};

const SOURCE_LABEL: Record<ArtworkSource, string> = {
    local: "Dossier",
    "fanart.tv": "fanart.tv",
    tmdb: "TMDB",
    radarr: "Radarr",
    sonarr: "Sonarr",
};
const SOURCE_TONE: Record<ArtworkSource, string> = {
    local: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
    "fanart.tv": "bg-primary/15 text-primary ring-primary/30",
    tmdb: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
    radarr: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
    sonarr: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
};
const DISC_LABEL: Record<string, string> = { bluray: "Blu-ray", dvd: "DVD", "3d": "Blu-ray 3D" };

/** Damier sombre derrière les images transparentes (on voit leurs contours). */
const CHECKER =
    "bg-[conic-gradient(#1b2230_25%,#141a25_0_50%,#1b2230_0_75%,#141a25_0)] bg-[length:20px_20px]";

type Filter = "all" | "local" | "sites" | "arr";

function matches(item: ArtworkItem, filter: Filter): boolean {
    if (filter === "all") return true;
    if (filter === "local") return item.source === "local";
    if (filter === "sites") return item.source === "fanart.tv" || item.source === "tmdb";
    return item.source === "radarr" || item.source === "sonarr";
}

function langLabel(lang: string): string {
    if (!lang || lang === "00") return "sans texte";
    return lang.toUpperCase();
}

function ArtworkCard({ item, onOpen }: { item: ArtworkItem; onOpen: (item: ArtworkItem) => void }) {
    const [failed, setFailed] = useState(false);
    const kind = KINDS[item.kind];
    return (
        <motion.figure variants={fadeUp} className="group min-w-0">
            <button
                type="button"
                onClick={() => onOpen(item)}
                disabled={failed}
                aria-label={`Voir en grand : ${kind.label}${item.name ? ` (${item.name})` : ""}, ${SOURCE_LABEL[item.source]}`}
                className={cn(
                    "relative block w-full overflow-hidden rounded-xl ring-1 ring-white/[0.07] transition hover:ring-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                    kind.frame,
                    !failed && kind.transparent ? CHECKER : "bg-white/[0.03]",
                )}
            >
                {failed ? (
                    <span className="flex h-full w-full flex-col items-center justify-center gap-1 text-muted-foreground/60">
                        <ImageOff className="h-4 w-4" aria-hidden />
                        <span className="text-[10px]">Image inaccessible</span>
                    </span>
                ) : (
                    <img
                        src={item.preview || item.url}
                        alt=""
                        loading="lazy"
                        onError={() => setFailed(true)}
                        className={cn(
                            "h-full w-full transition-transform duration-500 ease-smooth group-hover:scale-[1.04]",
                            kind.transparent ? "object-contain p-2" : "object-cover",
                        )}
                    />
                )}
                <span
                    className={cn(
                        "absolute left-1.5 top-1.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 backdrop-blur",
                        SOURCE_TONE[item.source],
                    )}
                >
                    {SOURCE_LABEL[item.source]}
                </span>
            </button>
            <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
                {item.season && <span>Saison {item.season === "0" ? "spéciale" : item.season}</span>}
                {item.disc_type && <span>{DISC_LABEL[item.disc_type] ?? item.disc_type}</span>}
                {item.source !== "local" && item.source !== "radarr" && item.source !== "sonarr" && (
                    <span>{langLabel(item.lang)}</span>
                )}
                {item.likes > 0 && (
                    <span className="inline-flex items-center gap-0.5">
                        <Heart className="h-3 w-3" aria-hidden />
                        {item.likes}
                    </span>
                )}
                {item.name && <span className="truncate font-mono text-[10px]">{item.name}</span>}
            </figcaption>
        </motion.figure>
    );
}

export function ArtworksTab({ media }: { media: MediaDetail }) {
    const type = media.type;
    const gallery = useArtworkGallery(type, media.id);
    const refresh = useArtworkRefreshOne();
    const { data: status } = useArtworkStatus();
    const [filter, setFilter] = useState<Filter>("all");
    const [open, setOpen] = useState<ArtworkItem | null>(null);

    // Tableau stable entre deux rendus (sinon les calculs ci-dessous refont tout à chaque rendu)
    const images = useMemo(() => gallery.data?.images ?? [], [gallery.data]);
    const counts = useMemo(
        () => ({
            all: images.length,
            local: images.filter((i) => matches(i, "local")).length,
            sites: images.filter((i) => matches(i, "sites")).length,
            arr: images.filter((i) => matches(i, "arr")).length,
        }),
        [images],
    );
    const groups = useMemo(() => {
        const visible = images.filter((i) => matches(i, filter));
        return (Object.keys(KINDS) as ArtworkKind[])
            .map((kind) => ({ kind, items: visible.filter((i) => i.kind === kind) }))
            .filter((g) => g.items.length > 0);
    }, [images, filter]);

    const noSite = status && !status.sources.fanart && !status.sources.tmdb;
    const run = () =>
        refresh.mutate(
            { type, id: media.id },
            {
                onSuccess: (res) => {
                    if (res.status === "ok") toast.success("Artworks actualisés", { description: media.title });
                    else if (res.status === "empty")
                        toast.info("Rien de nouveau", { description: "Ni le dossier, ni fanart.tv, ni TMDB n'ont d'image pour ce titre." });
                    else toast.error("Sites injoignables", { description: "fanart.tv / TMDB n'ont pas répondu, réessaie plus tard." });
                },
                onError: (e) => toast.error("Actualisation impossible", { description: e.message }),
            },
        );

    const filters: { key: Filter; label: string }[] = [
        { key: "all", label: "Tout" },
        { key: "local", label: "Dossier du média" },
        { key: "sites", label: "fanart.tv / TMDB" },
        { key: "arr", label: type === "movie" ? "Radarr" : "Sonarr" },
    ];

    return (
        <motion.div variants={stagger(0.04, 0.05)} initial="hidden" animate="show" className="space-y-4">
            <Panel
                title={gallery.data ? `Artworks · ${images.length} image${images.length > 1 ? "s" : ""}` : "Artworks"}
                icon={Images}
                action={
                    <Button variant="outline" size="sm" onClick={run} disabled={refresh.isPending} aria-label="Actualiser les artworks">
                        <RefreshCw className={cn(refresh.isPending && "animate-spin")} />
                        Actualiser<span className="hidden sm:inline"> les artworks</span>
                    </Button>
                }
                bodyClassName="space-y-6 p-5"
            >
                {/* Filtre par source */}
                <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrer par source">
                    {filters.map((f) => (
                        <button
                            key={f.key}
                            type="button"
                            onClick={() => setFilter(f.key)}
                            disabled={f.key !== "all" && counts[f.key] === 0}
                            aria-pressed={filter === f.key}
                            className={cn(
                                "chip transition disabled:opacity-40",
                                filter === f.key && "bg-primary/15 text-primary ring-primary/40",
                            )}
                        >
                            {f.label}
                            <span className="tabular-nums opacity-70">{counts[f.key]}</span>
                        </button>
                    ))}
                    {gallery.data?.fetched_at && (
                        <span className="ml-auto text-[11px] text-muted-foreground">
                            Récupérés le {new Date(gallery.data.fetched_at).toLocaleDateString("fr-FR")}
                        </span>
                    )}
                </div>

                {noSite && (
                    <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
                        Seules les images du dossier et de {type === "movie" ? "Radarr" : "Sonarr"} sont disponibles : ajoute{" "}
                        <code>FANART_CLIENT_KEY</code> (clé personnelle d&apos;un compte fanart.tv gratuit) dans le{" "}
                        <code>.env</code> du serveur pour les logos HD, disques, clearart et toutes les variantes.
                    </p>
                )}

                {gallery.isLoading ? (
                    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                        {Array.from({ length: 8 }).map((_, i) => (
                            <Skeleton key={i} className="aspect-video" />
                        ))}
                    </div>
                ) : gallery.isError ? (
                    <p className="text-sm text-destructive">Galerie indisponible : {gallery.error.message}</p>
                ) : groups.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-white/10 py-10 text-center text-sm text-muted-foreground">
                        <ImageOff className="h-6 w-6" aria-hidden />
                        {gallery.data?.status === "never"
                            ? "Artworks pas encore récupérés pour ce titre."
                            : "Aucune image trouvée pour ce titre."}
                        <Button variant="outline" size="sm" onClick={run} disabled={refresh.isPending}>
                            <RefreshCw className={cn(refresh.isPending && "animate-spin")} />
                            Récupérer maintenant
                        </Button>
                    </div>
                ) : (
                    groups.map(({ kind, items }) => (
                        <section key={kind} aria-labelledby={`artwork-${kind}`} className="space-y-3">
                            <div className="flex items-baseline gap-2">
                                <h3 id={`artwork-${kind}`} className="text-sm font-semibold">
                                    {KINDS[kind].label}
                                </h3>
                                <span className="text-xs tabular-nums text-muted-foreground">{items.length}</span>
                                <span className="truncate text-xs text-muted-foreground/70">· {KINDS[kind].hint}</span>
                            </div>
                            <motion.div variants={stagger(0, 0.02)} className={cn("grid gap-3", KINDS[kind].grid)}>
                                {items.map((item) => (
                                    <ArtworkCard key={item.url} item={item} onOpen={setOpen} />
                                ))}
                            </motion.div>
                        </section>
                    ))
                )}
            </Panel>

            {/* Image en grand */}
            <Dialog open={!!open} onOpenChange={(v) => !v && setOpen(null)}>
                <DialogContent className="max-w-5xl border-white/10 bg-[#0B0F17]/95 p-4">
                    {open && (
                        <>
                            <DialogTitle className="text-base">
                                {KINDS[open.kind].label} · {SOURCE_LABEL[open.source]}
                            </DialogTitle>
                            <DialogDescription className="text-xs">
                                {[
                                    open.name,
                                    open.season && `Saison ${open.season}`,
                                    open.disc_type && (DISC_LABEL[open.disc_type] ?? open.disc_type),
                                    open.source !== "local" && open.source !== "radarr" && open.source !== "sonarr"
                                        ? langLabel(open.lang)
                                        : "",
                                    open.likes > 0 && `${open.likes} j'aime`,
                                ]
                                    .filter(Boolean)
                                    .join(" · ") || media.title}
                            </DialogDescription>
                            <div
                                className={cn(
                                    "flex max-h-[70vh] items-center justify-center overflow-hidden rounded-lg",
                                    KINDS[open.kind].transparent ? CHECKER : "bg-black/40",
                                )}
                            >
                                <img src={open.url} alt={`${KINDS[open.kind].label} de ${media.title}`} className="max-h-[70vh] w-auto object-contain" />
                            </div>
                            <a
                                href={open.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 self-start text-xs font-medium text-primary hover:underline"
                            >
                                Ouvrir l&apos;original dans un nouvel onglet
                                <ExternalLink className="h-3 w-3" aria-hidden />
                            </a>
                        </>
                    )}
                </DialogContent>
            </Dialog>
        </motion.div>
    );
}
