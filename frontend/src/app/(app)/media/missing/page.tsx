"use client";

/**
 * Manquants (/media/missing) — médias suivis par Radarr/Sonarr mais sans
 * fichier, avec lancement des recherches automatiques (unitaire ou groupé).
 * ----------------------------------------------------------------
 * Corrections par rapport à l'ancienne page :
 *  - la sélection garde les OBJETS sélectionnés (Map id → média) : changer
 *    de page ne fait plus « perdre » la moitié de la sélection au moment de
 *    lancer (avant, le bouton annonçait 12 mais n'en cherchait que 5) ;
 *  - « Tout rechercher » ne prétend plus tout chercher : le bouton dit
 *    honnêtement « Rechercher les N de la page » ;
 *  - un seul toast de progression pour une recherche groupée, annulable
 *    (Stop) et arrêtée si on quitte la page ;
 *  - recherche debouncée, tri ascendant / descendant, état d'erreur dédié
 *    (avant : « Rien ne manque 🎉 » s'affichait quand l'API était en panne).
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
    ArrowDownWideNarrow,
    ArrowUpNarrowWide,
    CheckCircle2,
    CheckSquare,
    Eye,
    Film,
    LayoutGrid,
    List,
    Loader2,
    PackageX,
    Rocket,
    Search,
    SlidersHorizontal,
    Square,
    Tv,
    X,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton, Shimmer } from "@/components/shared/loading-skeleton";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useMedia, useMediaFacets, type MediaItem } from "@/hooks/use-media";
import { useDebounce } from "@/hooks/use-debounce";
import { formatNumber, plural } from "@/lib/format";
import { stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useParamState, usePageParam, writeParams } from "@/components/library/use-param-state";
import { SegmentedControl } from "@/components/library/segmented-control";
import { LiveCount } from "@/components/library/live-count";
import { SmartPagination } from "@/components/library/smart-pagination";
import { FloatingBar, SelectionCount } from "@/components/library/floating-bar";
import { SearchField, StickyToolbar } from "@/components/library/toolbar";
import { mediaHref, mediaKey } from "@/components/library/media-card";
import { MissingRow, RowSearchButton, releaseStatus } from "@/components/library/missing-row";
import { useBulkSearch } from "@/components/library/use-bulk-search";

const PER_PAGE = 50;
const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";
const TYPES = ["all", "movie", "series"] as const;
const SORTS = ["title", "year", "added"] as const;
const ORDERS = ["asc", "desc"] as const;
const VIEWS = ["list", "grid"] as const;
type Sort = (typeof SORTS)[number];
const SORT_LABELS: Record<Sort, string> = { title: "Titre", year: "Année", added: "Date d'ajout" };

export default function MissingMediaPage() {
    return (
        <>
            <Header title="Manquants" />
            <Suspense
                fallback={
                    <PageContainer>
                        <Shimmer className="h-40 w-full rounded-3xl" />
                        <Shimmer className="h-[420px] w-full rounded-2xl" />
                    </PageContainer>
                }
            >
                <MissingMedia />
            </Suspense>
        </>
    );
}

function MissingMedia() {
    const params = useSearchParams();
    const [type] = useParamState("type", "all", TYPES);
    const [sort] = useParamState<Sort>("sort", "title", SORTS);
    const [order] = useParamState("order", "asc", ORDERS);
    const [view, setView] = useParamState("view", "list", VIEWS);
    const [monitoredOnly] = useParamState("mon", "0", ["0", "1"] as const);
    const [page, setPage] = usePageParam();

    const setFilter = useCallback((key: string, value: string, defaultValue: string) => {
        writeParams({ [key]: value === defaultValue ? null : value, page: null });
    }, []);

    /* ── Recherche debouncée synchronisée avec ?q= ── */
    const urlQuery = (params.get("q") ?? "").trim();
    const [searchInput, setSearchInput] = useState(urlQuery);
    const lastSynced = useRef(urlQuery);
    const debouncedSearch = useDebounce(searchInput.trim(), 300);
    useEffect(() => {
        if (urlQuery !== lastSynced.current) {
            lastSynced.current = urlQuery;
            setSearchInput(urlQuery);
        }
    }, [urlQuery]);
    useEffect(() => {
        if (debouncedSearch === lastSynced.current) return;
        lastSynced.current = debouncedSearch;
        writeParams({ q: debouncedSearch || null, page: null });
    }, [debouncedSearch]);

    /* ── Données ── */
    const { data, isLoading, isError, error, refetch, isFetching, isPlaceholderData } = useMedia({
        type: type === "all" ? undefined : type,
        search: urlQuery || undefined,
        availability: "missing",
        monitored: monitoredOnly === "1" ? true : undefined,
        sort,
        order,
        page,
        per_page: PER_PAGE,
    });
    const { data: facets } = useMediaFacets();
    const items = useMemo(() => data?.items ?? [], [data]);
    const total = data?.pagination.total ?? 0;
    const totalPages = data?.pagination.total_pages ?? 1;

    useEffect(() => {
        const maxPage = Math.max(1, totalPages);
        if (data && !isPlaceholderData && page > maxPage) setPage(maxPage);
    }, [data, isPlaceholderData, page, totalPages, setPage]);

    const goToPage = (p: number) => {
        setPage(p);
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    /* ── Recherches ── */
    const { rowStates, progress, running, searchOne, runBulk, stop } = useBulkSearch();
    const launchedCount = Object.values(rowStates).filter((s) => s === "launched").length;
    // « Rechercher les N de la page » ignore ceux déjà lancés pendant la session.
    const pagePending = items.filter((i) => rowStates[mediaKey(i)] !== "launched");

    /* ── Sélection (persiste entre les pages, objets complets) ── */
    const [selected, setSelected] = useState<Map<string, MediaItem>>(() => new Map());
    const [selectMode, setSelectMode] = useState(false); // vue grille uniquement
    const toggle = (item: MediaItem) =>
        setSelected((prev) => {
            const next = new Map(prev);
            const k = mediaKey(item);
            if (next.has(k)) next.delete(k);
            else next.set(k, item);
            return next;
        });
    const allPageSelected = items.length > 0 && items.every((i) => selected.has(mediaKey(i)));
    const toggleAllPage = () =>
        setSelected((prev) => {
            const next = new Map(prev);
            if (allPageSelected) items.forEach((i) => next.delete(mediaKey(i)));
            else items.forEach((i) => next.set(mediaKey(i), i));
            return next;
        });
    const clearSelection = useCallback(() => {
        setSelected(new Map());
        setSelectMode(false);
    }, []);

    const searchSelection = async () => {
        const targets = Array.from(selected.values());
        const result = await runBulk(targets);
        // On ne garde sélectionnés que ceux qui n'ont pas abouti.
        if (result && !result.interrupted) clearSelection();
    };

    useEffect(() => {
        if (selected.size === 0 && !selectMode) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key !== "Escape" || running) return;
            // Échap ferme d'abord une liste déroulante / boîte ouverte.
            if (document.querySelector("[role='dialog'], [data-radix-popper-content-wrapper]")) return;
            clearSelection();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [selected.size, selectMode, running, clearSelection]);

    const hasFilters = !!urlQuery || type !== "all" || monitoredOnly === "1";
    const listKey = `${data?.pagination.page ?? 0}:${type}:${sort}:${order}:${monitoredOnly}:${urlQuery}:${view}`;
    const barOpen = running || selected.size > 0 || selectMode;

    return (
        <>
            <PageContainer>
                <PageHeader
                    icon={PackageX}
                    accent="amber"
                    title="Manquants"
                    description="Films et séries suivis sans fichier : relance leur recherche automatique sur tes indexers, un par un ou par lots."
                    actions={
                        // « Tout rechercher » : lance la recherche des manquants de la page
                        <Button size="sm" variant="tinted" onClick={() => runBulk(pagePending)} disabled={running || pagePending.length === 0}>
                            {running ? <Loader2 className="animate-spin" /> : <Rocket />}
                            {pagePending.length === 0 && items.length > 0 ? (
                                "Tout est lancé"
                            ) : (
                                <>
                                    <span className="hidden sm:inline">Tout rechercher</span>
                                    <span className="sm:hidden">Rechercher</span> ({pagePending.length})
                                </>
                            )}
                        </Button>
                    }
                >
                    <StatPill label="manquants" value={<LiveCount value={facets?.missing_count} />} icon={PackageX} tone="warning" />
                    <StatPill label="surveillés" value={<LiveCount value={facets?.missing_monitored_count} />} icon={Eye} />
                    <AnimatePresence>
                        {launchedCount > 0 && (
                            <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}>
                                <StatPill label="recherches lancées" value={<LiveCount value={launchedCount} />} icon={CheckCircle2} tone="success" />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </PageHeader>

                {/* ── Barre d'outils ── */}
                <StickyToolbar>
                    <div className="flex flex-wrap items-center gap-2">
                        <SearchField
                            className="min-w-[160px] flex-1"
                            value={searchInput}
                            onChange={setSearchInput}
                            // Spinner pendant la frappe (debounce) puis pendant la requête.
                            loading={searchInput.trim() !== urlQuery || (!!urlQuery && isFetching && isPlaceholderData)}
                            placeholder="Filtrer les manquants par titre…"
                            ariaLabel="Filtrer les médias manquants par titre"
                        />
                        <div className="-mx-1 flex w-full items-center gap-2 overflow-x-auto px-1 py-0.5 scrollbar-none lg:mx-0 lg:w-auto lg:overflow-visible lg:p-0">
                            <SegmentedControl
                                layoutId="missing-type-pill"
                                ariaLabel="Type de média"
                                value={type}
                                onChange={(v) => setFilter("type", v, "all")}
                                options={[
                                    { value: "all", label: "Tout" },
                                    { value: "movie", label: "Films", icon: Film },
                                    { value: "series", label: "Séries", icon: Tv },
                                ]}
                            />
                            <div className="flex shrink-0 items-center gap-1">
                                <Select value={sort} onValueChange={(v) => setFilter("sort", v, "title")}>
                                    <SelectTrigger className="h-[30px] w-auto shrink-0 gap-1.5 rounded-[9px] px-3 text-[13px]" aria-label="Trier par">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SORTS.map((s) => (
                                            <SelectItem key={s} value={s}>
                                                {SORT_LABELS[s]}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    variant="outline"
                                    size="icon"
                                    onClick={() => setFilter("order", order === "asc" ? "desc" : "asc", "asc")}
                                    aria-label={order === "asc" ? "Ordre croissant (cliquer pour inverser)" : "Ordre décroissant (cliquer pour inverser)"}
                                    title={order === "asc" ? "Croissant" : "Décroissant"}
                                >
                                    <motion.span key={order} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} transition={{ duration: 0.25 }}>
                                        {order === "asc" ? <ArrowUpNarrowWide className="h-4 w-4" /> : <ArrowDownWideNarrow className="h-4 w-4" />}
                                    </motion.span>
                                </Button>
                            </div>
                            <Button
                                variant={monitoredOnly === "1" ? "glow" : "outline"}
                                onClick={() => setFilter("mon", monitoredOnly === "1" ? "0" : "1", "0")}
                                aria-pressed={monitoredOnly === "1"}
                                className="shrink-0"
                            >
                                <Eye /> Surveillés uniquement
                            </Button>
                            <SegmentedControl
                                layoutId="missing-view-pill"
                                ariaLabel="Affichage"
                                value={view}
                                onChange={(v) => {
                                    setView(v);
                                    setSelectMode(false);
                                }}
                                options={[
                                    { value: "list", label: "Liste", icon: List, title: "Vue liste" },
                                    { value: "grid", label: "Grille", icon: LayoutGrid, title: "Vue grille" },
                                ]}
                            />
                            {view === "grid" && (
                                <Button
                                    variant={selectMode ? "glow" : "outline"}
                                    onClick={() => (selectMode ? clearSelection() : setSelectMode(true))}
                                    aria-pressed={selectMode}
                                    className="shrink-0"
                                >
                                    <CheckSquare /> Sélectionner
                                </Button>
                            )}
                        </div>
                    </div>
                </StickyToolbar>

                {/* ── Résumé ── */}
                {data && !isError && total > 0 && (
                    <div className="-mb-2 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-muted-foreground">
                        <div className="flex items-center gap-3">
                            {view === "list" && (
                                <button
                                    type="button"
                                    onClick={toggleAllPage}
                                    className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 transition-colors hover:bg-white/[0.05] hover:text-foreground"
                                >
                                    {allPageSelected ? <CheckSquare className="h-3.5 w-3.5 text-primary" /> : <Square className="h-3.5 w-3.5" />}
                                    {allPageSelected ? "Désélectionner la page" : "Sélectionner la page"}
                                </button>
                            )}
                            <p>
                                <span className="font-semibold tabular-nums text-foreground">{formatNumber(total)}</span>{" "}
                                {total > 1 ? "manquants" : "manquant"}
                                {totalPages > 1 && (
                                    <span className="tabular-nums">
                                        {" "}
                                        · page {page} / {totalPages}
                                    </span>
                                )}
                            </p>
                        </div>
                        {isFetching && !isLoading && (
                            <span className="flex items-center gap-1.5 text-primary">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Mise à jour…
                            </span>
                        )}
                    </div>
                )}

                {/* ── Contenu ── */}
                {isError ? (
                    <div className="glass rounded-2xl">
                        <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger les manquants" />
                    </div>
                ) : isLoading ? (
                    view === "grid" ? (
                        <PosterGridSkeleton count={14} />
                    ) : (
                        <div className="glass space-y-1.5 rounded-2xl p-2">
                            {Array.from({ length: 8 }).map((_, i) => (
                                <Shimmer key={i} className="h-[80px] w-full" />
                            ))}
                        </div>
                    )
                ) : total === 0 ? (
                    <div className="glass rounded-2xl">
                        {hasFilters ? (
                            <EmptyState
                                icon={SlidersHorizontal}
                                title="Aucun manquant ne correspond"
                                description={urlQuery ? `Rien pour « ${urlQuery} » avec ces filtres.` : "Essaie d'élargir les filtres."}
                                action={{
                                    label: "Réinitialiser les filtres",
                                    onClick: () => {
                                        setSearchInput("");
                                        lastSynced.current = "";
                                        writeParams({ q: null, type: null, mon: null, page: null });
                                    },
                                }}
                            />
                        ) : (
                            <EmptyState
                                tone="success"
                                icon={CheckCircle2}
                                title="Rien ne manque 🎉"
                                description="Tous tes médias suivis ont un fichier. Ta flotte est au complet."
                                action={{ label: "Ajouter un titre", href: "/search" }}
                            />
                        )}
                    </div>
                ) : view === "grid" ? (
                    <motion.div
                        key={listKey}
                        variants={stagger(0, 0.02)}
                        initial="hidden"
                        animate="show"
                        className={cn(GRID, "transition-opacity duration-300", isPlaceholderData && "opacity-60")}
                    >
                        {items.map((item) => {
                            const k = mediaKey(item);
                            const st = releaseStatus(item);
                            return (
                                <PosterCard
                                    key={k}
                                    title={item.title}
                                    subtitle={`${item.year ?? "—"} · ${item.type === "movie" ? "Film" : "Série"}`}
                                    posterUrl={item.poster_url}
                                    type={item.type}
                                    href={mediaHref(item)}
                                    dimmed
                                    badges={
                                        <>
                                            {item.monitored ? (
                                                <PosterBadge tone="success">
                                                    <Eye className="h-2.5 w-2.5" /> Surveillé
                                                </PosterBadge>
                                            ) : (
                                                <PosterBadge>Non surveillé</PosterBadge>
                                            )}
                                            {st && <PosterBadge>{st.label}</PosterBadge>}
                                        </>
                                    }
                                    corner={
                                        <RowSearchButton
                                            compact
                                            state={rowStates[k]}
                                            onSearch={() => searchOne(item)}
                                            disabled={running}
                                            title={item.title}
                                        />
                                    }
                                    selectable={selectMode}
                                    selected={selected.has(k)}
                                    onToggleSelect={() => toggle(item)}
                                />
                            );
                        })}
                    </motion.div>
                ) : (
                    <div className={cn("glass rounded-2xl p-1.5 transition-opacity duration-300 sm:p-2", isPlaceholderData && "opacity-60")}>
                        {/* La clé remonte la liste à chaque page (pas d'animations de sortie en masse) ;
                            dans une même page, un média qui disparaît (fichier arrivé) glisse hors de la liste. */}
                        <div key={listKey} className="space-y-0.5">
                            <AnimatePresence>
                                {items.map((item) => {
                                    const k = mediaKey(item);
                                    return (
                                        <MissingRow
                                            key={k}
                                            item={item}
                                            selected={selected.has(k)}
                                            onToggle={() => toggle(item)}
                                            onSearch={() => searchOne(item)}
                                            state={rowStates[k]}
                                            disabled={running}
                                        />
                                    );
                                })}
                            </AnimatePresence>
                        </div>
                    </div>
                )}

                {data && !isError && (
                    <SmartPagination page={page} totalPages={totalPages} onChange={goToPage} layoutId="missing-page-pill" className="pt-2" />
                )}
            </PageContainer>

            {/* ── Barre flottante : sélection ou progression de la recherche groupée ── */}
            <FloatingBar open={barOpen} label={running ? "Recherche groupée en cours" : "Actions de sélection"}>
                {running && progress ? (
                    <div className="flex w-[min(80vw,26rem)] items-center gap-3 px-1">
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                        <div className="min-w-0 flex-1 space-y-1.5">
                            <div className="flex items-center justify-between gap-2 text-xs">
                                <span className="truncate text-muted-foreground">
                                    <Search className="mr-1 inline h-3 w-3" />
                                    {progress.current}
                                </span>
                                <span className="shrink-0 font-semibold tabular-nums text-foreground">
                                    {progress.done}/{progress.total}
                                </span>
                            </div>
                            <GradientProgress value={(progress.done / progress.total) * 100} active />
                        </div>
                        <Button variant="destructive" size="sm" onClick={stop}>
                            <X /> Stop
                        </Button>
                    </div>
                ) : (
                    <>
                        <SelectionCount count={selected.size} />
                        <Button variant="ghost" size="sm" onClick={toggleAllPage} disabled={items.length === 0}>
                            <CheckSquare />
                            <span className="sm:hidden">{allPageSelected ? "Aucun" : "Page"}</span>
                            <span className="hidden sm:inline">{allPageSelected ? "Désélectionner la page" : "Tout sélectionner (page)"}</span>
                        </Button>
                        <Button size="sm" onClick={searchSelection} disabled={selected.size === 0}>
                            <Search />
                            Rechercher {selected.size > 0 && <span className="tabular-nums">({selected.size})</span>}
                        </Button>
                        <Button variant="ghost" size="icon-sm" onClick={clearSelection} aria-label="Annuler la sélection (Échap)">
                            <X />
                        </Button>
                    </>
                )}
            </FloatingBar>

            {/* Annonce aux lecteurs d'écran (la barre visuelle bouge, pas le focus). */}
            <p className="sr-only" aria-live="polite">
                {running && progress ? `Recherche ${progress.done} sur ${progress.total}` : selected.size > 0 ? plural(selected.size, "média sélectionné", "médias sélectionnés") : ""}
            </p>
        </>
    );
}
