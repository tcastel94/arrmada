"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Trash2,
    Film,
    Tv,
    AlertTriangle,
    Eye,
    EyeOff,
    HardDrive,
    ArrowDown,
    Maximize,
    DiscAlbum,
} from "lucide-react";
import { useCleanupScan, CleanupItem } from "@/hooks/use-new-features";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const TABS = [
    { key: "unmonitored", label: "Non surveillés", icon: EyeOff, color: "text-amber-400" },
    { key: "low_quality", label: "Basse qualité", icon: ArrowDown, color: "text-red-400" },
    { key: "oversized", label: "Surdimensionnés", icon: Maximize, color: "text-purple-400" },
    { key: "incomplete_ended", label: "Séries incomplètes", icon: DiscAlbum, color: "text-blue-400" },
] as const;

type TabKey = typeof TABS[number]["key"];

function CleanupItemRow({ item }: { item: CleanupItem }) {
    return (
        <div className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors">
            {item.poster_url ? (
                <img src={item.poster_url} alt={item.title} className="h-14 w-10 rounded object-cover ring-1 ring-white/10" />
            ) : (
                <div className="h-14 w-10 rounded bg-muted/20 flex items-center justify-center">
                    {item.type === "movie" ? <Film className="h-4 w-4 text-muted-foreground" /> : <Tv className="h-4 w-4 text-muted-foreground" />}
                </div>
            )}
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.suggestion}</p>
                <div className="flex items-center gap-2 mt-0.5">
                    {item.quality && (
                        <Badge variant="outline" className="text-[9px] px-1 h-4">{item.quality}</Badge>
                    )}
                    <span className="text-[10px] text-muted-foreground">{item.service}</span>
                </div>
            </div>
            <div className="text-right">
                <p className="text-sm font-bold tabular-nums text-amber-400">{item.size_human}</p>
                <p className="text-[10px] text-muted-foreground">{item.year ?? ""}</p>
            </div>
        </div>
    );
}

export default function CleanupPage() {
    const { data, isLoading } = useCleanupScan();
    const [activeTab, setActiveTab] = useState<TabKey>("unmonitored");

    if (isLoading) {
        return (
            <>
                <Header title="Nettoyage" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    const summary = data?.summary;
    const tabData = {
        unmonitored: data?.unmonitored,
        low_quality: data?.low_quality,
        oversized: data?.oversized,
        incomplete_ended: data?.incomplete_ended,
    };

    const currentItems = (tabData[activeTab] as any)?.items ?? [];
    const currentTotal = (tabData[activeTab] as any)?.total ?? 0;

    return (
        <>
            <Header title="Smart Cleanup" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-red-600/20 via-orange-600/10 to-transparent p-6 ring-1 ring-red-500/20">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="rounded-xl p-2.5 bg-red-500/20">
                                    <Trash2 className="h-6 w-6 text-red-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold">Smart Cleanup</h2>
                                    <p className="text-sm text-muted-foreground">
                                        Identifiez et récupérez de l&apos;espace disque
                                    </p>
                                </div>
                            </div>
                            {summary && (
                                <div className="text-right">
                                    <p className="text-2xl font-bold text-emerald-400 tabular-nums">{summary.total_reclaimable_human}</p>
                                    <p className="text-xs text-muted-foreground">récupérables</p>
                                    <p className="text-xs text-muted-foreground tabular-nums">{summary.total_issues} problèmes détectés</p>
                                </div>
                            )}
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-red-500/30" />
                    </div>
                </motion.div>

                {/* Tab Selector */}
                <motion.div variants={fadeUp}>
                    <div className="flex gap-2 overflow-x-auto pb-1">
                        {TABS.map((tab) => {
                            const Icon = tab.icon;
                            const count = (tabData[tab.key] as any)?.total ?? 0;
                            return (
                                <button
                                    key={tab.key}
                                    onClick={() => setActiveTab(tab.key)}
                                    className={cn(
                                        "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
                                        activeTab === tab.key
                                            ? "bg-white/10 ring-1 ring-white/20"
                                            : "bg-white/[0.02] hover:bg-white/[0.05]",
                                    )}
                                >
                                    <Icon className={cn("h-4 w-4", tab.color)} />
                                    {tab.label}
                                    {count > 0 && (
                                        <Badge className="bg-white/10 text-foreground border-0 text-[10px]">{count}</Badge>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </motion.div>

                {/* Items List */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                        <CardContent className="p-0">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4 text-amber-400" />
                                    <span className="text-sm font-semibold">
                                        {currentTotal} élément{currentTotal > 1 ? "s" : ""}
                                    </span>
                                </div>
                                {activeTab === "unmonitored" && data?.unmonitored && (
                                    <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-xs">
                                        <HardDrive className="h-3 w-3 mr-1" />
                                        {data.unmonitored.reclaimable_human} récupérables
                                    </Badge>
                                )}
                            </div>
                            <div className="divide-y divide-white/5">
                                {currentItems.map((item: CleanupItem, idx: number) => (
                                    <CleanupItemRow key={idx} item={item} />
                                ))}
                                {currentItems.length === 0 && (
                                    <div className="text-center py-12 text-muted-foreground">
                                        <Trash2 className="h-8 w-8 mx-auto mb-2 opacity-20" />
                                        <p className="text-sm">Aucun élément dans cette catégorie</p>
                                        <p className="text-xs">Votre bibliothèque est propre ! 🎉</p>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </motion.div>
        </>
    );
}
