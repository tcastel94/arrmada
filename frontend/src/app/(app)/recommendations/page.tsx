"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Sparkles,
    Film,
    Tv,
    TrendingUp,
    Star,
    Check,
    Library,
    ChevronRight,
    Search,
    Info,
} from "lucide-react";
import {
    useRecommendations,
    useRecommendationsBasedOn,
    TMDBItem,
} from "@/hooks/use-new-features";
import { RecommendationDetailModal } from "@/components/media/recommendation-detail-modal";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

function TMDBCard({
    item,
    onClick,
}: {
    item: TMDBItem;
    onClick: () => void;
}) {
    return (
        <div
            onClick={onClick}
            className="group relative overflow-hidden rounded-xl ring-1 ring-white/10 hover:ring-primary/50 transition-all hover:scale-[1.03] duration-300 cursor-pointer shadow-lg hover:shadow-primary/10"
        >
            <div className="aspect-[2/3] relative">
                {item.poster_url ? (
                    <img
                        src={item.poster_url}
                        alt={item.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                ) : (
                    <div className="w-full h-full bg-muted/20 flex items-center justify-center">
                        <Film className="h-8 w-8 text-muted-foreground/30" />
                    </div>
                )}
                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent opacity-80 group-hover:opacity-90 transition-opacity" />

                {/* In library badge */}
                {item.in_library && (
                    <div className="absolute top-2 right-2 z-10">
                        <Badge className="bg-emerald-500/90 text-white border-0 text-[10px] shadow-lg backdrop-blur-md">
                            <Check className="h-3 w-3 mr-0.5" /> En possession
                        </Badge>
                    </div>
                )}

                {/* Rating */}
                {item.rating != null && item.rating > 0 && (
                    <div className="absolute top-2 left-2 z-10 flex items-center gap-1 bg-black/70 rounded-full px-2 py-0.5 backdrop-blur-md border border-white/10">
                        <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                        <span className="text-[10px] font-bold text-yellow-100 tabular-nums">
                            {item.rating.toFixed(1)}
                        </span>
                    </div>
                )}

                {/* Hover overlay hint */}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40 backdrop-blur-[2px]">
                    <span className="bg-white/20 hover:bg-white/30 text-white text-xs px-3 py-1.5 rounded-full font-semibold flex items-center gap-1.5 shadow-2xl backdrop-blur-md border border-white/30">
                        <Info className="h-3.5 w-3.5" /> Détails
                    </span>
                </div>

                {/* Bottom info */}
                <div className="absolute bottom-0 inset-x-0 p-3 z-10">
                    <p className="text-sm font-semibold text-white truncate leading-tight group-hover:text-primary transition-colors">
                        {item.title}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1">
                        {item.year && (
                            <span className="text-[10px] text-white/70 font-medium">{item.year}</span>
                        )}
                        <Badge variant="outline" className="text-[8px] px-1.5 h-4 border-white/20 text-white/70">
                            {item.type === "movie" ? "Film" : "Série"}
                        </Badge>
                    </div>
                </div>
            </div>
        </div>
    );
}

function TMDBRow({
    items,
    title,
    icon: Icon,
    gradient,
    onSelect,
}: {
    items: TMDBItem[];
    title: string;
    icon: typeof Film;
    gradient: string;
    onSelect: (item: TMDBItem) => void;
}) {
    if (!items || items.length === 0) return null;
    return (
        <motion.div variants={fadeUp}>
            <div className="flex items-center gap-2 mb-3">
                <Icon className={cn("h-4 w-4", gradient)} />
                <span className="text-sm font-semibold">{title}</span>
                <Badge variant="outline" className="text-[10px] ml-auto">{items.length}</Badge>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 sm:gap-4">
                {items.map((item) => (
                    <TMDBCard
                        key={item.tmdb_id}
                        item={item}
                        onClick={() => onSelect(item)}
                    />
                ))}
            </div>
        </motion.div>
    );
}

export default function RecommendationsPage() {
    const { data, isLoading } = useRecommendations();
    const [selectedModalItem, setSelectedModalItem] = useState<{ tmdb_id: number; type: string } | null>(null);
    const [selectedLibraryItem, setSelectedLibraryItem] = useState<{ tmdb_id: number; type: string; title: string } | null>(null);

    const { data: targetedRecs, isLoading: isTargetedLoading } = useRecommendationsBasedOn(
        selectedLibraryItem?.type,
        selectedLibraryItem?.tmdb_id
    );

    if (isLoading) {
        return (
            <>
                <Header title="Découvrir & Suggestions" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    if (!data) return null;

    return (
        <>
            <Header title="Découvrir & Suggestions" />
            <motion.div
                className="p-4 md:p-6 space-y-8 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-900/30 via-indigo-900/20 to-zinc-950 p-6 sm:p-8 ring-1 ring-purple-500/20 shadow-2xl">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="flex items-center gap-4">
                                <div className="rounded-2xl p-3 bg-purple-500/20 ring-1 ring-purple-500/30">
                                    <Sparkles className="h-7 w-7 text-purple-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                                        Recommandations Médias
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Suggestions personnalisées basées sur vos films et séries en médiathèque. Cliquez sur une affiche pour plus de détails et bande-annonce.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Dynamic Library Item Selector */}
                {data.library_select_items && data.library_select_items.length > 0 && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-white/10 bg-card/60 backdrop-blur-md">
                            <CardContent className="p-5 space-y-4">
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                    <div className="flex items-center gap-2">
                                        <Library className="h-4 w-4 text-purple-400" />
                                        <span className="text-sm font-semibold">
                                            Explorer des suggestions à partir d'un élément de votre médiathèque
                                        </span>
                                    </div>
                                    <Select
                                        onValueChange={(val) => {
                                            const item = data.library_select_items.find((i) => String(i.id) === val);
                                            if (item && item.tmdb_id) {
                                                setSelectedLibraryItem({
                                                    tmdb_id: item.tmdb_id,
                                                    type: item.type,
                                                    title: item.title,
                                                });
                                            }
                                        }}
                                    >
                                        <SelectTrigger className="w-full sm:w-[320px] bg-zinc-900/80 border-zinc-800 text-sm">
                                            <SelectValue placeholder="Sélectionnez un film ou une série..." />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-72 bg-zinc-900 border-zinc-800 text-white">
                                            {data.library_select_items.map((item) => (
                                                <SelectItem key={item.id} value={String(item.id)}>
                                                    <span className="flex items-center gap-2">
                                                        <span>{item.title}</span>
                                                        <span className="text-[10px] text-muted-foreground">({item.year || item.type})</span>
                                                    </span>
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* Display targeted results if selected */}
                                {selectedLibraryItem && (
                                    <div className="pt-3 border-t border-white/5 space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Sparkles className="h-4 w-4 text-amber-400" />
                                            <span className="text-xs font-semibold text-zinc-300">
                                                Recommandations basées sur <span className="text-purple-400 font-bold">{selectedLibraryItem.title}</span>
                                            </span>
                                        </div>
                                        {isTargetedLoading ? (
                                            <div className="p-4 text-center text-xs text-muted-foreground">Recherche des recommandations...</div>
                                        ) : targetedRecs?.items && targetedRecs.items.length > 0 ? (
                                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                                                {targetedRecs.items.map((item) => (
                                                    <TMDBCard
                                                        key={item.tmdb_id}
                                                        item={item}
                                                        onClick={() => setSelectedModalItem({ tmdb_id: item.tmdb_id, type: item.type })}
                                                    />
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-xs text-muted-foreground italic">Aucune recommandation TMDB spécifique trouvée pour ce titre.</p>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>
                )}

                {/* Because You Have... Groups (Library based) */}
                {data.because_you_have && data.because_you_have.length > 0 && (
                    <div className="space-y-6">
                        {data.because_you_have.map((group, idx) => (
                            <motion.div key={idx} variants={fadeUp}>
                                <Card className="border-0 ring-1 ring-purple-500/20 bg-card/40 backdrop-blur-sm overflow-hidden">
                                    <CardContent className="p-0">
                                        <div className="flex items-center gap-3 px-5 py-3.5 border-b border-white/5 bg-purple-500/5">
                                            <Library className="h-4 w-4 text-purple-400" />
                                            <span className="text-sm font-semibold">
                                                Parce que vous avez <span className="text-purple-300 font-bold">{group.base_title}</span>
                                            </span>
                                            <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto" />
                                        </div>
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4">
                                            {group.recommendations.map((rec) => (
                                                <TMDBCard
                                                    key={rec.tmdb_id}
                                                    item={rec}
                                                    onClick={() => setSelectedModalItem({ tmdb_id: rec.tmdb_id, type: rec.type })}
                                                />
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </div>
                )}

                {/* Trending Movies */}
                <TMDBRow
                    items={data.trending_movies}
                    title="Tendances Films"
                    icon={TrendingUp}
                    gradient="text-blue-400"
                    onSelect={(item) => setSelectedModalItem({ tmdb_id: item.tmdb_id, type: item.type })}
                />

                {/* Trending Series */}
                <TMDBRow
                    items={data.trending_series}
                    title="Tendances Séries"
                    icon={TrendingUp}
                    gradient="text-cyan-400"
                    onSelect={(item) => setSelectedModalItem({ tmdb_id: item.tmdb_id, type: item.type })}
                />

                {/* Wanted / Missing */}
                {data.wanted && data.wanted.length > 0 && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-amber-500/20 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-2 px-5 py-3.5 border-b border-white/5">
                                    <Film className="h-4 w-4 text-amber-400" />
                                    <span className="text-sm font-semibold">En attente de téléchargement dans votre médiathèque</span>
                                    <Badge className="bg-amber-500/20 text-amber-400 border-0 text-[10px] ml-auto">
                                        {data.wanted.length}
                                    </Badge>
                                </div>
                                <div className="divide-y divide-white/5">
                                    {data.wanted.slice(0, 10).map((item: any, idx: number) => (
                                        <div
                                            key={idx}
                                            onClick={() => {
                                                if (item.tmdb_id) {
                                                    setSelectedModalItem({ tmdb_id: item.tmdb_id, type: item.type });
                                                }
                                            }}
                                            className="flex items-center gap-3 px-5 py-2.5 hover:bg-white/[0.04] transition-colors cursor-pointer"
                                        >
                                            {item.poster_url ? (
                                                <img src={item.poster_url} alt="" className="h-10 w-7 rounded object-cover" />
                                            ) : (
                                                <div className="h-10 w-7 rounded bg-muted/20 flex items-center justify-center">
                                                    <Film className="h-3 w-3 text-muted-foreground" />
                                                </div>
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{item.title}</p>
                                                <p className="text-[10px] text-muted-foreground">{item.year} · {item.source_service}</p>
                                            </div>
                                            <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
                                                Manquant
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}
            </motion.div>

            {/* Modal for detail view on poster click */}
            <RecommendationDetailModal
                tmdbId={selectedModalItem?.tmdb_id || null}
                mediaType={selectedModalItem?.type || "movie"}
                isOpen={!!selectedModalItem}
                onClose={() => setSelectedModalItem(null)}
            />
        </>
    );
}
