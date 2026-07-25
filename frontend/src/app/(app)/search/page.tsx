"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Search,
    Brain,
    Plus,
    CheckCircle2,
    Film,
    Tv,
    Loader2,
    ListChecks,
    Flame,
    Trash2,
    Sparkles,
} from "lucide-react";
import {
    useUnifiedSearch,
    useAISearch,
    useDiscoverLookup,
    type LookupItem,
} from "@/hooks/use-search";
import { useCreateRequest, useRequests, useDeleteRequest } from "@/hooks/use-requests";
import { apiFetch } from "@/lib/api-client";
import type { MediaItem } from "@/hooks/use-media";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

/* ── A generic addable/linkable item ───────────────────────── */
interface DiscoverItem {
    tmdb_id: number | null;
    title: string;
    type: "movie" | "series";
    year: number | string | null;
    poster_url: string | null;
    in_library?: boolean;
}

function TypeIcon({ type, className }: { type: string; className?: string }) {
    return type === "series" ? <Tv className={className} /> : <Film className={className} />;
}

function PosterTile({
    title,
    subtitle,
    poster,
    type,
    href,
    owned,
    onAdd,
    addState,
}: {
    title: string;
    subtitle?: string;
    poster: string | null;
    type: string;
    href?: string;
    owned?: boolean;
    onAdd?: () => void;
    addState?: "idle" | "adding" | "added";
}) {
    const inner = (
        <Card className="overflow-hidden border-0 ring-1 ring-white/5 bg-card/40 hover:ring-white/15 transition h-full">
            <div className="relative aspect-[2/3] bg-muted/20">
                {poster ? (
                    <img src={poster} alt={title} loading="lazy" className="w-full h-full object-cover" />
                ) : (
                    <div className="w-full h-full flex items-center justify-center">
                        <TypeIcon type={type} className="h-8 w-8 text-muted-foreground/25" />
                    </div>
                )}
                <Badge className="absolute top-1.5 left-1.5 text-[9px] bg-black/60 border-0 text-white gap-1">
                    <TypeIcon type={type} className="h-2.5 w-2.5" />
                    {type === "series" ? "Série" : "Film"}
                </Badge>
                {owned && (
                    <Badge className="absolute top-1.5 right-1.5 text-[9px] bg-emerald-600/85 border-0 text-white">
                        ✓
                    </Badge>
                )}
                {onAdd && (
                    <button
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onAdd();
                        }}
                        disabled={addState !== "idle"}
                        title="Ajouter et lancer la recherche"
                        className="absolute bottom-1.5 right-1.5 rounded-md bg-primary/90 hover:bg-primary text-primary-foreground p-1.5 disabled:opacity-80"
                    >
                        {addState === "adding" ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : addState === "added" ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                            <Plus className="h-3.5 w-3.5" />
                        )}
                    </button>
                )}
            </div>
            <CardContent className="p-2">
                <p className="text-xs font-medium truncate" title={title}>{title}</p>
                {subtitle && <p className="text-[10px] text-muted-foreground truncate">{subtitle}</p>}
            </CardContent>
        </Card>
    );
    return href ? (
        <Link href={href} className="block h-full hover:opacity-95 transition-opacity">{inner}</Link>
    ) : (
        <div className="h-full">{inner}</div>
    );
}

/* ── Shared "add to library" logic ─────────────────────────── */
function useAdder() {
    const createReq = useCreateRequest();
    const [added, setAdded] = useState<Set<string>>(new Set());
    const [adding, setAdding] = useState<string | null>(null);
    const keyOf = (it: DiscoverItem) => `${it.type}:${it.tmdb_id}`;
    const add = (it: DiscoverItem) => {
        const k = keyOf(it);
        setAdding(k);
        createReq.mutate(
            {
                title: it.title,
                type: it.type,
                tmdb_id: it.tmdb_id ?? undefined,
                year: it.year ? Number(it.year) : undefined,
                poster_url: it.poster_url ?? undefined,
            },
            {
                onSuccess: () => {
                    setAdded((p) => new Set(p).add(k));
                    toast.success(`« ${it.title} » ajouté — recherche lancée.`);
                },
                onError: (e) => toast.error("Échec de l'ajout : " + e.message),
                onSettled: () => setAdding(null),
            },
        );
    };
    const stateOf = (it: DiscoverItem): "idle" | "adding" | "added" =>
        added.has(keyOf(it)) ? "added" : adding === keyOf(it) ? "adding" : "idle";
    return { add, stateOf };
}

const GRID = "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3";

/* ── Tab 1: Search (library + add) ─────────────────────────── */
function SearchTab() {
    const [mode, setMode] = useState<"standard" | "ai">("standard");
    const [query, setQuery] = useState("");
    const [submitted, setSubmitted] = useState("");

    const std = useUnifiedSearch(mode === "standard" ? submitted : "");
    const ai = useAISearch(mode === "ai" ? submitted : "");
    const discover = useDiscoverLookup(submitted, mode === "standard");
    const { add, stateOf } = useAdder();

    const library: MediaItem[] = mode === "ai" ? ai.data?.items ?? [] : std.data?.library.items ?? [];
    const addable: LookupItem[] = (discover.data ?? []).filter((x) => !x.in_library);
    const busy = mode === "standard" ? std.isFetching || discover.isFetching : ai.isFetching;

    const run = () => setSubmitted(query.trim());

    return (
        <div className="space-y-5">
            <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-3 space-y-3">
                <div className="flex gap-2">
                    <Button
                        size="sm"
                        variant={mode === "standard" ? "default" : "outline"}
                        className={cn(mode === "standard" ? "bg-teal-600 hover:bg-teal-500" : "border-white/10")}
                        onClick={() => { setMode("standard"); setSubmitted(""); }}
                    >
                        <Search className="h-4 w-4 mr-1.5" /> Titre
                    </Button>
                    <Button
                        size="sm"
                        variant={mode === "ai" ? "default" : "outline"}
                        className={cn(mode === "ai" ? "bg-violet-600 hover:bg-violet-500" : "border-white/10")}
                        onClick={() => { setMode("ai"); setSubmitted(""); }}
                    >
                        <Brain className="h-4 w-4 mr-1.5" /> IA
                    </Button>
                </div>
                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                        <Input
                            autoFocus
                            placeholder={mode === "ai" ? "Ex: films de SF des années 80 que je n'ai pas" : "Titre d'un film ou d'une série…"}
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && run()}
                            className="pl-10 border-white/10 bg-transparent"
                        />
                    </div>
                    <Button onClick={run} disabled={query.trim().length < 2}>
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "ai" ? "Analyser" : "Rechercher"}
                    </Button>
                </div>
            </div>

            {!submitted && (
                <EmptyState
                    icon={mode === "ai" ? Brain : Search}
                    title={mode === "ai" ? "Recherche en langage naturel" : "Recherche unifiée"}
                    description="Trouve un titre dans ta bibliothèque ou ajoute-en un nouveau en un clic."
                />
            )}

            {submitted && busy && (
                <div className={GRID}>
                    {Array.from({ length: 12 }).map((_, i) => (
                        <div key={i} className="aspect-[2/3] rounded-xl bg-muted/15 animate-pulse ring-1 ring-white/5" />
                    ))}
                </div>
            )}

            {submitted && !busy && (
                <div className="space-y-6">
                    {library.length > 0 && (
                        <section className="space-y-2">
                            <h3 className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5">
                                <CheckCircle2 className="h-4 w-4" /> Dans ta bibliothèque ({library.length})
                            </h3>
                            <div className={GRID}>
                                {library.map((m) => (
                                    <PosterTile
                                        key={`${m.type}-${m.external_id}`}
                                        title={m.title}
                                        subtitle={m.year ? String(m.year) : undefined}
                                        poster={m.poster_url}
                                        type={m.type}
                                        href={`/media/${m.type}/${m.external_id}`}
                                        owned
                                    />
                                ))}
                            </div>
                        </section>
                    )}

                    {mode === "standard" && addable.length > 0 && (
                        <section className="space-y-2">
                            <h3 className="text-sm font-semibold flex items-center gap-1.5">
                                <Plus className="h-4 w-4" /> À ajouter ({addable.length})
                            </h3>
                            <div className={GRID}>
                                {addable.map((it) => (
                                    <PosterTile
                                        key={`${it.type}-${it.tmdb_id}`}
                                        title={it.title}
                                        subtitle={it.year ? String(it.year) : undefined}
                                        poster={it.poster_url}
                                        type={it.type}
                                        onAdd={() => add(it)}
                                        addState={stateOf(it)}
                                    />
                                ))}
                            </div>
                        </section>
                    )}

                    {library.length === 0 && (mode === "ai" || addable.length === 0) && (
                        <EmptyState icon={Search} title="Aucun résultat" description={`Rien trouvé pour « ${submitted} ».`} />
                    )}
                </div>
            )}
        </div>
    );
}

/* ── Tab 2: Tracking (requests status) ─────────────────────── */
const REQ_STATUS: Record<string, { label: string; cls: string }> = {
    requested: { label: "En attente", cls: "bg-slate-500" },
    searching: { label: "Recherche", cls: "bg-yellow-500" },
    downloading: { label: "Téléchargement", cls: "bg-blue-500" },
    available: { label: "Disponible", cls: "bg-emerald-500" },
    failed: { label: "Échec", cls: "bg-red-500" },
};

function TrackingTab() {
    const { data, isLoading } = useRequests();
    const del = useDeleteRequest();

    if (isLoading) {
        return (
            <div className="space-y-2">
                {[0, 1, 2].map((i) => <div key={i} className="h-16 rounded-lg bg-muted/15 animate-pulse" />)}
            </div>
        );
    }
    if (!data || data.items.length === 0) {
        return <EmptyState icon={ListChecks} title="Aucun suivi" description="Les médias que tu ajoutes apparaissent ici avec leur statut de téléchargement." />;
    }
    return (
        <div className="space-y-2">
            {data.items.map((req) => {
                const s = REQ_STATUS[req.status] || REQ_STATUS.requested;
                return (
                    <Card key={req.id} className="bg-card/40 border-border/50">
                        <CardContent className="p-3 flex items-center gap-3">
                            <div className="w-10 h-14 rounded overflow-hidden bg-muted/30 shrink-0">
                                {req.poster_url && <img src={req.poster_url} alt="" className="w-full h-full object-cover" />}
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium truncate">{req.title}</p>
                                <p className="text-xs text-muted-foreground">
                                    {req.type === "series" ? "Série" : "Film"}{req.year ? ` · ${req.year}` : ""}
                                </p>
                            </div>
                            <Badge className={cn("text-[10px] border-0 text-white gap-1.5", s.cls + "/80")}>
                                <span className={cn("h-1.5 w-1.5 rounded-full", s.cls)} /> {s.label}
                            </Badge>
                            <Button
                                size="icon"
                                variant="ghost"
                                className="h-8 w-8 shrink-0 text-muted-foreground hover:text-red-400"
                                onClick={() => del.mutate(req.id)}
                                title="Retirer du suivi"
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}

/* ── Tab 3: Suggestions (TMDB trending + personalised) ─────── */
interface DiscoveryData {
    trending_movies: DiscoverItem[];
    trending_series: DiscoverItem[];
    because_you_have: DiscoverItem[];
    wanted: { title: string; type: string; year: number | null; poster_url: string | null }[];
    tmdb_available: boolean;
}

function SuggestionRow({ title, icon, items }: { title: string; icon: React.ReactNode; items: DiscoverItem[] }) {
    const { add, stateOf } = useAdder();
    if (!items || items.length === 0) return null;
    return (
        <section className="space-y-2">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">{icon} {title}</h3>
            <div className={GRID}>
                {items.map((it) => (
                    <PosterTile
                        key={`${it.type}-${it.tmdb_id}`}
                        title={it.title}
                        subtitle={it.year ? String(it.year) : undefined}
                        poster={it.poster_url}
                        type={it.type}
                        owned={it.in_library}
                        onAdd={it.in_library ? undefined : () => add(it)}
                        addState={stateOf(it)}
                    />
                ))}
            </div>
        </section>
    );
}

function SuggestionsTab() {
    const { data, isLoading } = useQuery<DiscoveryData>({
        queryKey: ["recommendations"],
        queryFn: () => apiFetch("/api/recommendations"),
        staleTime: 120_000,
    });

    if (isLoading) {
        return (
            <div className={GRID}>
                {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="aspect-[2/3] rounded-xl bg-muted/15 animate-pulse ring-1 ring-white/5" />
                ))}
            </div>
        );
    }
    if (!data || !data.tmdb_available) {
        return <EmptyState icon={Sparkles} title="Suggestions indisponibles" description="TMDB n'est pas configuré." />;
    }
    return (
        <div className="space-y-6">
            <SuggestionRow title="Parce que tu as aimé" icon={<Sparkles className="h-4 w-4 text-violet-400" />} items={data.because_you_have} />
            <SuggestionRow title="Films tendance" icon={<Flame className="h-4 w-4 text-orange-400" />} items={data.trending_movies} />
            <SuggestionRow title="Séries tendance" icon={<Flame className="h-4 w-4 text-orange-400" />} items={data.trending_series} />
        </div>
    );
}

/* ── Page ──────────────────────────────────────────────────── */
export default function SearchHubPage() {
    const { data: reqData } = useRequests();
    const activeCount = reqData?.items.filter((r) => r.status !== "available" && r.status !== "failed").length ?? 0;

    return (
        <>
            <Header title="Rechercher & Ajouter" />
            <div className="p-4 md:p-6 space-y-5 max-w-[1500px] mx-auto">
                <Tabs defaultValue="search">
                    <TabsList className="bg-muted/30">
                        <TabsTrigger value="search"><Search className="h-4 w-4 mr-1.5" /> Rechercher</TabsTrigger>
                        <TabsTrigger value="tracking">
                            <ListChecks className="h-4 w-4 mr-1.5" /> Suivi
                            {activeCount > 0 && (
                                <span className="ml-1.5 rounded-full bg-primary/80 text-primary-foreground text-[10px] px-1.5">{activeCount}</span>
                            )}
                        </TabsTrigger>
                        <TabsTrigger value="discover"><Flame className="h-4 w-4 mr-1.5" /> Suggestions</TabsTrigger>
                    </TabsList>
                    <TabsContent value="search" className="mt-4"><SearchTab /></TabsContent>
                    <TabsContent value="tracking" className="mt-4"><TrackingTab /></TabsContent>
                    <TabsContent value="discover" className="mt-4"><SuggestionsTab /></TabsContent>
                </Tabs>
            </div>
        </>
    );
}
