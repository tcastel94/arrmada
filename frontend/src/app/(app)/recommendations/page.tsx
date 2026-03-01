"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Sparkles,
    Film,
    Tv,
    Clock,
    TrendingUp,
    AlertTriangle,
} from "lucide-react";
import { useRecommendations } from "@/hooks/use-recommendations";
import { motion } from "framer-motion";

function MediaRow({ item }: { item: any }) {
    return (
        <div className="flex items-center gap-3 py-2.5 px-3 rounded-md hover:bg-muted/50 transition-colors">
            <div className="w-10 h-14 rounded-md overflow-hidden bg-muted shrink-0">
                {item.poster_url ? (
                    <img
                        src={item.poster_url}
                        alt=""
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center">
                        {item.type === "movie" ? (
                            <Film className="h-4 w-4 text-muted-foreground/30" />
                        ) : (
                            <Tv className="h-4 w-4 text-muted-foreground/30" />
                        )}
                    </div>
                )}
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.title}</p>
                <div className="flex items-center gap-2 mt-0.5">
                    {item.year && (
                        <span className="text-xs text-muted-foreground">{item.year}</span>
                    )}
                    <Badge variant="outline" className="text-[10px]">
                        {item.type === "movie" ? "Film" : "Série"}
                    </Badge>
                </div>
            </div>
            {item.genres && item.genres.length > 0 && (
                <div className="flex gap-1 shrink-0 hidden lg:flex">
                    {item.genres.slice(0, 2).map((g: string) => (
                        <Badge key={g} variant="secondary" className="text-[10px]">
                            {g}
                        </Badge>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function RecommendationsPage() {
    const { data, isLoading } = useRecommendations();

    if (isLoading) {
        return (
            <>
                <Header title="Recommandations" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    if (!data) return null;

    return (
        <>
            <Header title="Recommandations" />
            <div className="p-6 space-y-6">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                        <Sparkles className="h-6 w-6 text-yellow-500" />
                        Recommandations
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Basées sur l&apos;analyse de votre médiathèque
                    </p>
                </div>

                {/* Top Genres */}
                <div className="flex flex-wrap gap-2">
                    <span className="text-sm text-muted-foreground mr-1">
                        Vos genres préférés :
                    </span>
                    {data.top_genres.map((g) => (
                        <Badge key={g} className="text-sm">
                            {g}
                        </Badge>
                    ))}
                </div>

                <div className="grid gap-6 lg:grid-cols-2">
                    {/* Wanted / Missing */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4 text-orange-500" />
                                    Recherche en cours
                                    <Badge variant="outline" className="ml-auto text-xs">
                                        {data.stats.total_wanted} manquants
                                    </Badge>
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {data.wanted.length === 0 ? (
                                    <EmptyState
                                        icon={Sparkles}
                                        title="Tout est téléchargé"
                                        description="Aucun média en attente de téléchargement"
                                    />
                                ) : (
                                    <div className="space-y-1 max-h-[420px] overflow-y-auto">
                                        {data.wanted.map((item, i) => (
                                            <motion.div
                                                key={`${item.title}-${i}`}
                                                initial={{ opacity: 0, x: -5 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: i * 0.02 }}
                                            >
                                                <MediaRow item={item} />
                                            </motion.div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Recently Added */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                    >
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Clock className="h-4 w-4 text-blue-400" />
                                    Récemment ajoutés
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {data.recently_added.length === 0 ? (
                                    <EmptyState
                                        icon={Clock}
                                        title="Pas d'ajouts récents"
                                        description="Aucun média récemment ajouté"
                                    />
                                ) : (
                                    <div className="space-y-1">
                                        {data.recently_added.map((item, i) => (
                                            <motion.div
                                                key={`${item.title}-${i}`}
                                                initial={{ opacity: 0, x: -5 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: i * 0.02 }}
                                            >
                                                <MediaRow item={item} />
                                            </motion.div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>
                </div>
            </div>
        </>
    );
}
