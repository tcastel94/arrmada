"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
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
    Grid3X3,
    List,
} from "lucide-react";
import { useMedia, type MediaItem } from "@/hooks/use-media";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function MediaCard({ item }: { item: MediaItem }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
        >
            <Link href={`/media/${item.type}/${item.external_id}`}>
                <Card className="overflow-hidden transition-all duration-200 hover:scale-[1.02] hover:border-primary/20 group cursor-pointer">
                    {/* Poster */}
                    <div className="relative aspect-[2/3] bg-muted overflow-hidden">
                        {item.poster_url ? (
                            <img
                                src={item.poster_url}
                                alt={item.title}
                                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                                loading="lazy"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center">
                                {item.type === "movie" ? (
                                    <Film className="h-12 w-12 text-muted-foreground/30" />
                                ) : (
                                    <Tv className="h-12 w-12 text-muted-foreground/30" />
                                )}
                            </div>
                        )}
                        {/* Overlay badges */}
                        <div className="absolute top-2 left-2 flex flex-col gap-1">
                            {item.quality && (
                                <Badge className="text-[10px] bg-black/70 border-0">
                                    {item.quality}
                                </Badge>
                            )}
                        </div>
                        <div className="absolute top-2 right-2">
                            {!item.has_file && (
                                <Badge variant="destructive" className="text-[10px]">
                                    Manquant
                                </Badge>
                            )}
                        </div>
                        {/* Bottom gradient overlay */}
                        <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-black/80 to-transparent" />
                        <div className="absolute bottom-2 left-2 right-2">
                            <p className="text-sm font-semibold text-white truncate">
                                {item.title}
                            </p>
                            <div className="flex items-center gap-2 mt-0.5">
                                {item.year && (
                                    <span className="text-xs text-white/70">{item.year}</span>
                                )}
                                <span className="text-xs text-white/50">
                                    {item.source_service}
                                </span>
                            </div>
                        </div>
                    </div>
                    {/* Meta */}
                    <CardContent className="p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                                {item.type === "movie" ? (
                                    <Film className="h-3 w-3 text-muted-foreground" />
                                ) : (
                                    <Tv className="h-3 w-3 text-muted-foreground" />
                                )}
                                <span className="text-xs text-muted-foreground capitalize">
                                    {item.type === "movie" ? "Film" : "Série"}
                                </span>
                            </div>
                            <span className="text-xs text-muted-foreground">
                                {formatBytes(item.size_bytes)}
                            </span>
                        </div>
                        {item.type === "series" &&
                            item.episodes_have !== undefined &&
                            item.episodes_total !== undefined && (
                                <p className="text-xs text-muted-foreground">
                                    {item.episodes_have}/{item.episodes_total} épisodes
                                </p>
                            )}
                        {item.genres && item.genres.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                {item.genres.slice(0, 3).map((g) => (
                                    <Badge
                                        key={g}
                                        variant="secondary"
                                        className="text-[10px] px-1.5 py-0"
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

    const { data, isLoading } = useMedia({
        type: type === "all" ? undefined : type,
        search: search || undefined,
        sort,
        order,
        page,
        per_page: 48,
    });

    return (
        <>
            <Header title="Médiathèque" />
            <div className="p-6 space-y-6">
                {/* Filters bar */}
                <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Rechercher un titre…"
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setPage(1);
                            }}
                            className="pl-10"
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
                        <TabsList>
                            <TabsTrigger value="all">Tout</TabsTrigger>
                            <TabsTrigger value="movie">Films</TabsTrigger>
                            <TabsTrigger value="series">Séries</TabsTrigger>
                        </TabsList>
                    </Tabs>

                    <Select
                        value={sort}
                        onValueChange={(v) => {
                            setSort(v);
                            setPage(1);
                        }}
                    >
                        <SelectTrigger className="w-[140px]">
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
                        onClick={() => setOrder(order === "asc" ? "desc" : "asc")}
                        className="shrink-0"
                    >
                        {order === "asc" ? "↑" : "↓"}
                    </Button>
                </div>

                {/* Results count */}
                {data && (
                    <p className="text-sm text-muted-foreground">
                        {data.pagination.total} résultat{data.pagination.total !== 1 ? "s" : ""}
                    </p>
                )}

                {/* Grid */}
                {isLoading ? (
                    <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                        {Array.from({ length: 12 }).map((_, i) => (
                            <CardSkeleton key={i} />
                        ))}
                    </div>
                ) : !data || data.items.length === 0 ? (
                    <EmptyState
                        icon={Film}
                        title="Aucun média trouvé"
                        description={
                            search
                                ? `Aucun résultat pour « ${search} »`
                                : "Connectez vos services *arr pour voir votre médiathèque"
                        }
                    />
                ) : (
                    <motion.div
                        className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6"
                        initial="hidden"
                        animate="visible"
                        variants={{
                            visible: { transition: { staggerChildren: 0.03 } },
                        }}
                    >
                        {data.items.map((item) => (
                            <MediaCard
                                key={`${item.type}-${item.external_id}`}
                                item={item}
                            />
                        ))}
                    </motion.div>
                )}

                {/* Pagination */}
                {data && data.pagination.total_pages > 1 && (
                    <div className="flex items-center justify-center gap-4">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1}
                            onClick={() => setPage(page - 1)}
                        >
                            <ChevronLeft className="h-4 w-4 mr-1" />
                            Précédent
                        </Button>
                        <span className="text-sm text-muted-foreground">
                            Page {page} / {data.pagination.total_pages}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= data.pagination.total_pages}
                            onClick={() => setPage(page + 1)}
                        >
                            Suivant
                            <ChevronRight className="h-4 w-4 ml-1" />
                        </Button>
                    </div>
                )}
            </div>
        </>
    );
}
