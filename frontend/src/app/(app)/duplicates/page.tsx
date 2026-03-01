"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Copy, HardDrive, ArrowUpCircle, AlertTriangle } from "lucide-react";
import { useDuplicates } from "@/hooks/use-duplicates";
import { motion } from "framer-motion";

export default function DuplicatesPage() {
    const { data, isLoading } = useDuplicates();

    if (isLoading) {
        return (
            <>
                <Header title="Doublons" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    if (!data) return null;

    return (
        <>
            <Header title="Doublons" />
            <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">
                            Détection des doublons
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Analyse croisée de vos services pour détecter les doublons et
                            opportunités d&apos;upgrade
                        </p>
                    </div>
                </div>

                {/* Stats overview */}
                <div className="grid gap-4 sm:grid-cols-3">
                    <Card>
                        <CardContent className="p-4 flex items-center gap-3">
                            <div className="h-10 w-10 rounded-lg bg-red-500/10 flex items-center justify-center">
                                <Copy className="h-5 w-5 text-red-500" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {data.stats.total_duplicates}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Doublons détectés
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 flex items-center gap-3">
                            <div className="h-10 w-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                                <ArrowUpCircle className="h-5 w-5 text-yellow-500" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {data.stats.total_upgrades}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Upgrades possibles
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 flex items-center gap-3">
                            <div className="h-10 w-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                                <HardDrive className="h-5 w-5 text-orange-500" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold">
                                    {data.stats.wasted_space_human}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Espace récupérable
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <Tabs defaultValue="duplicates">
                    <TabsList>
                        <TabsTrigger value="duplicates">
                            Doublons ({data.stats.total_duplicates})
                        </TabsTrigger>
                        <TabsTrigger value="upgrades">
                            Upgrades ({data.stats.total_upgrades})
                        </TabsTrigger>
                    </TabsList>

                    {/* Duplicates Tab */}
                    <TabsContent value="duplicates" className="space-y-3 mt-4">
                        {data.duplicates.length === 0 ? (
                            <EmptyState
                                icon={Copy}
                                title="Aucun doublon"
                                description="Aucun doublon cross-service détecté — votre bibliothèque est propre !"
                            />
                        ) : (
                            data.duplicates.map((dup, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.03 }}
                                >
                                    <Card>
                                        <CardContent className="p-4">
                                            <div className="flex items-start justify-between gap-4">
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <h3 className="font-semibold truncate">
                                                            {dup.title}
                                                        </h3>
                                                        {dup.year && (
                                                            <span className="text-sm text-muted-foreground">
                                                                ({dup.year})
                                                            </span>
                                                        )}
                                                        <Badge variant="outline" className="text-xs capitalize">
                                                            {dup.type === "movie" ? "Film" : "Série"}
                                                        </Badge>
                                                    </div>
                                                    <div className="flex flex-wrap gap-2 mt-2">
                                                        {dup.items.map((item, j) => (
                                                            <Badge
                                                                key={j}
                                                                variant="secondary"
                                                                className="text-xs"
                                                            >
                                                                {item.source}: {item.quality} ({item.size_human})
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <p className="font-semibold">
                                                        {dup.total_size_human}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {dup.copies} copies
                                                    </p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            ))
                        )}
                    </TabsContent>

                    {/* Upgrades Tab */}
                    <TabsContent value="upgrades" className="space-y-3 mt-4">
                        {data.upgrade_opportunities.length === 0 ? (
                            <EmptyState
                                icon={ArrowUpCircle}
                                title="Pas d'upgrade disponible"
                                description="Tous vos médias sont déjà dans la meilleure qualité disponible"
                            />
                        ) : (
                            data.upgrade_opportunities.map((up, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.03 }}
                                >
                                    <Card>
                                        <CardContent className="p-4">
                                            <div className="flex items-center justify-between gap-4">
                                                <div className="min-w-0">
                                                    <h3 className="font-semibold truncate">
                                                        {up.title}
                                                        {up.year && (
                                                            <span className="text-sm text-muted-foreground ml-2">
                                                                ({up.year})
                                                            </span>
                                                        )}
                                                    </h3>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {up.service}
                                                    </p>
                                                </div>
                                                <div className="flex gap-1.5 shrink-0">
                                                    {up.qualities.map((q, j) => (
                                                        <Badge key={j} variant="outline" className="text-xs">
                                                            {q}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            ))
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </>
    );
}
