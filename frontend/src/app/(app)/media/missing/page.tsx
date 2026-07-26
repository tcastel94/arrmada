"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Film,
    Tv,
    Search,
    Loader2,
    PackageX,
    Eye,
    EyeOff,
    ChevronLeft,
    ChevronRight,
    SquareCheck,
    Square,
    CheckCircle2,
    ArrowLeft,
    CalendarPlus,
} from "lucide-react";
import { useMedia, useMediaFacets, type MediaItem } from "@/hooks/use-media";
import { useTriggerMediaSearch } from "@/hooks/use-media-actions";
import { cn } from "@/lib/utils";

/** French label + colour for a Radarr/Sonarr status. */
function statusLabel(item: MediaItem): { label: string; className: string } | null {
    const s = (item.status || "").toLowerCase();
    const map: Record<string, { label: string; className: string }> = {
        released: { label: "Sorti", className: "bg-emerald-600/20 text-emerald-300" },
        incinemas: { label: "Au cinéma", className: "bg-sky-600/20 text-sky-300" },
        announced: { label: "Annoncé", className: "bg-amber-600/20 text-amber-300" },
        tba: { label: "À venir", className: "bg-muted/40 text-muted-foreground" },
        continuing: { label: "En cours", className: "bg-emerald-600/20 text-emerald-300" },
        upcoming: { label: "À venir", className: "bg-amber-600/20 text-amber-300" },
        ended: { label: "Terminée", className: "bg-muted/40 text-muted-foreground" },
    };
    return map[s] ?? (s ? { label: item.status, className: "bg-muted/40 text-muted-foreground" } : null);
}

function fmtDate(iso: string | null): string | null {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function MissingRow({
    item,
    selected,
    onToggle,
    onSearch,
    searching,
    launched,
}: {
    item: MediaItem;
    selected: boolean;
    onToggle: () => void;
    onSearch: () => void;
    searching: boolean;
    launched: boolean;
}) {
    const st = statusLabel(item);
    const added = fmtDate(item.added);
    return (
        <div
            className={cn(
                "flex items-center gap-3 rounded-xl ring-1 p-2.5 transition-colors",
                selected ? "ring-violet-500/60 bg-violet-500/5" : "ring-white/5 bg-card/30 hover:bg-card/50"
            )}
        >
            {/* Checkbox */}
            <button
                onClick={onToggle}
                className="shrink-0 p-1"
                title={selected ? "Désélectionner" : "Sélectionner"}
            >
                {selected ? (
                    <SquareCheck className="h-5 w-5 text-violet-400" />
                ) : (
                    <Square className="h-5 w-5 text-white/30" />
                )}
            </button>

            {/* Poster */}
            <Link href={`/media/${item.type}/${item.external_id}`} className="shrink-0">
                <div className="relative h-16 w-11 overflow-hidden rounded-md bg-muted/20 ring-1 ring-white/5">
                    {item.poster_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={item.poster_url} alt={item.title} className="h-full w-full object-cover" loading="lazy" />
                    ) : (
                        <div className="flex h-full w-full items-center justify-center">
                            {item.type === "movie" ? (
                                <Film className="h-5 w-5 text-muted-foreground/30" />
                            ) : (
                                <Tv className="h-5 w-5 text-muted-foreground/30" />
                            )}
                        </div>
                    )}
                </div>
            </Link>

            {/* Info */}
            <div className="min-w-0 flex-1">
                <Link href={`/media/${item.type}/${item.external_id}`} className="group">
                    <p className="truncate text-sm font-semibold group-hover:text-violet-300">
                        {item.title}
                        {item.year && <span className="ml-1.5 font-normal text-muted-foreground">{item.year}</span>}
                    </p>
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <Badge className="gap-1 border-0 bg-black/40 text-[10px] text-white/70">
                        {item.type === "movie" ? <Film className="h-2.5 w-2.5" /> : <Tv className="h-2.5 w-2.5" />}
                        {item.type === "movie" ? "Film" : "Série"}
                    </Badge>
                    {item.monitored ? (
                        <Badge className="gap-1 border-0 bg-emerald-600/20 text-[10px] text-emerald-300">
                            <Eye className="h-2.5 w-2.5" /> Surveillé
                        </Badge>
                    ) : (
                        <Badge className="gap-1 border-0 bg-muted/40 text-[10px] text-muted-foreground">
                            <EyeOff className="h-2.5 w-2.5" /> Non surveillé
                        </Badge>
                    )}
                    {st && <Badge className={cn("border-0 text-[10px]", st.className)}>{st.label}</Badge>}
                    {added && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
                            <CalendarPlus className="h-2.5 w-2.5" /> {added}
                        </span>
                    )}
                    <span className="text-[10px] text-muted-foreground/40">{item.source_service}</span>
                </div>
            </div>

            {/* Search action */}
            <Button
                size="sm"
                variant={launched ? "outline" : "default"}
                disabled={searching || launched}
                onClick={onSearch}
                className={cn(
                    "shrink-0 gap-1.5",
                    launched
                        ? "border-emerald-500/40 text-emerald-300"
                        : "bg-violet-600 hover:bg-violet-500"
                )}
                title={!item.monitored ? "Astuce : le média n'est pas surveillé — la recherche peut ne rien récupérer" : "Lancer la recherche automatique"}
            >
                {searching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                ) : launched ? (
                    <CheckCircle2 className="h-4 w-4" />
                ) : (
                    <Search className="h-4 w-4" />
                )}
                {launched ? "Lancé" : "Rechercher"}
            </Button>
        </div>
    );
}

export default function MissingMediaPage() {
    const [type, setType] = useState<string>("all");
    const [search, setSearch] = useState("");
    const [sort, setSort] = useState("title");
    const [monitoredOnly, setMonitoredOnly] = useState(false);
    const [page, setPage] = useState(1);

    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [searchingIds, setSearchingIds] = useState<Set<string>>(new Set());
    const [launchedIds, setLaunchedIds] = useState<Set<string>>(new Set());

    const queryClient = useQueryClient();
    const triggerSearch = useTriggerMediaSearch();
    const { data: facets } = useMediaFacets();

    const { data, isLoading } = useMedia({
        type: type === "all" ? undefined : type,
        search: search || undefined,
        availability: "missing",
        monitored: monitoredOnly ? true : undefined,
        sort,
        order: "asc",
        page,
        per_page: 50,
    });

    const items = data?.items ?? [];

    const key = (i: MediaItem) => `${i.type}:${i.external_id}`;

    const runSearch = async (item: MediaItem) => {
        const k = key(item);
        setSearchingIds((s) => new Set(s).add(k));
        try {
            await triggerSearch.mutateAsync({ type: item.type, id: item.external_id });
            setLaunchedIds((s) => new Set(s).add(k));
            toast.success(`Recherche lancée : ${item.title}`);
        } catch (e: any) {
            toast.error(`Échec de la recherche : ${item.title}`, {
                description: e?.message ?? "Erreur inconnue",
            });
        } finally {
            setSearchingIds((s) => {
                const n = new Set(s);
                n.delete(k);
                return n;
            });
        }
    };

    const searchMany = async (targets: MediaItem[]) => {
        if (targets.length === 0) return;
        toast.info(`Lancement de ${targets.length} recherche(s)…`);
        // Sequentially to avoid hammering the indexers all at once.
        for (const it of targets) {
            // eslint-disable-next-line no-await-in-loop
            await runSearch(it);
        }
        setSelectedIds(new Set());
    };

    const selectedItems = useMemo(
        () => items.filter((i) => selectedIds.has(key(i))),
        [items, selectedIds]
    );

    const toggle = (i: MediaItem) => {
        const k = key(i);
        setSelectedIds((s) => {
            const n = new Set(s);
            if (n.has(k)) n.delete(k);
            else n.add(k);
            return n;
        });
    };

    const allSelected = items.length > 0 && items.every((i) => selectedIds.has(key(i)));
    const toggleAll = () => {
        if (allSelected) setSelectedIds(new Set());
        else setSelectedIds(new Set(items.map(key)));
    };

    return (
        <>
            <Header title="Médias manquants" />
            <div className="p-4 md:p-6 space-y-5 max-w-[1100px] mx-auto">
                {/* Hero */}
                <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-amber-600/20 via-orange-600/10 to-transparent ring-1 ring-white/5 p-6">
                    <div className="flex items-center gap-4">
                        <div className="rounded-xl bg-amber-500/20 p-3">
                            <PackageX className="h-6 w-6 text-amber-400" />
                        </div>
                        <div className="flex-1">
                            <h2 className="text-2xl font-bold tracking-tight">Médias manquants</h2>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                {facets ? (
                                    <>
                                        <span className="font-semibold text-foreground tabular-nums">{facets.missing_count}</span>{" "}
                                        média{facets.missing_count !== 1 ? "s" : ""} sans fichier
                                        {facets.missing_monitored_count > 0 && (
                                            <> — dont <span className="font-semibold text-amber-300 tabular-nums">{facets.missing_monitored_count}</span> surveillé{facets.missing_monitored_count !== 1 ? "s" : ""}</>
                                        )}
                                    </>
                                ) : (
                                    "Chargement…"
                                )}
                            </p>
                        </div>
                        <Button variant="outline" size="sm" asChild className="border-white/10 gap-1.5">
                            <Link href="/media">
                                <ArrowLeft className="h-4 w-4" /> Médiathèque
                            </Link>
                        </Button>
                    </div>
                    <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-amber-500/10 blur-3xl" />
                </div>

                {/* Toolbar */}
                <div className="flex flex-col sm:flex-row flex-wrap gap-3 items-start sm:items-center rounded-xl ring-1 ring-white/5 bg-card/30 backdrop-blur-sm p-3">
                    <div className="relative flex-1 min-w-[180px] max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                        <Input
                            placeholder="Filtrer par titre…"
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setPage(1);
                            }}
                            className="pl-10 border-white/10 bg-transparent"
                        />
                    </div>

                    <Tabs value={type} onValueChange={(v) => { setType(v); setPage(1); }}>
                        <TabsList className="bg-muted/30">
                            <TabsTrigger value="all">Tout</TabsTrigger>
                            <TabsTrigger value="movie"><Film className="h-3 w-3 mr-1" />Films</TabsTrigger>
                            <TabsTrigger value="series"><Tv className="h-3 w-3 mr-1" />Séries</TabsTrigger>
                        </TabsList>
                    </Tabs>

                    <Select value={sort} onValueChange={(v) => { setSort(v); setPage(1); }}>
                        <SelectTrigger className="w-[140px] border-white/10 bg-transparent">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="title">Titre</SelectItem>
                            <SelectItem value="year">Année</SelectItem>
                            <SelectItem value="added">Ajouté le</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button
                        variant={monitoredOnly ? "default" : "outline"}
                        size="sm"
                        onClick={() => { setMonitoredOnly((m) => !m); setPage(1); }}
                        className={cn("gap-1.5", monitoredOnly ? "bg-emerald-600 hover:bg-emerald-500" : "border-white/10")}
                    >
                        <Eye className="h-4 w-4" /> Surveillés
                    </Button>

                    <div className="hidden lg:flex flex-1" />

                    {/* Bulk actions */}
                    <div className="flex items-center gap-2 ml-auto">
                        {items.length > 0 && (
                            <Button variant="ghost" size="sm" onClick={toggleAll} className="gap-1.5 text-muted-foreground">
                                {allSelected ? <SquareCheck className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                                {allSelected ? "Aucun" : "Tout"}
                            </Button>
                        )}
                        {selectedIds.size > 0 ? (
                            <Button
                                size="sm"
                                onClick={() => searchMany(selectedItems)}
                                disabled={triggerSearch.isPending}
                                className="gap-1.5 bg-violet-600 hover:bg-violet-500"
                            >
                                <Search className="h-4 w-4" />
                                Rechercher ({selectedIds.size})
                            </Button>
                        ) : (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => searchMany(items)}
                                disabled={items.length === 0 || triggerSearch.isPending}
                                className="gap-1.5 border-violet-500/40 text-violet-300 hover:bg-violet-500/10"
                            >
                                <Search className="h-4 w-4" />
                                Tout rechercher
                            </Button>
                        )}
                    </div>
                </div>

                {/* List */}
                {isLoading ? (
                    <div className="space-y-2">
                        {Array.from({ length: 10 }).map((_, i) => (
                            <div key={i} className="h-[86px] rounded-xl bg-muted/15 animate-pulse ring-1 ring-white/5" />
                        ))}
                    </div>
                ) : items.length === 0 ? (
                    <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                        <EmptyState
                            icon={CheckCircle2}
                            title="Rien ne manque ici 🎉"
                            description={
                                search || type !== "all" || monitoredOnly
                                    ? "Aucun média manquant ne correspond à ces filtres"
                                    : "Tous vos médias suivis ont un fichier"
                            }
                        />
                    </div>
                ) : (
                    <div className="space-y-2">
                        {items.map((item) => {
                            const k = key(item);
                            return (
                                <MissingRow
                                    key={k}
                                    item={item}
                                    selected={selectedIds.has(k)}
                                    onToggle={() => toggle(item)}
                                    onSearch={() => runSearch(item)}
                                    searching={searchingIds.has(k)}
                                    launched={launchedIds.has(k)}
                                />
                            );
                        })}
                    </div>
                )}

                {/* Pagination */}
                {data && data.pagination.total_pages > 1 && (
                    <div className="flex items-center justify-center gap-3">
                        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="gap-1 border-white/10">
                            <ChevronLeft className="h-4 w-4" /> Précédent
                        </Button>
                        <span className="text-sm text-muted-foreground tabular-nums">
                            {page} / {data.pagination.total_pages}
                        </span>
                        <Button variant="outline" size="sm" disabled={page >= data.pagination.total_pages} onClick={() => setPage(page + 1)} className="gap-1 border-white/10">
                            Suivant <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                )}
            </div>
        </>
    );
}
