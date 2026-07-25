"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { useQueryClient } from "@tanstack/react-query";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Film,
    Tv,
    Search,
    ChevronLeft,
    ChevronRight,
    Library,
    SortAsc,
    SortDesc,
    SquareCheck,
    Square,
    RefreshCw,
    CloudDownload,
    Settings,
    Trash2,
    Loader2
} from "lucide-react";
import { useMedia, type MediaItem } from "@/hooks/use-media";
import { useSubtitleStatus } from "@/hooks/use-subtitles";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

/** Per-item French-subtitle state derived from the Bazarr status map. */
type SubState = "present" | "missing" | undefined;

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.03 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 12, scale: 0.97 },
    show: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { duration: 0.3, ease: "easeOut" },
    },
};

function SubBadge({ state }: { state: SubState }) {
    if (state === "present") {
        return (
            <Badge
                className="text-[10px] bg-emerald-600/80 backdrop-blur-sm border-0 text-white"
                title="Sous-titres FR disponibles"
            >
                ST FR ✓
            </Badge>
        );
    }
    if (state === "missing") {
        return (
            <Badge
                className="text-[10px] bg-amber-600/85 backdrop-blur-sm border-0 text-white"
                title="Sous-titres FR manquants"
            >
                ST FR ✗
            </Badge>
        );
    }
    return null;
}

function MediaCard({ item, selectionMode, isSelected, onToggle, subState }: { item: MediaItem, selectionMode?: boolean, isSelected?: boolean, onToggle?: () => void, subState?: SubState }) {
    return (
        <motion.div variants={fadeUp} className="relative">
            {selectionMode && (
                <div 
                    className="absolute top-2 right-2 z-20 cursor-pointer p-1" 
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle?.(); }}
                >
                    {isSelected ? <SquareCheck className="h-5 w-5 text-violet-400 drop-shadow-md" /> : <Square className="h-5 w-5 text-white/50 drop-shadow-md" />}
                </div>
            )}
            <Link href={`/media/${item.type}/${item.external_id}`} onClick={(e) => {
                if (selectionMode) {
                    e.preventDefault();
                    onToggle?.();
                }
            }}>
                <Card className={cn(
                    "overflow-hidden border-0 ring-1 bg-card/40 transition-all duration-300 hover:scale-[1.03] hover:shadow-xl hover:shadow-black/20 group cursor-pointer",
                    isSelected ? "ring-violet-500 ring-2" : "ring-white/5 hover:ring-white/15"
                )}>
                    {/* Poster */}
                    <div className="relative aspect-[2/3] bg-muted/20 overflow-hidden">
                        {item.poster_url ? (
                            <img
                                src={item.poster_url}
                                alt={item.title}
                                className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                                loading="lazy"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-muted/30 to-muted/10">
                                {item.type === "movie" ? (
                                    <Film className="h-12 w-12 text-muted-foreground/20" />
                                ) : (
                                    <Tv className="h-12 w-12 text-muted-foreground/20" />
                                )}
                            </div>
                        )}
                        {/* Top badges */}
                        <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
                            {item.quality && (
                                <Badge className="text-[10px] bg-black/60 backdrop-blur-sm border-0 text-white">
                                    {item.quality}
                                </Badge>
                            )}
                            <SubBadge state={subState} />
                        </div>
                        <div className="absolute top-2 right-2">
                            {!item.has_file && (
                                <Badge className="text-[10px] bg-red-500/80 backdrop-blur-sm border-0 text-white">
                                    Manquant
                                </Badge>
                            )}
                        </div>
                        {/* Bottom gradient */}
                        <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-black/90 via-black/50 to-transparent" />
                        <div className="absolute bottom-2.5 left-2.5 right-2.5">
                            <p className="text-sm font-semibold text-white truncate drop-shadow-lg">
                                {item.title}
                            </p>
                            <div className="flex items-center gap-2 mt-0.5">
                                {item.year && (
                                    <span className="text-[11px] text-white/70">
                                        {item.year}
                                    </span>
                                )}
                                <span className="text-[10px] text-white/40">
                                    {item.source_service}
                                </span>
                            </div>
                        </div>
                    </div>
                    {/* Meta */}
                    <CardContent className="p-2.5 space-y-1.5">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                                {item.type === "movie" ? (
                                    <Film className="h-3 w-3 text-violet-400" />
                                ) : (
                                    <Tv className="h-3 w-3 text-blue-400" />
                                )}
                                <span className="text-[10px] text-muted-foreground">
                                    {item.type === "movie" ? "Film" : "Série"}
                                </span>
                            </div>
                            <span className="text-[10px] text-muted-foreground/60 tabular-nums">
                                {formatBytes(item.size_bytes)}
                            </span>
                        </div>
                        {item.type === "series" &&
                            item.episodes_have !== undefined &&
                            item.episodes_total !== undefined && (
                                <div className="relative h-1 rounded-full bg-muted/30 overflow-hidden">
                                    <div
                                        className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400"
                                        style={{
                                            width: `${item.episodes_total
                                                    ? (item.episodes_have /
                                                        item.episodes_total) *
                                                    100
                                                    : 0
                                                }%`,
                                        }}
                                    />
                                </div>
                            )}
                        {item.genres && item.genres.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                {item.genres.slice(0, 2).map((g) => (
                                    <Badge
                                        key={g}
                                        variant="outline"
                                        className="text-[9px] px-1 py-0 h-3.5 border-white/10"
                                    >
                                        {g}
                                    </Badge>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </Link>
        </motion.div>
    );
}

export default function MediaPage() {
    const [type, setType] = useState<string>("all");
    const [search, setSearch] = useState("");
    const [sort, setSort] = useState("title");
    const [order, setOrder] = useState("asc");
    const [page, setPage] = useState(1);
    // French-subtitle filter: all / missing (sans ST FR) / present.
    const [subFilter, setSubFilter] = useState<"all" | "missing" | "present">("all");

    const queryClient = useQueryClient();

    // Selection state
    const [selectionMode, setSelectionMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

    // Bulk deletion state
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteFiles, setDeleteFiles] = useState(true);
    const [deleteDownloads, setDeleteDownloads] = useState(true);
    const [isDeleting, setIsDeleting] = useState(false);

    const handleBulkDelete = async () => {
        const items = data?.items.filter(i => selectedIds.has(i.external_id));
        if (!items || items.length === 0) return;

        setIsDeleting(true);
        try {
            const promises = items.map(item => 
                apiFetch(`/api/media/${item.type}/${item.external_id}?delete_files=${deleteFiles}&delete_downloads=${deleteDownloads}`, {
                    method: "DELETE"
                })
            );
            await Promise.all(promises);
            
            alert(`${items.length} média(s) supprimé(s) avec succès !`);
            
            setDeleteDialogOpen(false);
            setSelectionMode(false);
            setSelectedIds(new Set());
            queryClient.invalidateQueries({ queryKey: ["media"] });
        } catch (e) {
            alert("Erreur lors de la suppression des médias.");
        } finally {
            setIsDeleting(false);
        }
    };

    const { data, isLoading } = useMedia({
        type: type === "all" ? undefined : type,
        search: search || undefined,
        sort,
        order,
        page,
        per_page: 48,
    });

    // Bazarr French-subtitle status (full library map, keyed by Radarr/Sonarr id).
    const { data: subStatus } = useSubtitleStatus("fr");

    const subStateFor = (item: MediaItem): SubState => {
        if (!subStatus) return undefined;
        if (item.type === "movie") return subStatus.movies[item.external_id];
        // Series map only lists series that still miss FR subs on some episode.
        if (subStatus.series[item.external_id]) return "missing";
        return item.has_file ? "present" : undefined;
    };

    // The filter narrows the current page client-side (the media list itself is
    // paginated server-side, so it applies within the loaded page).
    const visibleItems =
        data?.items.filter((item) => {
            if (subFilter === "all") return true;
            const s = subStateFor(item);
            return subFilter === "missing" ? s === "missing" : s === "present";
        }) ?? [];

    return (
        <>
            <Header title="Médiathèque" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1600px] mx-auto"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
            >
                {/* Hero Header */}
                <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-violet-600/20 via-fuchsia-600/10 to-transparent ring-1 ring-white/5 p-6">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="rounded-xl bg-violet-500/20 p-3">
                                <Library className="h-6 w-6 text-violet-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold tracking-tight">
                                    Médiathèque
                                </h2>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    {data ? (
                                        <>
                                            <span className="font-semibold text-foreground tabular-nums">
                                                {data.pagination.total}
                                            </span>{" "}
                                            résultat{data.pagination.total !== 1 ? "s" : ""}
                                        </>
                                    ) : (
                                        "Chargement..."
                                    )}
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-violet-500/10 blur-3xl" />
                    <div className="absolute -bottom-8 -left-8 w-32 h-32 rounded-full bg-fuchsia-500/10 blur-3xl" />
                </div>

                {/* Filter Bar */}
                <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center rounded-xl ring-1 ring-white/5 bg-card/30 backdrop-blur-sm p-3">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                        <Input
                            placeholder="Rechercher un titre…"
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setPage(1);
                            }}
                            className="pl-10 border-white/10 bg-transparent"
                            id="media-search"
                        />
                    </div>

                    <Tabs
                        value={type}
                        onValueChange={(v) => {
                            setType(v);
                            setPage(1);
                        }}
                    >
                        <TabsList className="bg-muted/30">
                            <TabsTrigger value="all">Tout</TabsTrigger>
                            <TabsTrigger value="movie">
                                <Film className="h-3 w-3 mr-1" />
                                Films
                            </TabsTrigger>
                            <TabsTrigger value="series">
                                <Tv className="h-3 w-3 mr-1" />
                                Séries
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>

                    <Select
                        value={sort}
                        onValueChange={(v) => {
                            setSort(v);
                            setPage(1);
                        }}
                    >
                        <SelectTrigger className="w-[140px] border-white/10 bg-transparent">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="title">Titre</SelectItem>
                            <SelectItem value="year">Année</SelectItem>
                            <SelectItem value="added">Ajouté le</SelectItem>
                            <SelectItem value="size_bytes">Taille</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button
                        variant="outline"
                        size="icon"
                        onClick={() =>
                            setOrder(order === "asc" ? "desc" : "asc")
                        }
                        className="shrink-0 border-white/10"
                    >
                        {order === "asc" ? (
                            <SortAsc className="h-4 w-4" />
                        ) : (
                            <SortDesc className="h-4 w-4" />
                        )}
                    </Button>

                    {/* Subtitle (FR) filter */}
                    <Select value={subFilter} onValueChange={(v) => setSubFilter(v as typeof subFilter)}>
                        <SelectTrigger className="w-[150px] border-white/10 bg-transparent">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">ST FR : tous</SelectItem>
                            <SelectItem value="missing">Sans ST FR</SelectItem>
                            <SelectItem value="present">Avec ST FR</SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Spacer for sm screens */}
                    <div className="hidden lg:flex flex-1" />

                    {/* Action Buttons */}
                    <div className="flex flex-wrap items-center gap-2 mt-2 sm:mt-0 ml-auto shrink-0">
                        {selectionMode ? (
                            <>
                                <span className="text-sm text-muted-foreground mr-2 font-medium">{selectedIds.size} sél.</span>
                                <Button 
                                    size="sm" 
                                    variant="default"
                                    className="bg-violet-600 hover:bg-violet-500"
                                    onClick={async () => {
                                        const items = data?.items.filter(i => selectedIds.has(i.external_id));
                                        if (items?.length) {
                                            await apiFetch("/api/media/scrape", { 
                                                method: "POST", 
                                                headers: { "Content-Type": "application/json" }, 
                                                body: JSON.stringify({ items: items.map(i => ({ movie_id: i.external_id, tmdb_id: i.tmdb_id, source_service: i.source_service })) }) 
                                            });
                                            alert("Scraping démarré pour la sélection !");
                                            setSelectionMode(false);
                                            setSelectedIds(new Set());
                                        }
                                    }}
                                >
                                    <CloudDownload className="h-4 w-4 mr-1.5" />
                                    Scraper SR
                                </Button>
                                <Button 
                                    size="sm" 
                                    variant="destructive"
                                    onClick={() => setDeleteDialogOpen(true)}
                                    disabled={selectedIds.size === 0}
                                >
                                    <Trash2 className="h-4 w-4 mr-1.5" />
                                    Supprimer
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => { setSelectionMode(false); setSelectedIds(new Set()); }}>Annuler</Button>
                            </>
                        ) : (
                            <>
                                <Button size="sm" variant="outline" onClick={() => setSelectionMode(true)} className="border-white/10">
                                    <SquareCheck className="h-4 w-4 mr-1.5" />
                                    Sélectionner
                                </Button>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="border-white/10"
                                    onClick={async () => {
                                        if (data?.items) {
                                            await apiFetch("/api/media/scrape", { 
                                                method: "POST", 
                                                headers: { "Content-Type": "application/json" }, 
                                                body: JSON.stringify({ items: data.items.map(i => ({ movie_id: i.external_id, tmdb_id: i.tmdb_id, source_service: i.source_service })) }) 
                                            });
                                            alert("Scraping de tous les éléments affichés démarré !");
                                        }
                                    }}
                                >
                                    <CloudDownload className="h-4 w-4 mr-1.5" />
                                    Scraper Page
                                </Button>
                                <div className="flex items-center">
                                    <Button 
                                        size="sm"
                                        variant="default"
                                        className="bg-sky-600 hover:bg-sky-500 shadow-lg shadow-sky-900/20 rounded-r-none border-r border-sky-400"
                                        onClick={async () => {
                                            await apiFetch("/api/kodi/sync", { method: "POST" });
                                            alert("Synchronisation Kodi démarrée !");
                                        }}
                                    >
                                        <RefreshCw className="h-4 w-4 mr-1.5" />
                                        Sync Kodi
                                    </Button>
                                    <Button 
                                        size="icon" 
                                        variant="default" 
                                        className="bg-sky-600 hover:bg-sky-500 rounded-l-none h-9 w-9"
                                        asChild
                                    >
                                        <Link href="/settings/kodi" title="Paramètres Kodi">
                                            <Settings className="h-4 w-4" />
                                        </Link>
                                    </Button>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Grid */}
                {isLoading ? (
                    <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
                        {Array.from({ length: 16 }).map((_, i) => (
                            <div
                                key={i}
                                className="aspect-[2/3] rounded-xl bg-muted/15 animate-pulse ring-1 ring-white/5"
                            />
                        ))}
                    </div>
                ) : !data || visibleItems.length === 0 ? (
                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                        <EmptyState
                            icon={Film}
                            title="Aucun média trouvé"
                            description={
                                subFilter !== "all"
                                    ? `Aucun média « ${subFilter === "missing" ? "sans" : "avec"} ST FR » sur cette page`
                                    : search
                                        ? `Aucun résultat pour « ${search} »`
                                        : "Connectez vos services *arr pour voir votre médiathèque"
                            }
                        />
                    </div>
                ) : (
                    <motion.div
                        className="grid gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8"
                        variants={container}
                        initial="hidden"
                        animate="show"
                    >
                        {visibleItems.map((item) => (
                            <MediaCard
                                key={`${item.type}-${item.external_id}`}
                                item={item}
                                subState={subStateFor(item)}
                                selectionMode={selectionMode}
                                isSelected={selectedIds.has(item.external_id)}
                                onToggle={() => {
                                    const next = new Set(selectedIds);
                                    if (next.has(item.external_id)) next.delete(item.external_id);
                                    else next.add(item.external_id);
                                    setSelectedIds(next);
                                }}
                            />
                        ))}
                    </motion.div>
                )}

                {/* Pagination */}
                {data && data.pagination.total_pages > 1 && (
                    <div className="flex items-center justify-center gap-3">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1}
                            onClick={() => setPage(page - 1)}
                            className="gap-1 border-white/10"
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Précédent
                        </Button>
                        <div className="flex items-center gap-1">
                            {Array.from(
                                { length: Math.min(data.pagination.total_pages, 7) },
                                (_, i) => {
                                    const p = i + 1;
                                    return (
                                        <Button
                                            key={p}
                                            variant={p === page ? "default" : "ghost"}
                                            size="sm"
                                            onClick={() => setPage(p)}
                                            className={cn(
                                                "w-8 h-8 p-0 tabular-nums",
                                                p === page && "bg-violet-600 hover:bg-violet-500"
                                            )}
                                        >
                                            {p}
                                        </Button>
                                    );
                                }
                            )}
                            {data.pagination.total_pages > 7 && (
                                <span className="text-xs text-muted-foreground px-1">
                                    …{data.pagination.total_pages}
                                </span>
                            )}
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= data.pagination.total_pages}
                            onClick={() => setPage(page + 1)}
                            className="gap-1 border-white/10"
                        >
                            Suivant
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                )}
            </motion.div>

            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmer la suppression groupée</DialogTitle>
                        <DialogDescription>
                            Voulez-vous vraiment supprimer les {selectedIds.size} média(s) sélectionné(s) ? Cette action est irréversible.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-2 space-y-3">
                        <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={deleteFiles} 
                                onChange={(e) => setDeleteFiles(e.target.checked)}
                                className="h-4.5 w-4.5 rounded border-white/10 bg-muted text-red-600 focus:ring-red-500 focus:ring-offset-background"
                            />
                            <span>Supprimer également les fichiers téléchargés du disque</span>
                        </label>
                        <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={deleteDownloads} 
                                onChange={(e) => setDeleteDownloads(e.target.checked)}
                                className="h-4.5 w-4.5 rounded border-white/10 bg-muted text-red-600 focus:ring-red-500 focus:ring-offset-background"
                            />
                            <span>Supprimer de la file d&apos;attente et de l&apos;historique (SABnzbd, torrents, etc.)</span>
                        </label>
                    </div>
                    <DialogFooter>
                        <Button 
                            variant="outline" 
                            onClick={() => setDeleteDialogOpen(false)}
                            disabled={isDeleting}
                        >
                            Annuler
                        </Button>
                        <Button 
                            variant="destructive" 
                            onClick={handleBulkDelete}
                            disabled={isDeleting || selectedIds.size === 0}
                        >
                            {isDeleting ? "Suppression..." : "Supprimer"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
