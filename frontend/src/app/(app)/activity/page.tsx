"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Activity,
    Download,
    CheckCircle2,
    XCircle,
    Captions,
    Play,
    MonitorPlay,
    Search,
    Trash2,
    Plus,
    Send,
    Library,
    Film,
    Tv,
    Rows3,
    LayoutGrid,
    RefreshCw,
} from "lucide-react";
import { useActivityTimeline, type TimelineItem } from "@/hooks/use-activity";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

/* ── Visual maps ─────────────────────────────────────────────── */

const CATEGORIES = [
    { key: "download", label: "Téléchargements", icon: Download, color: "text-sky-400" },
    { key: "subtitle", label: "Sous-titres", icon: Captions, color: "text-blue-400" },
    { key: "playback", label: "Lectures", icon: Play, color: "text-violet-400" },
    { key: "library", label: "Bibliothèque", icon: Library, color: "text-amber-400" },
    { key: "telegram", label: "Telegram", icon: Send, color: "text-cyan-400" },
];

const ACTION_LABELS: Record<string, string> = {
    grabbed: "Téléchargement lancé",
    grab: "Grab lancé",
    imported: "Importé",
    downloadFolderImported: "Importé",
    downloadFailed: "Échec du téléchargement",
    failed: "Échec",
    sub_download: "Sous-titre téléchargé",
    sub_sync: "Sous-titre synchronisé",
    kodi_play: "Lecture",
    search: "Recherche lancée",
    delete: "Supprimé",
    add: "Ajouté",
    episodeFileDeleted: "Fichier supprimé",
    movieFileDeleted: "Fichier supprimé",
    movieDeleted: "Film supprimé",
    seriesDeleted: "Série supprimée",
    episodeFileRenamed: "Renommé",
    movieFileRenamed: "Renommé",
};

const SOURCE_LABELS: Record<string, string> = {
    arrmada: "Arrmada",
    kodi: "Kodi",
    radarr: "Radarr",
    sonarr: "Sonarr",
    bazarr: "Bazarr",
    telegram: "Telegram",
    external: "Externe",
};

function actionLabel(a: string) {
    return ACTION_LABELS[a] ?? a;
}

function IconFor({ item }: { item: TimelineItem }) {
    const cls = "h-4 w-4";
    if (item.status === "ko") return <XCircle className={cn(cls, "text-red-400")} />;
    switch (item.action) {
        case "imported":
        case "downloadFolderImported":
            return <CheckCircle2 className={cn(cls, "text-emerald-400")} />;
        case "grabbed":
        case "grab":
            return <Download className={cn(cls, "text-sky-400")} />;
        case "sub_download":
        case "sub_sync":
            return <Captions className={cn(cls, "text-blue-400")} />;
        case "kodi_play":
            return <MonitorPlay className={cn(cls, "text-violet-400")} />;
        case "search":
            return <Search className={cn(cls, "text-amber-400")} />;
        case "delete":
        case "movieDeleted":
        case "seriesDeleted":
        case "episodeFileDeleted":
        case "movieFileDeleted":
            return <Trash2 className={cn(cls, "text-red-400")} />;
        case "add":
            return item.source === "telegram" ? (
                <Send className={cn(cls, "text-cyan-400")} />
            ) : (
                <Plus className={cn(cls, "text-emerald-400")} />
            );
        default:
            return <Activity className={cn(cls, "text-muted-foreground")} />;
    }
}

function ago(ts: number): string {
    const s = Math.floor(Date.now() / 1000) - ts;
    if (s < 60) return "à l'instant";
    const m = Math.floor(s / 60);
    if (m < 60) return `il y a ${m} min`;
    const h = Math.floor(m / 60);
    if (h < 24) return `il y a ${h} h`;
    const d = Math.floor(h / 24);
    if (d < 7) return `il y a ${d} j`;
    return new Date(ts * 1000).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}

function statusDot(status: string) {
    return status === "ok"
        ? "bg-emerald-500"
        : status === "ko"
            ? "bg-red-500"
            : "bg-slate-500";
}

function Row({ item, compact = false }: { item: TimelineItem; compact?: boolean }) {
    const href =
        item.media_type && item.media_id
            ? `/media/${item.media_type}/${item.media_id}`
            : null;
    const body = (
        <div className="flex items-center gap-3">
            <div className="relative shrink-0">
                <span className={cn("absolute -left-1 top-1/2 -translate-y-1/2 h-1.5 w-1.5 rounded-full", statusDot(item.status))} />
                <div className="ml-1.5 rounded-lg bg-muted/30 p-2">
                    <IconFor item={item} />
                </div>
            </div>
            {!compact && item.poster_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={item.poster_url} alt="" className="h-10 w-7 rounded object-cover ring-1 ring-white/5 shrink-0" loading="lazy" />
            )}
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm">
                    <span className="font-medium">{actionLabel(item.action)}</span>
                    {item.title && <span className="text-muted-foreground"> · {item.title}</span>}
                </p>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground/70">
                    {item.subtitle && <span className="truncate">{item.subtitle}</span>}
                    {item.detail && <span className="truncate">· {item.detail}</span>}
                    {item.device && (
                        <span className="truncate">· {item.device}</span>
                    )}
                    <Badge variant="outline" className="border-white/10 px-1 py-0 text-[9px]">
                        {SOURCE_LABELS[item.source] ?? item.source}
                    </Badge>
                </div>
            </div>
            <span className="shrink-0 text-[11px] text-muted-foreground/60 tabular-nums">{ago(item.ts)}</span>
        </div>
    );
    return (
        <div className="rounded-lg px-2 py-2 hover:bg-white/[0.03] transition-colors">
            {href ? <Link href={href}>{body}</Link> : body}
        </div>
    );
}

export default function ActivityPage() {
    const [cats, setCats] = useState<Set<string>>(new Set());
    const [status, setStatus] = useState<"all" | "ok" | "ko" | "info">("all");
    const [search, setSearch] = useState("");
    const [group, setGroup] = useState<"none" | "media">("none");

    const { data, isLoading, isFetching, refetch } = useActivityTimeline({
        categories: cats.size ? Array.from(cats) : undefined,
        statuses: status === "all" ? undefined : [status],
        search: search || undefined,
        group,
        limit: 300,
    });

    const toggleCat = (k: string) =>
        setCats((s) => {
            const n = new Set(s);
            if (n.has(k)) n.delete(k);
            else n.add(k);
            return n;
        });

    const total = data?.total ?? 0;

    return (
        <>
            <Header title="Activité" />
            <motion.div className="p-4 md:p-6 space-y-5 max-w-4xl mx-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                {/* Hero */}
                <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-emerald-600/15 via-teal-600/10 to-transparent ring-1 ring-white/5 p-6">
                    <div className="flex items-center gap-4">
                        <div className="rounded-xl bg-emerald-500/20 p-3">
                            <Activity className="h-6 w-6 text-emerald-400" />
                        </div>
                        <div className="flex-1">
                            <h2 className="text-2xl font-bold tracking-tight">Activité</h2>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                Téléchargements, sous-titres, lectures, ajouts — tout ce qui se passe dans ta stack.
                            </p>
                        </div>
                        <Button variant="outline" size="icon" className="border-white/10" onClick={() => refetch()} title="Rafraîchir">
                            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
                        </Button>
                    </div>
                    <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-emerald-500/10 blur-3xl" />
                </div>

                {/* Filters */}
                <div className="flex flex-col gap-3 rounded-xl ring-1 ring-white/5 bg-card/30 backdrop-blur-sm p-3">
                    <div className="flex flex-wrap items-center gap-2">
                        {CATEGORIES.map((c) => {
                            const active = cats.has(c.key);
                            const Icon = c.icon;
                            return (
                                <button
                                    key={c.key}
                                    onClick={() => toggleCat(c.key)}
                                    className={cn(
                                        "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors",
                                        active ? "border-white/20 bg-white/10" : "border-white/10 text-muted-foreground hover:bg-white/5"
                                    )}
                                >
                                    <Icon className={cn("h-3.5 w-3.5", active ? c.color : "")} />
                                    {c.label}
                                </button>
                            );
                        })}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <div className="relative flex-1 min-w-[160px] max-w-xs">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                            <Input
                                placeholder="Filtrer par titre…"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="pl-10 border-white/10 bg-transparent h-9"
                            />
                        </div>
                        {/* Status */}
                        <div className="flex rounded-lg border border-white/10 overflow-hidden">
                            {([
                                ["all", "Tous"],
                                ["ok", "OK"],
                                ["ko", "KO"],
                            ] as const).map(([k, lbl]) => (
                                <button
                                    key={k}
                                    onClick={() => setStatus(k)}
                                    className={cn(
                                        "px-3 py-1.5 text-xs transition-colors",
                                        status === k ? "bg-white/10 font-medium" : "text-muted-foreground hover:bg-white/5"
                                    )}
                                >
                                    {lbl}
                                </button>
                            ))}
                        </div>
                        {/* Group toggle */}
                        <div className="flex rounded-lg border border-white/10 overflow-hidden ml-auto">
                            <button
                                onClick={() => setGroup("none")}
                                className={cn("flex items-center gap-1 px-3 py-1.5 text-xs", group === "none" ? "bg-white/10 font-medium" : "text-muted-foreground hover:bg-white/5")}
                                title="Chronologique"
                            >
                                <Rows3 className="h-3.5 w-3.5" /> Chrono
                            </button>
                            <button
                                onClick={() => setGroup("media")}
                                className={cn("flex items-center gap-1 px-3 py-1.5 text-xs", group === "media" ? "bg-white/10 font-medium" : "text-muted-foreground hover:bg-white/5")}
                                title="Regrouper par média"
                            >
                                <LayoutGrid className="h-3.5 w-3.5" /> Par média
                            </button>
                        </div>
                    </div>
                </div>

                {/* Body */}
                {isLoading ? (
                    <div className="space-y-2">
                        {Array.from({ length: 10 }).map((_, i) => (
                            <div key={i} className="h-14 rounded-lg bg-muted/15 animate-pulse ring-1 ring-white/5" />
                        ))}
                    </div>
                ) : total === 0 ? (
                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                        <EmptyState icon={Activity} title="Aucune activité" description="Les actions apparaîtront ici au fil de l'eau." />
                    </div>
                ) : group === "media" && data?.groups ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                        {data.groups.map((g) => (
                            <Card key={g.key} className="border-0 ring-1 ring-white/5 bg-card/40">
                                <CardContent className="p-3">
                                    <div className="flex items-center gap-3 mb-2">
                                        {g.poster_url ? (
                                            // eslint-disable-next-line @next/next/no-img-element
                                            <img src={g.poster_url} alt="" className="h-12 w-8 rounded object-cover ring-1 ring-white/5" loading="lazy" />
                                        ) : (
                                            <div className="flex h-12 w-8 items-center justify-center rounded bg-muted/30">
                                                {g.media_type === "series" ? <Tv className="h-4 w-4 text-muted-foreground/40" /> : <Film className="h-4 w-4 text-muted-foreground/40" />}
                                            </div>
                                        )}
                                        <div className="min-w-0 flex-1">
                                            {g.media_type && g.media_id ? (
                                                <Link href={`/media/${g.media_type}/${g.media_id}`} className="text-sm font-semibold truncate hover:text-emerald-300 block">
                                                    {g.title}
                                                </Link>
                                            ) : (
                                                <p className="text-sm font-semibold truncate">{g.title}</p>
                                            )}
                                            <p className="text-[11px] text-muted-foreground">{g.count} événement{g.count > 1 ? "s" : ""}</p>
                                        </div>
                                    </div>
                                    <div className="space-y-0.5">
                                        {g.items.map((it) => (
                                            <Row key={it.id} item={it} compact />
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-1.5">
                        {data?.items?.map((it) => (
                            <Row key={it.id} item={it} />
                        ))}
                    </div>
                )}
            </motion.div>
        </>
    );
}
