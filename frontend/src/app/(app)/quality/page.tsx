"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Gauge,
    ArrowUpCircle,
    Film,
    Tv,
    HardDrive,
    TrendingUp,
} from "lucide-react";
import { useQualityOverview } from "@/hooks/use-new-features";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const RESOLUTION_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
    "2160p": { bg: "bg-violet-500/20", text: "text-violet-400", bar: "from-violet-500 to-purple-400" },
    "1080p": { bg: "bg-blue-500/20", text: "text-blue-400", bar: "from-blue-500 to-cyan-400" },
    "720p": { bg: "bg-amber-500/20", text: "text-amber-400", bar: "from-amber-500 to-yellow-400" },
    "SD": { bg: "bg-red-500/20", text: "text-red-400", bar: "from-red-500 to-red-400" },
    "Other": { bg: "bg-gray-500/20", text: "text-gray-400", bar: "from-gray-500 to-gray-400" },
};

const QUALITY_TIER_LABELS: Record<number, string> = {
    1: "SD", 2: "DVD", 3: "720p Web", 4: "720p Bluray",
    5: "1080p Web", 6: "1080p Bluray", 7: "1080p Remux",
    8: "2160p Web", 9: "2160p Bluray", 10: "2160p Remux",
};

export default function QualityPage() {
    const { data, isLoading } = useQualityOverview();

    if (isLoading) {
        return (
            <>
                <Header title="Qualité" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    const movies = data?.movies;
    const upgradeable = data?.upgradeable;
    const resolutionDist = movies?.resolution_distribution ?? {};

    return (
        <>
            <Header title="Qualité & Upgrades" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-violet-600/20 via-blue-600/10 to-transparent p-6 ring-1 ring-violet-500/20">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="rounded-xl p-2.5 bg-violet-500/20">
                                    <Gauge className="h-6 w-6 text-violet-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold">Qualité Tracker</h2>
                                    <p className="text-sm text-muted-foreground">
                                        Distribution qualité et opportunités d&apos;upgrade
                                    </p>
                                </div>
                            </div>
                            {upgradeable && upgradeable.count > 0 && (
                                <div className="text-right">
                                    <p className="text-2xl font-bold text-amber-400 tabular-nums">{upgradeable.count}</p>
                                    <p className="text-xs text-muted-foreground">upgrades possibles</p>
                                </div>
                            )}
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-violet-500/30" />
                    </div>
                </motion.div>

                {/* Resolution Distribution */}
                <motion.div variants={fadeUp}>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {Object.entries(resolutionDist).map(([res, info]) => {
                            const colors = RESOLUTION_COLORS[res] ?? RESOLUTION_COLORS.Other;
                            return (
                                <Card key={res} className={cn("border-0 ring-1 ring-white/5 bg-gradient-to-br to-transparent", colors.bg.replace("/20", "/10"))}>
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <Badge className={cn("border-0 text-xs", colors.bg, colors.text)}>
                                                {res}
                                            </Badge>
                                            <span className={cn("text-2xl font-bold tabular-nums", colors.text)}>
                                                {info.percent}%
                                            </span>
                                        </div>
                                        <div className="relative">
                                            <Progress value={info.percent} className="h-2 bg-muted/30" />
                                            <div
                                                className={cn("absolute inset-0 h-2 rounded-full bg-gradient-to-r opacity-80", colors.bar)}
                                                style={{ width: `${info.percent}%` }}
                                            />
                                        </div>
                                        <p className="text-[10px] text-muted-foreground mt-1 tabular-nums">
                                            {info.count} film{info.count > 1 ? "s" : ""}
                                        </p>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </motion.div>

                {/* Detailed Quality Distribution */}
                {movies && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                    <TrendingUp className="h-4 w-4 text-violet-400" />
                                    <span className="text-sm font-semibold">Distribution détaillée ({movies.total} films)</span>
                                </div>
                                <div className="p-4 space-y-2">
                                    {Object.entries(movies.quality_distribution).map(([quality, info]) => (
                                        <div key={quality} className="flex items-center gap-3">
                                            <span className="text-xs font-mono w-32 truncate text-muted-foreground">{quality}</span>
                                            <div className="flex-1 relative">
                                                <Progress value={info.percent} className="h-1.5 bg-muted/30" />
                                                <div
                                                    className="absolute inset-0 h-1.5 rounded-full bg-gradient-to-r from-violet-500 to-blue-400 opacity-80"
                                                    style={{ width: `${info.percent}%` }}
                                                />
                                            </div>
                                            <span className="text-xs tabular-nums text-muted-foreground w-16 text-right">
                                                {info.count} ({info.percent}%)
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}

                {/* Upgrade Opportunities */}
                {upgradeable && upgradeable.count > 0 && (
                    <motion.div variants={fadeUp}>
                        <Card className="border-0 ring-1 ring-amber-500/20 bg-card/40 backdrop-blur-sm">
                            <CardContent className="p-0">
                                <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                    <div className="flex items-center gap-2">
                                        <ArrowUpCircle className="h-4 w-4 text-amber-400" />
                                        <span className="text-sm font-semibold">Upgrades disponibles</span>
                                    </div>
                                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                        <span>Espace actuel: {upgradeable.total_current_size}</span>
                                        <span>Espace estimé: +{upgradeable.estimated_space_needed}</span>
                                    </div>
                                </div>
                                <div className="divide-y divide-white/5">
                                    {upgradeable.items.slice(0, 20).map((item, idx) => (
                                        <div key={idx} className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors">
                                            <div className="rounded-lg p-1.5 bg-amber-500/10">
                                                {item.type === "movie" ? (
                                                    <Film className="h-4 w-4 text-amber-400" />
                                                ) : (
                                                    <Tv className="h-4 w-4 text-amber-400" />
                                                )}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{item.title}</p>
                                                <p className="text-[10px] text-muted-foreground">
                                                    {item.year} · {item.profile} · {item.service}
                                                </p>
                                            </div>
                                            <Badge className="bg-red-500/20 text-red-400 border-0 text-[10px]">
                                                {item.quality}
                                            </Badge>
                                            <span className="text-xs text-muted-foreground tabular-nums">
                                                {item.size_human}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}
            </motion.div>
        </>
    );
}
