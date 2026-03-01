"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    BarChart3,
    Film,
    Tv,
    HardDrive,
    Eye,
    EyeOff,
    AlertTriangle,
} from "lucide-react";
import { useAnalytics } from "@/hooks/use-analytics";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from "recharts";
import { motion } from "framer-motion";

const CHART_COLORS = [
    "hsl(217, 91%, 60%)",
    "hsl(142, 71%, 45%)",
    "hsl(47, 100%, 50%)",
    "hsl(0, 84%, 60%)",
    "hsl(270, 76%, 60%)",
    "hsl(190, 90%, 50%)",
    "hsl(30, 90%, 55%)",
    "hsl(330, 80%, 55%)",
    "hsl(160, 60%, 45%)",
    "hsl(200, 70%, 50%)",
];

function StatBox({
    label,
    value,
    icon: Icon,
    color,
}: {
    label: string;
    value: string | number;
    icon: any;
    color?: string;
}) {
    return (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
            <div
                className="h-10 w-10 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: color || "hsl(217, 91%, 60%, 0.15)" }}
            >
                <Icon className="h-5 w-5" style={{ color: color || "hsl(217, 91%, 60%)" }} />
            </div>
            <div>
                <p className="text-sm text-muted-foreground">{label}</p>
                <p className="text-lg font-semibold">{value}</p>
            </div>
        </div>
    );
}

export default function AnalyticsPage() {
    const { data, isLoading } = useAnalytics();

    if (isLoading) {
        return (
            <>
                <Header title="Analytics" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    if (!data) return null;
    const { overview, quality_distribution, genre_distribution, year_distribution, top_biggest, service_breakdown } = data;

    return (
        <>
            <Header title="Analytics" />
            <div className="p-6 space-y-6">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Statistiques</h2>
                    <p className="text-sm text-muted-foreground">
                        Vue d&apos;ensemble de votre médiathèque
                    </p>
                </div>

                {/* Overview Stats */}
                <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                    <StatBox label="Films" value={overview.movies} icon={Film} color="hsl(47, 100%, 50%)" />
                    <StatBox label="Séries" value={overview.series} icon={Tv} color="hsl(217, 91%, 60%)" />
                    <StatBox label="Stockage total" value={overview.total_size_human} icon={HardDrive} color="hsl(142, 71%, 45%)" />
                    <StatBox label="Manquants" value={overview.missing} icon={AlertTriangle} color="hsl(0, 84%, 60%)" />
                </div>

                <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                    <StatBox label="Taille films" value={overview.movie_size_human} icon={Film} />
                    <StatBox label="Taille séries" value={overview.series_size_human} icon={Tv} />
                    <StatBox label="Moy. film" value={overview.avg_movie_size_human} icon={Film} />
                    <StatBox label="Moy. série" value={overview.avg_series_size_human} icon={Tv} />
                </div>

                {/* Charts Row */}
                <div className="grid gap-6 lg:grid-cols-2">
                    {/* Quality Distribution */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Distribution qualité</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ResponsiveContainer width="100%" height={280}>
                                <BarChart data={quality_distribution.slice(0, 10)} layout="vertical">
                                    <XAxis type="number" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                                    <YAxis
                                        type="category"
                                        dataKey="name"
                                        width={120}
                                        tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: "hsl(var(--card))",
                                            border: "1px solid hsl(var(--border))",
                                            borderRadius: 8,
                                            color: "hsl(var(--foreground))",
                                        }}
                                    />
                                    <Bar dataKey="count" fill="hsl(217, 91%, 60%)" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    {/* Genre Distribution */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Genres les plus représentés</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ResponsiveContainer width="100%" height={280}>
                                <PieChart>
                                    <Pie
                                        data={genre_distribution.slice(0, 10)}
                                        cx="50%"
                                        cy="50%"
                                        outerRadius={100}
                                        innerRadius={55}
                                        dataKey="count"
                                        nameKey="name"
                                        label={({ name, percent }: any) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                                        labelLine={false}
                                    >
                                        {genre_distribution.slice(0, 10).map((_, i) => (
                                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{
                                            background: "hsl(var(--card))",
                                            border: "1px solid hsl(var(--border))",
                                            borderRadius: 8,
                                            color: "hsl(var(--foreground))",
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </div>

                {/* Year distribution */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">Distribution par année</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={year_distribution}>
                                <XAxis
                                    dataKey="year"
                                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                                <Tooltip
                                    contentStyle={{
                                        background: "hsl(var(--card))",
                                        border: "1px solid hsl(var(--border))",
                                        borderRadius: 8,
                                        color: "hsl(var(--foreground))",
                                    }}
                                />
                                <Bar dataKey="count" fill="hsl(142, 71%, 45%)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Bottom Row */}
                <div className="grid gap-6 lg:grid-cols-2">
                    {/* Top Biggest */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Top 10 — plus volumineux</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {top_biggest.map((item, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.03 }}
                                        className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-muted/50 transition-colors"
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <span className="text-xs text-muted-foreground font-mono w-5">
                                                {i + 1}.
                                            </span>
                                            {item.type === "movie" ? (
                                                <Film className="h-3.5 w-3.5 text-yellow-500 shrink-0" />
                                            ) : (
                                                <Tv className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                                            )}
                                            <span className="text-sm truncate">{item.title}</span>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            {item.quality && (
                                                <Badge variant="outline" className="text-[10px]">
                                                    {item.quality}
                                                </Badge>
                                            )}
                                            <span className="text-sm font-semibold tabular-nums">
                                                {item.size_human}
                                            </span>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Service Breakdown */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Répartition par service</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ResponsiveContainer width="100%" height={250}>
                                <PieChart>
                                    <Pie
                                        data={service_breakdown}
                                        cx="50%"
                                        cy="50%"
                                        outerRadius={90}
                                        innerRadius={50}
                                        dataKey="count"
                                        nameKey="name"
                                        label={({ name, value }: any) => `${name}: ${value}`}
                                        labelLine
                                    >
                                        {service_breakdown.map((_, i) => (
                                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{
                                            background: "hsl(var(--card))",
                                            border: "1px solid hsl(var(--border))",
                                            borderRadius: 8,
                                            color: "hsl(var(--foreground))",
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </>
    );
}
