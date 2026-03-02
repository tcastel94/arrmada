"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Search,
    Film,
    Tv,
    ExternalLink,
    Loader2,
    Library,
    Globe,
    Sparkles,
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

const fadeUp = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

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
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1200px] mx-auto"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                {/* Hero + Search */}
                <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-teal-600/20 via-cyan-600/10 to-transparent ring-1 ring-white/5 p-6">
                    <div className="flex items-center gap-4 mb-5">
                        <div className="rounded-xl bg-teal-500/20 p-3">
                            <Sparkles className="h-6 w-6 text-teal-400" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold tracking-tight">
                                Recherche unifiée
                            </h2>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                Médiathèque et indexeurs Prowlarr simultanément
                            </p>
                        </div>
                    </div>

                    <form onSubmit={handleSearch} className="flex gap-3 max-w-2xl">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                            <Input
                                placeholder="Rechercher un film, une série…"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                className="pl-10 h-11 border-white/10 bg-black/20 backdrop-blur-sm"
                                id="search-input"
                            />
                        </div>
                        <Button
                            type="submit"
                            disabled={query.length < 2 || isLoading}
                            className="h-11 gap-2 bg-teal-600 hover:bg-teal-500"
                        >
                            {isLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Search className="h-4 w-4" />
                            )}
                            Rechercher
                        </Button>
                    </form>

                    <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-teal-500/10 blur-3xl" />
                </div>

                {/* Results */}
                {submitted && data && (
                    <motion.div variants={fadeUp} initial="hidden" animate="show">
                        <Tabs defaultValue="library">
                            <TabsList className="bg-muted/30">
                                <TabsTrigger value="library">
                                    <Library className="h-3 w-3 mr-1.5" />
                                    Médiathèque ({data.library.total})
                                </TabsTrigger>
                                <TabsTrigger value="indexers">
                                    <Globe className="h-3 w-3 mr-1.5" />
                                    Indexeurs ({data.indexers.total})
                                </TabsTrigger>
                            </TabsList>

                            {/* Library results */}
                            <TabsContent value="library" className="mt-4 space-y-2">
                                {data.library.items.length === 0 ? (
                                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                                        <EmptyState
                                            icon={Search}
                                            title="Aucun résultat"
                                            description={`Rien trouvé dans votre médiathèque pour « ${submitted} »`}
                                        />
                                    </div>
                                ) : (
                                    data.library.items.map((item, i) => (
                                        <motion.div
                                            key={`${item.type}-${item.external_id}`}
                                            initial={{ opacity: 0, y: 8 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.03 }}
                                        >
                                            <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm hover:ring-white/10 transition-all">
                                                <CardContent className="p-4 flex items-center gap-4">
                                                    <div className="w-12 h-16 rounded-lg overflow-hidden bg-muted/20 shrink-0 ring-1 ring-white/5">
                                                        {item.poster_url ? (
                                                            <img
                                                                src={item.poster_url}
                                                                alt=""
                                                                className="w-full h-full object-cover"
                                                            />
                                                        ) : (
                                                            <div className="w-full h-full flex items-center justify-center">
                                                                {item.type === "movie" ? (
                                                                    <Film className="h-5 w-5 text-muted-foreground/20" />
                                                                ) : (
                                                                    <Tv className="h-5 w-5 text-muted-foreground/20" />
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
                                                                <span className="text-xs text-muted-foreground/60">
                                                                    {item.year}
                                                                </span>
                                                            )}
                                                            <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-white/10 capitalize">
                                                                {item.type === "movie" ? "Film" : "Série"}
                                                            </Badge>
                                                            <span className="text-[10px] text-muted-foreground/50">
                                                                {item.source_service}
                                                            </span>
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-2 shrink-0">
                                                        {item.quality && (
                                                            <Badge className="text-[10px] bg-muted/30 border-0">
                                                                {String(item.quality)}
                                                            </Badge>
                                                        )}
                                                        <Badge
                                                            className={cn(
                                                                "text-[10px] border-0",
                                                                item.has_file
                                                                    ? "bg-emerald-500/20 text-emerald-400"
                                                                    : "bg-red-500/20 text-red-400"
                                                            )}
                                                        >
                                                            {item.has_file ? "Disponible" : "Manquant"}
                                                        </Badge>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </motion.div>
                                    ))
                                )}
                            </TabsContent>

                            {/* Indexer results */}
                            <TabsContent value="indexers" className="mt-4 space-y-2">
                                {isLoading ? (
                                    <TableSkeleton rows={5} />
                                ) : data.indexers.items.length === 0 ? (
                                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                                        <EmptyState
                                            icon={Search}
                                            title="Aucun résultat"
                                            description={`Aucun résultat sur les indexeurs pour « ${submitted} »`}
                                        />
                                    </div>
                                ) : (
                                    data.indexers.items.map((item, i) => (
                                        <motion.div
                                            key={i}
                                            initial={{ opacity: 0, y: 8 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.02 }}
                                        >
                                            <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm hover:ring-white/10 transition-all">
                                                <CardContent className="p-4 flex items-center gap-4">
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium truncate">
                                                            {item.title}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className="text-[10px] text-muted-foreground/60">
                                                                {item.indexer}
                                                            </span>
                                                            {item.categories.length > 0 && (
                                                                <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-white/10">
                                                                    {item.categories[0]}
                                                                </Badge>
                                                            )}
                                                            <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-white/10 uppercase">
                                                                {item.protocol}
                                                            </Badge>
                                                        </div>
                                                    </div>

                                                    <span className="text-xs text-muted-foreground/60 shrink-0 tabular-nums hidden sm:block">
                                                        {formatBytes(item.size_bytes)}
                                                    </span>

                                                    {item.protocol === "torrent" && (
                                                        <div className="flex items-center gap-2 shrink-0">
                                                            <span className="text-xs text-emerald-400 tabular-nums">
                                                                ▲{item.seeders}
                                                            </span>
                                                            <span className="text-xs text-red-400 tabular-nums">
                                                                ▼{item.leechers}
                                                            </span>
                                                        </div>
                                                    )}

                                                    {item.info_url && (
                                                        <a
                                                            href={item.info_url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="text-muted-foreground/40 hover:text-foreground transition-colors"
                                                        >
                                                            <ExternalLink className="h-4 w-4" />
                                                        </a>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        </motion.div>
                                    ))
                                )}
                            </TabsContent>
                        </Tabs>
                    </motion.div>
                )}

                {/* Initial state */}
                {!submitted && (
                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                        <EmptyState
                            icon={Search}
                            title="Recherche unifiée"
                            description="Tapez au moins 2 caractères pour rechercher dans votre médiathèque et vos indexeurs"
                        />
                    </div>
                )}
            </motion.div>
        </>
    );
}
