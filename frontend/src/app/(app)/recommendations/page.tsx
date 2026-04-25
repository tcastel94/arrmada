"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Sparkles,
    Film,
    Tv,
    TrendingUp,
    Star,
    Check,
    Library,
    ChevronRight,
} from "lucide-react";
import { useRecommendations, TMDBItem } from "@/hooks/use-new-features";
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

function TMDBCard({ item }: { item: TMDBItem }) {
    return (
        <div className="group relative overflow-hidden rounded-lg ring-1 ring-white/10 hover:ring-white/20 transition-all hover:scale-[1.02] duration-300">
            <div className="aspect-[2/3] relative">
                {item.poster_url ? (
                    <img
                        src={item.poster_url}
                        alt={item.title}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full bg-muted/20 flex items-center justify-center">
                        <Film className="h-8 w-8 text-muted-foreground/30" />
                    </div>
                )}
                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

                {/* In library badge */}
                {item.in_library && (
                    <div className="absolute top-2 right-2">
                        <Badge className="bg-emerald-500/90 text-white border-0 text-[10px] shadow-lg">
                            <Check className="h-3 w-3 mr-0.5" /> Dans la lib
                        </Badge>
                    </div>
                )}

                {/* Rating */}
                {item.rating != null && item.rating > 0 && (
                    <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/60 rounded-full px-1.5 py-0.5 backdrop-blur-sm">
                        <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                        <span className="text-[10px] font-bold text-yellow-100 tabular-nums">
                            {item.rating.toFixed(1)}
                        </span>
                    </div>
                )}

                {/* Bottom info */}
                <div className="absolute bottom-0 inset-x-0 p-3">
                    <p className="text-sm font-semibold text-white truncate leading-tight">
                        {item.title}
                    </p>
                    <div className="flex items-center gap-1 mt-0.5">
                        {item.year && (
                            <span className="text-[10px] text-white/60">{item.year}</span>
                        )}
                        <Badge variant="outline" className="text-[8px] px-1 h-3.5 border-white/20 text-white/60">
                            {item.type === "movie" ? "Film" : "Série"}
                        </Badge>
                    </div>
                </div>
            </div>
        </div>
    );
}

function TMDBRow({ items, title, icon: Icon, gradient }: {
    items: TMDBItem[];
    title: string;
    icon: typeof Film;
    gradient: string;
}) {
    if (!items || items.length === 0) return null;
    return (
        <motion.div variants={fadeUp}>
            <div className="flex items-center gap-2 mb-3">
                <Icon className={cn("h-4 w-4", gradient)} />
                <span className="text-sm font-semibold">{title}</span>
                <Badge variant="outline" className="text-[10px] ml-auto">{items.length}</Badge>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                {items.map((item) => (
                    <TMDBCard key={item.tmdb_id} item={item} />
                ))}
            </div>
        </motion.div>
    );
}

export default function RecommendationsPage() {
    const { data, isLoading } = useRecommendations();

    if (isLoading) {
        return (
            <>
                <Header title="Découvrir" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    if (!data) return null;

    return (
        <>
            <Header title="Découvrir" />
            <motion.div
                className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-yellow-600/20 via-orange-600/10 to-transparent p-6 ring-1 ring-yellow-500/20">
                        <div className="flex items-center gap-3">
                            <div className="rounded-xl p-2.5 bg-yellow-500/20">
                                <Sparkles className="h-6 w-6 text-yellow-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold">Découvrir</h2>
                                <p className="text-sm text-muted-foreground">
                                    {data.tmdb_available
                                        ? "Recommandations personnalisées basées sur votre bibliothèque et TMDB"
                                        : "Configurez votre clé TMDB pour des recommandations personnalisées"}
                                </p>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-yellow-500/30" />
                    </div>
                </motion.div>

                {/* Trending Movies */}
                <TMDBRow
                    items={data.trending_movies}
                    title="Tendances Films"
                    icon={TrendingUp}
                    gradient="text-blue-400"
                />

                {/* Trending Series */}
                <TMDBRow
                    items={data.trending_series}
                    title="Tendances Séries"
                    icon={TrendingUp}
                    gradient="text-cyan-400"
                />

                {/* Because You Have... */}
                {data.because_you_have?.map((group, idx) => (
                    <motion.div key={idx} variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-3 px-5 py-3 border-b border-white/5">
                                    <Library className="h-4 w-4 text-purple-400" />
                                    <span className="text-sm font-semibold">
                                        Parce que vous avez <span className="text-purple-400">{group.base_title}</span>
                                    </span>
                                    <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto" />
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4">
                                    {group.recommendations.map((rec) => (
                                        <TMDBCard key={rec.tmdb_id} item={rec} />
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                ))}

                {/* Wanted */}
                {data.wanted && data.wanted.length > 0 && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-amber-500/20 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                    <Film className="h-4 w-4 text-amber-400" />
                                    <span className="text-sm font-semibold">En attente de téléchargement</span>
                                    <Badge className="bg-amber-500/20 text-amber-400 border-0 text-[10px] ml-auto">
                                        {data.wanted.length}
                                    </Badge>
                                </div>
                                <div className="divide-y divide-white/5">
                                    {data.wanted.slice(0, 10).map((item: any, idx: number) => (
                                        <div key={idx} className="flex items-center gap-3 px-5 py-2.5 hover:bg-white/[0.02]">
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
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}

                {/* No TMDB key warning */}
                {!data.tmdb_available && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-amber-500/20 bg-amber-500/5">
                            <CardContent className="p-6 text-center">
                                <Sparkles className="h-8 w-8 text-amber-400 mx-auto mb-2" />
                                <h3 className="font-semibold mb-1">Clé TMDB non configurée</h3>
                                <p className="text-sm text-muted-foreground">
                                    Ajoutez <code className="bg-white/10 px-1 rounded">TMDB_API_KEY</code> dans votre .env pour obtenir
                                    des tendances et des recommandations personnalisées.
                                </p>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}
            </motion.div>
        </>
    );
}
