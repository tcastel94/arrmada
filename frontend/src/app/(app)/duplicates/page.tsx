"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Copy,
    HardDrive,
    ArrowUpCircle,
    ScanSearch,
} from "lucide-react";
import { useDuplicates } from "@/hooks/use-duplicates";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

const STAT_CARDS = [
    {
        key: "dups",
        icon: Copy,
        gradient: "from-red-500/20 to-red-500/5",
        iconColor: "text-red-400",
        iconBg: "bg-red-500/20",
        ring: "ring-red-500/20",
        label: "Doublons détectés",
    },
    {
        key: "upgrades",
        icon: ArrowUpCircle,
        gradient: "from-amber-500/20 to-amber-500/5",
        iconColor: "text-amber-400",
        iconBg: "bg-amber-500/20",
        ring: "ring-amber-500/20",
        label: "Upgrades possibles",
    },
    {
        key: "space",
        icon: HardDrive,
        gradient: "from-orange-500/20 to-orange-500/5",
        iconColor: "text-orange-400",
        iconBg: "bg-orange-500/20",
        ring: "ring-orange-500/20",
        label: "Espace récupérable",
    },
];

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

    const statValues = [
        data.stats.total_duplicates,
        data.stats.total_upgrades,
        data.stats.wasted_space_human,
    ];

    return (
        <>
            <Header title="Doublons" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-red-600/20 via-orange-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center gap-4">
                            <div className="rounded-xl bg-red-500/20 p-3">
                                <ScanSearch className="h-6 w-6 text-red-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold tracking-tight">
                                    Détection des doublons
                                </h2>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    Analyse croisée de vos services pour détecter les doublons et upgrades
                                </p>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-red-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Stats */}
                <div className="grid gap-3 sm:grid-cols-3">
                    {STAT_CARDS.map((cfg, idx) => {
                        const Icon = cfg.icon;
                        return (
                            <motion.div key={cfg.key} variants={fadeUp}>
                                <Card
                                    className={cn(
                                        "border-0 bg-gradient-to-br ring-1 overflow-hidden relative",
                                        cfg.gradient,
                                        cfg.ring
                                    )}
                                >
                                    <CardContent className="p-5 flex items-center gap-3">
                                        <div className={cn("rounded-xl p-2.5", cfg.iconBg)}>
                                            <Icon className={cn("h-5 w-5", cfg.iconColor)} />
                                        </div>
                                        <div>
                                            <p className="text-2xl font-bold tabular-nums">
                                                {statValues[idx]}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {cfg.label}
                                            </p>
                                        </div>
                                    </CardContent>
                                    <div
                                        className={cn(
                                            "absolute -top-10 -right-10 w-28 h-28 rounded-full blur-2xl opacity-20",
                                            cfg.iconBg
                                        )}
                                    />
                                </Card>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Tabs */}
                <motion.div variants={fadeUp}>
                    <Tabs defaultValue="duplicates">
                        <TabsList className="bg-muted/30">
                            <TabsTrigger value="duplicates">
                                <Copy className="h-3 w-3 mr-1.5" />
                                Doublons ({data.stats.total_duplicates})
                            </TabsTrigger>
                            <TabsTrigger value="upgrades">
                                <ArrowUpCircle className="h-3 w-3 mr-1.5" />
                                Upgrades ({data.stats.total_upgrades})
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="duplicates" className="space-y-2 mt-4">
                            {data.duplicates.length === 0 ? (
                                <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                                    <EmptyState
                                        icon={Copy}
                                        title="Aucun doublon"
                                        description="Votre bibliothèque est propre !"
                                    />
                                </div>
                            ) : (
                                data.duplicates.map((dup, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.03 }}
                                    >
                                        <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm hover:ring-white/10 transition-all">
                                            <CardContent className="p-4">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            <h3 className="font-semibold truncate">
                                                                {dup.title}
                                                            </h3>
                                                            {dup.year && (
                                                                <span className="text-sm text-muted-foreground/60">
                                                                    ({dup.year})
                                                                </span>
                                                            )}
                                                            <Badge
                                                                variant="outline"
                                                                className="text-[10px] h-4 px-1.5 border-white/10 capitalize"
                                                            >
                                                                {dup.type === "movie" ? "Film" : "Série"}
                                                            </Badge>
                                                        </div>
                                                        <div className="flex flex-wrap gap-1.5 mt-2">
                                                            {dup.items.map((item, j) => (
                                                                <Badge
                                                                    key={j}
                                                                    className="text-[10px] bg-muted/30 border-0"
                                                                >
                                                                    {item.source}: {item.quality} ({item.size_human})
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    </div>
                                                    <div className="text-right shrink-0">
                                                        <p className="font-bold tabular-nums">
                                                            {dup.total_size_human}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground/60">
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

                        <TabsContent value="upgrades" className="space-y-2 mt-4">
                            {data.upgrade_opportunities.length === 0 ? (
                                <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                                    <EmptyState
                                        icon={ArrowUpCircle}
                                        title="Pas d'upgrade"
                                        description="Tous vos médias sont dans la meilleure qualité"
                                    />
                                </div>
                            ) : (
                                data.upgrade_opportunities.map((up, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.03 }}
                                    >
                                        <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm hover:ring-white/10 transition-all">
                                            <CardContent className="p-4">
                                                <div className="flex items-center justify-between gap-4">
                                                    <div className="min-w-0">
                                                        <h3 className="font-semibold truncate">
                                                            {up.title}
                                                            {up.year && (
                                                                <span className="text-sm text-muted-foreground/60 ml-2">
                                                                    ({up.year})
                                                                </span>
                                                            )}
                                                        </h3>
                                                        <p className="text-xs text-muted-foreground/60 mt-0.5">
                                                            {up.service}
                                                        </p>
                                                    </div>
                                                    <div className="flex gap-1.5 shrink-0">
                                                        {up.qualities.map((q, j) => (
                                                            <Badge
                                                                key={j}
                                                                variant="outline"
                                                                className="text-[10px] border-white/10"
                                                            >
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
                </motion.div>
            </motion.div>
        </>
    );
}
