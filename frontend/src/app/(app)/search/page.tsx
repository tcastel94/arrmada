"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Search,
    Film,
    Tv,
    ExternalLink,
    ArrowUpDown,
    Users,
    Loader2,
} from "lucide-react";
import { useUnifiedSearch } from "@/hooks/use-search";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

function formatBytes(bytes: number): string {
    if (!bytes) return "—";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [submitted, setSubmitted] = useState("");
    const { data, isLoading } = useUnifiedSearch(submitted);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.length >= 2) {
            setSubmitted(query);
        }
    };

    return (
        <>
            <Header title="Recherche" />
            <div className="p-6 space-y-6">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">
                        Recherche unifiée
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Recherchez dans votre médiathèque et les indexeurs Prowlarr
                        simultanément
                    </p>
                </div>

                {/* Search Bar */}
                <form onSubmit={handleSearch} className="flex gap-3 max-w-2xl">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Rechercher un film, une série…"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="pl-10 h-11"
                            id="search-input"
                        />
                    </div>
                    <Button type="submit" disabled={query.length < 2 || isLoading} className="h-11">
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Search className="h-4 w-4 mr-2" />
                        )}
                        Rechercher
                    </Button>
                </form>

                {/* Results */}
                {submitted && data && (
                    <Tabs defaultValue="library">
                        <TabsList>
                            <TabsTrigger value="library">
                                Médiathèque ({data.library.total})
                            </TabsTrigger>
                            <TabsTrigger value="indexers">
                                Indexeurs ({data.indexers.total})
                            </TabsTrigger>
                        </TabsList>

                        {/* Library results */}
                        <TabsContent value="library" className="mt-4">
                            {data.library.items.length === 0 ? (
                                <EmptyState
                                    icon={Search}
                                    title="Aucun résultat"
                                    description={`Rien trouvé dans votre médiathèque pour « ${submitted} »`}
                                />
                            ) : (
                                <div className="space-y-2">
                                    {data.library.items.map((item, i) => (
                                        <motion.div
                                            key={`${item.type}-${item.external_id}`}
                                            initial={{ opacity: 0, y: 5 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.03 }}
                                        >
                                            <Card>
                                                <CardContent className="p-4 flex items-center gap-4">
                                                    {/* Poster thumbnail */}
                                                    <div className="w-12 h-16 rounded-md overflow-hidden bg-muted shrink-0">
                                                        {item.poster_url ? (
                                                            <img
                                                                src={item.poster_url}
                                                                alt=""
                                                                className="w-full h-full object-cover"
                                                            />
                                                        ) : (
                                                            <div className="w-full h-full flex items-center justify-center">
                                                                {item.type === "movie" ? (
                                                                    <Film className="h-5 w-5 text-muted-foreground/30" />
                                                                ) : (
                                                                    <Tv className="h-5 w-5 text-muted-foreground/30" />
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>

                                                    <div className="flex-1 min-w-0">
                                                        <p className="font-semibold truncate">
                                                            {item.title}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            {item.year && (
                                                                <span className="text-xs text-muted-foreground">
                                                                    {item.year}
                                                                </span>
                                                            )}
                                                            <Badge variant="outline" className="text-[10px] capitalize">
                                                                {item.type === "movie" ? "Film" : "Série"}
                                                            </Badge>
                                                            <span className="text-xs text-muted-foreground">
                                                                {item.source_service}
                                                            </span>
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-2 shrink-0">
                                                        {item.quality && (
                                                            <Badge className="text-xs">
                                                                {String(item.quality)}
                                                            </Badge>
                                                        )}
                                                        <Badge
                                                            variant={item.has_file ? "default" : "destructive"}
                                                            className="text-xs"
                                                        >
                                                            {item.has_file ? "Disponible" : "Manquant"}
                                                        </Badge>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </motion.div>
                                    ))}
                                </div>
                            )}
                        </TabsContent>

                        {/* Indexer results */}
                        <TabsContent value="indexers" className="mt-4">
                            {isLoading ? (
                                <TableSkeleton rows={5} />
                            ) : data.indexers.items.length === 0 ? (
                                <EmptyState
                                    icon={Search}
                                    title="Aucun résultat"
                                    description={`Aucun résultat sur les indexeurs pour « ${submitted} »`}
                                />
                            ) : (
                                <div className="space-y-2">
                                    {data.indexers.items.map((item, i) => (
                                        <motion.div
                                            key={i}
                                            initial={{ opacity: 0, y: 5 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.02 }}
                                        >
                                            <Card>
                                                <CardContent className="p-4 flex items-center gap-4">
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium truncate">
                                                            {item.title}
                                                        </p>
                                                        <div className="flex items-center gap-3 mt-1">
                                                            <span className="text-xs text-muted-foreground">
                                                                {item.indexer}
                                                            </span>
                                                            {item.categories.length > 0 && (
                                                                <Badge
                                                                    variant="outline"
                                                                    className="text-[10px]"
                                                                >
                                                                    {item.categories[0]}
                                                                </Badge>
                                                            )}
                                                            <Badge
                                                                variant="outline"
                                                                className="text-[10px] uppercase"
                                                            >
                                                                {item.protocol}
                                                            </Badge>
                                                        </div>
                                                    </div>

                                                    {/* Size */}
                                                    <span className="text-xs text-muted-foreground shrink-0 tabular-nums hidden sm:block">
                                                        {formatBytes(item.size_bytes)}
                                                    </span>

                                                    {/* Seeders/Leechers */}
                                                    {item.protocol === "torrent" && (
                                                        <div className="flex items-center gap-2 shrink-0">
                                                            <span className="text-xs text-green-500 tabular-nums">
                                                                ▲{item.seeders}
                                                            </span>
                                                            <span className="text-xs text-red-400 tabular-nums">
                                                                ▼{item.leechers}
                                                            </span>
                                                        </div>
                                                    )}

                                                    {/* Info link */}
                                                    {item.info_url && (
                                                        <a
                                                            href={item.info_url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="text-muted-foreground hover:text-foreground transition-colors"
                                                        >
                                                            <ExternalLink className="h-4 w-4" />
                                                        </a>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        </motion.div>
                                    ))}
                                </div>
                            )}
                        </TabsContent>
                    </Tabs>
                )}

                {/* Initial state */}
                {!submitted && (
                    <EmptyState
                        icon={Search}
                        title="Recherche unifiée"
                        description="Tapez au moins 2 caractères pour rechercher dans votre médiathèque et vos indexeurs"
                    />
                )}
            </div>
        </>
    );
}
