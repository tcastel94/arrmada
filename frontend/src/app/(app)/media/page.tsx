"use client";

/**
 * Médiathèque (/media) — navigation dans toute la collection Radarr/Sonarr.
 * ----------------------------------------------------------------
 * Ce qui a changé par rapport à l'ancienne page :
 *  - Tous les réglages (recherche, type, tri, filtres, page, vue) vivent dans
 *    l'URL : un lien est partageable, et le retour arrière depuis une fiche
 *    ramène exactement à la même page (avant : retour systématique page 1).
 *    `?type=movie|series` (cartes du Dashboard) et `?q=` / `?search=`
 *    (palette ⌘K, anciens liens) sont lus dès le premier rendu.
 *  - Recherche « debouncée » (une requête quand tu as fini de taper, pas
 *    une par touche).
 *  - Pagination complète (1 … 4 5 6 … 20) au lieu des 7 premières pages.
 *  - Nouvelle vue Liste compacte, panneau de filtres animé, filtres actifs
 *    sous forme de chips supprimables.
 *  - Sélection multiple avec barre d'actions flottante ; suppression en
 *    parallèle avec bilan précis (succès / échecs) au lieu d'alert().
 *  - « Filtres enregistrés » : un jeu de filtres (= paramètres d'URL) peut
 *    être nommé, réappliqué en un clic ou supprimé (localStorage, voir
 *    lib/media-filters). Inutile de mémoriser les filtres en session :
 *    l'URL s'en charge déjà.
 *  - Affiches : badges techniques (4K · DV · Atmos) et studio / chaîne.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
    ArrowDownWideNarrow,
    ArrowUpNarrowWide,
    Check,
    CheckSquare,
    CloudDownload,
    LayoutGrid,
    Library,
    List,
    Loader2,
    MoreHorizontal,
    PackageX,
    Plus,
    RefreshCw,
    Search,
    Settings,
    SlidersHorizontal,
    Trash2,
    X,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { PageContainer } from "@/components/shared/page-container";
import { ArtworkRefreshButton } from "@/components/library/artwork-refresh-button";
import { LibrarySourcesBanner } from "@/components/library/library-sources-banner";
import { LocalSeriesRow } from "@/components/library/local-series-row";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton, Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLibrarySources, useMedia, useMediaFacets, type MediaItem } from "@/hooks/use-media";
import { useKodiSync } from "@/hooks/use-kodi";
import { useModuleEnabled } from "@/hooks/use-modules";
import { useDebounce } from "@/hooks/use-debounce";
import { apiFetch } from "@/lib/api-client";
import { formatNumber, plural } from "@/lib/format";
import { EASE_OUT, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useParamState, usePageParam, writeParams } from "@/components/library/use-param-state";
import { SegmentedControl } from "@/components/library/segmented-control";
import { SmartPagination } from "@/components/library/smart-pagination";
import { FloatingBar, SelectionCount } from "@/components/library/floating-bar";
import { FilterPresetsMenu, RemovableChip, SearchField, StickyToolbar } from "@/components/library/toolbar";
import { FilterSelect } from "@/components/library/filter-select";
import { useLibraryEnrichment } from "@/components/library/enrichment";
import {
    MediaListHeader,
    MediaListRow,
    MediaPosterCard,
    mediaKey,
} from "@/components/library/media-card";
import { translateGenre } from "@/lib/genres";
import {
    AVAIL_LABELS,
    MEDIA_AVAILS,
    MEDIA_MONITORS,
    MEDIA_ORDERS,
    MEDIA_SORTS,
    MEDIA_SUBS,
    MEDIA_TYPES,
    MEDIA_WATCHES,
    MONITOR_LABELS,
    SORT_LABELS,
    SUB_LABELS,
    WATCH_LABELS,
    choicesOf,
    paramsFromSearch,
    presetUpdates,
    type FilterPreset,
    type MediaSort,
} from "@/lib/media-filters";

/* ── Constantes ─────────────────────────────────────────────── */

const PER_PAGE = 48;
// 3 colonnes sur iPhone (comme l'app TV d'Apple), jusqu'à 8 sur grand écran.
const GRID = "grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";

// Valeurs autorisées et libellés des filtres : partagés avec les « filtres
// enregistrés » (lib/media-filters), pour qu'un préréglage parle le même langage.
const VIEWS = ["grid", "list"] as const;

type Sort = MediaSort;

const AVAIL_CHOICES = choicesOf(MEDIA_AVAILS, AVAIL_LABELS);
const MONITOR_CHOICES = choicesOf(MEDIA_MONITORS, MONITOR_LABELS);
const SUB_CHOICES = choicesOf(MEDIA_SUBS, SUB_LABELS);
const WATCH_CHOICES = choicesOf(MEDIA_WATCHES, WATCH_LABELS);

/* ── Page ───────────────────────────────────────────────────── */

export default function MediaPage() {
    return (
        <>
            <Header title="Médiathèque" />
            {/* useSearchParams (état dans l'URL) exige un Suspense au build. */}
            <Suspense
                fallback={
                    <PageContainer>
                        <Shimmer className="h-40 w-full rounded-3xl" />
                        <PosterGridSkeleton count={16} />
                    </PageContainer>
                }
            >
                <MediaLibrary />
            </Suspense>
        </>
    );
}

function MediaLibrary() {
    const queryClient = useQueryClient();
    const params = useSearchParams();

    /* ── État lu dans l'URL ── */
    const [type] = useParamState("type", "all", MEDIA_TYPES);
    const [sort] = useParamState<Sort>("sort", "title", MEDIA_SORTS);
    const [order] = useParamState("order", "asc", MEDIA_ORDERS);
    const [view, setView] = useParamState("view", "grid", VIEWS);
    const [genre] = useParamState<string>("genre", "all");
    const [quality] = useParamState<string>("quality", "all");
    const [availability] = useParamState("avail", "all", MEDIA_AVAILS);
    const [monitored] = useParamState("mon", "all", MEDIA_MONITORS);
    const [subFilter] = useParamState("sub", "all", MEDIA_SUBS);
    const [watchFilter] = useParamState("watch", "all", MEDIA_WATCHES);
    const [page, setPage] = usePageParam();

    /**
     * Change un filtre. Les filtres « serveur » reviennent en page 1 (sinon on
     * peut tomber sur une page vide) ; ST FR et Vu filtrent la page affichée,
     * on y reste donc.
     */
    const setFilter = useCallback((key: string, value: string, defaultValue = "all") => {
        const pageFilter = key === "sub" || key === "watch";
        writeParams({ [key]: value === defaultValue ? null : value, ...(pageFilter ? {} : { page: null }) });
    }, []);

    /* ── Recherche : champ local + écriture debouncée dans ?q= ── */
    // `?search=` = ancien lien de la palette ⌘K, toujours accepté en entrée.
    const urlQuery = (params.get("q") ?? params.get("search") ?? "").trim();
    const [searchInput, setSearchInput] = useState(urlQuery);
    const lastSynced = useRef(urlQuery);
    const debouncedSearch = useDebounce(searchInput.trim(), 300);

    // URL → champ : uniquement si l'URL a changé « de l'extérieur »
    // (navigation, palette…), pas suite à notre propre écriture.
    useEffect(() => {
        if (urlQuery !== lastSynced.current) {
            lastSynced.current = urlQuery;
            setSearchInput(urlQuery);
        }
    }, [urlQuery]);

    // Champ → URL, une fois la frappe terminée.
    useEffect(() => {
        if (debouncedSearch === lastSynced.current) return;
        lastSynced.current = debouncedSearch;
        writeParams({ q: debouncedSearch || null, search: null, page: null });
    }, [debouncedSearch]);

    /* ── Données ── */
    const { data, isLoading, isError, error, refetch, isFetching, isPlaceholderData } = useMedia({
        type: type === "all" ? undefined : type,
        search: urlQuery || undefined,
        sort,
        order,
        genre: genre === "all" ? undefined : genre,
        quality: quality === "all" ? undefined : quality,
        availability: availability === "all" ? undefined : availability,
        monitored: monitored === "all" ? undefined : monitored === "yes",
        page,
        per_page: PER_PAGE,
    });
    const { data: facets } = useMediaFacets();
    // Radarr / Sonarr injoignables : « ne répond pas » plutôt que « médiathèque vide »
    const downSources = (useLibrarySources().data?.sources ?? []).filter((source) => !source.ok);
    // Compteurs films / séries : requêtes minuscules (1 élément), servies
    // depuis le cache backend de la bibliothèque.
    const movieCount = useMedia({ type: "movie", per_page: 1 }).data?.pagination.total;
    const seriesCount = useMedia({ type: "series", per_page: 1 }).data?.pagination.total;
    const { subStateFor, watchStateFor, subtitlesAvailable, kodiAvailable } = useLibraryEnrichment();

    const total = data?.pagination.total ?? 0;
    const totalPages = data?.pagination.total_pages ?? 1;

    // Page hors limites (URL ancienne, suppression…) → dernière page valide.
    useEffect(() => {
        const maxPage = Math.max(1, totalPages);
        if (data && !isPlaceholderData && page > maxPage) setPage(maxPage);
    }, [data, isPlaceholderData, page, totalPages, setPage]);

    // Filtres ST FR / Vu : appliqués à la page chargée (les statuts viennent
    // de Bazarr / du vu partagé des TV, pas de l'API médias paginée côté serveur).
    const visibleItems = useMemo(() => {
        const items = data?.items ?? [];
        return items.filter((item) => {
            if (subFilter !== "all") {
                const s = subStateFor(item);
                if (subFilter === "missing" ? s !== "missing" : s !== "present") return false;
            }
            if (watchFilter !== "all") {
                const w = watchStateFor(item);
                // « En cours » : film commencé, ou série entamée (épisodes vus, pas tous)
                const started = !!w && !w.watched && ((w.progress ?? 0) > 0 || (w.episodes ?? 0) > 0);
                if (watchFilter === "watched" && !w?.watched) return false;
                if (watchFilter === "unwatched" && (w?.watched || started)) return false;
                if (watchFilter === "inprogress" && !started) return false;
            }
            return true;
        });
    }, [data, subFilter, watchFilter, subStateFor, watchStateFor]);

    /* ── Filtres actifs (chips) ── */
    const [showFilters, setShowFilters] = useState(false);
    const activeChips = useMemo(() => {
        const chips: { key: string; label: string; clear: () => void }[] = [];
        if (genre !== "all") chips.push({ key: "genre", label: `Genre : ${translateGenre(genre)}`, clear: () => setFilter("genre", "all") });
        if (quality !== "all") chips.push({ key: "quality", label: `Qualité : ${quality}`, clear: () => setFilter("quality", "all") });
        if (availability !== "all") chips.push({ key: "avail", label: AVAIL_LABELS[availability], clear: () => setFilter("avail", "all") });
        if (monitored !== "all") chips.push({ key: "mon", label: MONITOR_LABELS[monitored], clear: () => setFilter("mon", "all") });
        if (subFilter !== "all") chips.push({ key: "sub", label: SUB_LABELS[subFilter], clear: () => setFilter("sub", "all") });
        if (watchFilter !== "all") chips.push({ key: "watch", label: WATCH_LABELS[watchFilter], clear: () => setFilter("watch", "all") });
        return chips;
    }, [genre, quality, availability, monitored, subFilter, watchFilter, setFilter]);

    /* ── Filtres enregistrés ── */
    // Instantané des filtres de l'URL (recherche comprise) : c'est ce qu'un
    // préréglage enregistre, et ce qui permet de reconnaître celui qui est actif.
    const currentParams = useMemo(() => paramsFromSearch(params), [params]);

    /** Applique un préréglage : réécrit TOUTE l'URL de filtres et revient en page 1. */
    const applyPreset = (preset: FilterPreset) => {
        // Le champ de recherche suit l'URL (effet ci-dessus) ; on le cale tout
        // de suite pour éviter qu'une frappe en attente ne réécrive l'ancien texte.
        const q = preset.params.q ?? "";
        setSearchInput(q);
        lastSynced.current = q;
        writeParams(presetUpdates(preset.params));
    };

    const resetFilters = () =>
        writeParams({ genre: null, quality: null, avail: null, mon: null, sub: null, watch: null, page: null });

    const resetEverything = () => {
        setSearchInput("");
        lastSynced.current = "";
        writeParams({
            q: null,
            search: null,
            type: null,
            genre: null,
            quality: null,
            avail: null,
            mon: null,
            sub: null,
            watch: null,
            page: null,
        });
    };

    /** Changement de page : on remonte en haut pour voir la nouvelle grille. */
    const goToPage = (p: number) => {
        setPage(p);
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    /** Tri : « Date d'ajout » et « Taille » sont plus utiles du plus grand au plus petit. */
    const changeSort = (next: Sort) =>
        writeParams({
            sort: next === "title" ? null : next,
            order: next === "added" || next === "size_bytes" ? "desc" : null,
            page: null,
        });

    /* ── Sélection multiple ── */
    const [selectMode, setSelectMode] = useState(false);
    // Map clé → média : la sélection survit au changement de page et on
    // garde l'objet complet (type + id) pour agir dessus ensuite.
    const [selected, setSelected] = useState<Map<string, MediaItem>>(() => new Map());

    const exitSelection = useCallback(() => {
        setSelectMode(false);
        setSelected(new Map());
    }, []);

    // Échap = quitter le mode sélection (sauf si Échap sert à fermer une
    // boîte de dialogue ou une liste déroulante ouverte).
    useEffect(() => {
        if (!selectMode) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key !== "Escape") return;
            if (document.querySelector("[role='dialog'], [data-radix-popper-content-wrapper]")) return;
            exitSelection();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [selectMode, exitSelection]);

    const toggleItem = (item: MediaItem) =>
        setSelected((prev) => {
            const next = new Map(prev);
            const k = mediaKey(item);
            if (next.has(k)) next.delete(k);
            else next.set(k, item);
            return next;
        });

    const allPageSelected = visibleItems.length > 0 && visibleItems.every((i) => selected.has(mediaKey(i)));
    const toggleAllPage = () =>
        setSelected((prev) => {
            const next = new Map(prev);
            if (allPageSelected) visibleItems.forEach((i) => next.delete(mediaKey(i)));
            else visibleItems.forEach((i) => next.set(mediaKey(i), i));
            return next;
        });

    const selectedItems = useMemo(() => Array.from(selected.values()), [selected]);
    const selectedMovies = selectedItems.filter((i) => i.type === "movie");

    /* ── Actions ── */
    const kodiSync = useKodiSync();
    // Sans TV (module désactivé), les entrées Kodi du menu disparaissent
    const hasTv = useModuleEnabled()("tv");
    const syncKodi = () => {
        toast.promise(kodiSync.mutateAsync(), {
            loading: "Synchronisation de Kodi…",
            success: (r) =>
                r && typeof r.success === "number"
                    ? `Kodi synchronisé — ${plural(r.success, "instance")} OK${r.failed ? `, ${r.failed} en échec` : ""}`
                    : "Synchronisation Kodi lancée",
            error: (e: Error) => `Synchro Kodi impossible : ${e.message}`,
        });
    };

    /**
     * Scraper : génère NFO + artworks pour Kodi. Le backend ne gère que
     * Radarr → on n'envoie que les films (les séries sont ignorées).
     */
    const scrape = (items: MediaItem[]) => {
        const movies = items.filter((i) => i.type === "movie");
        if (movies.length === 0) {
            toast.warning("Aucun film à scraper", { description: "Le scraper ne gère que les films (Radarr)." });
            return;
        }
        const skipped = items.length - movies.length;
        toast.promise(
            apiFetch("/api/media/scrape", {
                method: "POST",
                body: JSON.stringify({
                    items: movies.map((i) => ({ movie_id: i.external_id, tmdb_id: i.tmdb_id, source_service: i.source_service })),
                }),
            }),
            {
                loading: "Envoi au scraper…",
                success: `Scraping lancé pour ${plural(movies.length, "film")}${skipped ? ` (${plural(skipped, "série ignorée", "séries ignorées")})` : ""} — NFO et artworks générés en arrière-plan`,
                error: (e: Error) => `Scraping impossible : ${e.message}`,
            },
        );
    };

    const [deleteOpen, setDeleteOpen] = useState(false);
    const [deleteFiles, setDeleteFiles] = useState(true);
    const [deleteDownloads, setDeleteDownloads] = useState(true);

    /**
     * Suppression groupée : toutes les requêtes partent en parallèle et on
     * attend TOUS les résultats (allSettled) — avant, un seul échec masquait
     * les autres succès. Les médias en échec restent sélectionnés.
     */
    const handleBulkDelete = async () => {
        const items = selectedItems;
        if (items.length === 0) return;
        const results = await Promise.allSettled(
            items.map((item) =>
                apiFetch(
                    `/api/media/${item.type}/${item.external_id}?delete_files=${deleteFiles}&delete_downloads=${deleteDownloads}`,
                    { method: "DELETE" },
                ),
            ),
        );
        const failed = items.filter((_, i) => results[i].status === "rejected");
        const ok = items.length - failed.length;
        queryClient.invalidateQueries({ queryKey: ["media"] });

        if (failed.length === 0) {
            toast.success(`${plural(ok, "média supprimé", "médias supprimés")}`, {
                description: deleteFiles ? "Fichiers effacés du disque." : "Fichiers conservés sur le disque.",
            });
            exitSelection();
            return;
        }
        const firstError = results.find((r): r is PromiseRejectedResult => r.status === "rejected")?.reason;
        const names = failed.slice(0, 3).map((i) => i.title).join(", ") + (failed.length > 3 ? "…" : "");
        if (ok === 0) {
            toast.error(`Aucune suppression n'a abouti`, {
                description: firstError instanceof Error ? firstError.message : names,
            });
        } else {
            toast.warning(`${plural(ok, "média supprimé", "médias supprimés")}, ${failed.length} en échec`, {
                description: `Toujours sélectionnés : ${names}`,
            });
        }
        setSelected(new Map(failed.map((i) => [mediaKey(i), i])));
    };

    const pageMovies = (data?.items ?? []).filter((i) => i.type === "movie");
    const hasServerFilters = genre !== "all" || quality !== "all" || availability !== "all" || monitored !== "all";
    const hasClientFilters = subFilter !== "all" || watchFilter !== "all";
    const filterCount = activeChips.length;

    // Clé de la grille : change quand les éléments affichés changent → on
    // rejoue l'animation d'entrée (et pas pendant l'affichage provisoire).
    const gridKey = `${data?.pagination.page ?? 0}:${visibleItems.length}:${visibleItems[0] ? mediaKey(visibleItems[0]) : ""}:${
        visibleItems.length ? mediaKey(visibleItems[visibleItems.length - 1]) : ""
    }:${view}`;

    /* ── Rendu ── */
    return (
        <>
            <PageContainer>
                <PageHeader
                    title="Médiathèque"
                    actions={
                        <div className="flex items-center gap-1">
                            {/* Mode sélection, comme « Sélectionner » de l'app Photos */}
                            <Button variant="ghost" className="text-primary" onClick={() => (selectMode ? exitSelection() : setSelectMode(true))} aria-pressed={selectMode}>
                                {selectMode ? "Terminé" : "Sélectionner"}
                            </Button>
                            {/* Logos, disques, clearart (fanart.tv / TMDB, côté serveur) */}
                            <ArtworkRefreshButton />
                            <Button asChild size="icon" variant="tinted" aria-label="Ajouter un titre">
                                <Link href="/search">
                                    <Plus className="!size-5" />
                                </Link>
                            </Button>
                        </div>
                    }
                />

                {/* Radarr / Sonarr injoignable : dernière liste connue affichée */}
                <LibrarySourcesBanner />

                {/* Séries maison (Naruto Kai…) : hors Sonarr, leur propre rangée */}
                {type !== "movie" && <LocalSeriesRow />}

                {/* ── Barre d'outils : recherche, type, filtres, tri, vue ── */}
                <StickyToolbar>
                    <SearchField
                        value={searchInput}
                        onChange={setSearchInput}
                        // Spinner pendant la frappe (debounce) puis pendant la requête.
                        loading={searchInput.trim() !== urlQuery || (!!urlQuery && isFetching && isPlaceholderData)}
                        placeholder="Rechercher dans ta médiathèque"
                        ariaLabel="Rechercher un titre dans la médiathèque"
                        id="media-search"
                    />
                    <div className="mt-2.5 flex items-center gap-2">
                        <SegmentedControl
                            className="min-w-0"
                            layoutId="media-type-pill"
                            ariaLabel="Type de média"
                            value={type}
                            onChange={(v) => setFilter("type", v)}
                            options={[
                                { value: "all", label: "Tout" },
                                { value: "movie", label: "Films", count: movieCount ?? null },
                                { value: "series", label: "Séries", count: seriesCount ?? null },
                            ]}
                        />
                        <div className="flex-1" />
                        <Button
                            variant={filterCount > 0 ? "tinted" : "secondary"}
                            size="sm"
                            onClick={() => setShowFilters(true)}
                            aria-label="Filtres"
                            className="shrink-0"
                        >
                            <SlidersHorizontal />
                            <span className="hidden sm:inline">Filtres</span>
                            {filterCount > 0 && <span className="tabular-nums">{filterCount}</span>}
                        </Button>
                        <FilterPresetsMenu current={currentParams} onApply={applyPreset} className="hidden h-8 rounded-lg px-3 text-[13px] md:inline-flex" />
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="secondary" size="icon-sm" aria-label="Tri, affichage et actions" className="shrink-0">
                                    <MoreHorizontal />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-64">
                                <DropdownMenuLabel className="text-[12px] font-medium text-muted-foreground">Trier par</DropdownMenuLabel>
                                {MEDIA_SORTS.map((s) => (
                                    <DropdownMenuItem key={s} onSelect={() => changeSort(s)}>
                                        <Check className={cn(sort !== s && "opacity-0")} />
                                        {SORT_LABELS[s]}
                                    </DropdownMenuItem>
                                ))}
                                <DropdownMenuItem onSelect={() => setFilter("order", order === "asc" ? "desc" : "asc", "asc")}>
                                    {order === "asc" ? <ArrowUpNarrowWide /> : <ArrowDownWideNarrow />}
                                    {order === "asc" ? "Ordre croissant" : "Ordre décroissant"}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuLabel className="text-[12px] font-medium text-muted-foreground">Affichage</DropdownMenuLabel>
                                <DropdownMenuItem onSelect={() => setView("grid")}>
                                    <LayoutGrid className={cn(view !== "grid" && "opacity-40")} />
                                    Grille
                                    {view === "grid" && <Check className="ml-auto" />}
                                </DropdownMenuItem>
                                <DropdownMenuItem onSelect={() => setView("list")}>
                                    <List className={cn(view !== "list" && "opacity-40")} />
                                    Liste
                                    {view === "list" && <Check className="ml-auto" />}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem asChild>
                                    <Link href="/media/missing">
                                        <PackageX />
                                        Manquants
                                        {facets?.missing_count ? <span className="ml-auto text-xs tabular-nums text-muted-foreground">{facets.missing_count}</span> : null}
                                    </Link>
                                </DropdownMenuItem>
                                {hasTv && (
                                    <DropdownMenuItem onSelect={syncKodi} disabled={kodiSync.isPending}>
                                        <RefreshCw className={cn(kodiSync.isPending && "animate-spin")} />
                                        Synchroniser Kodi
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onSelect={() => scrape(pageMovies)} disabled={pageMovies.length === 0}>
                                    <CloudDownload />
                                    Scraper la page
                                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{plural(pageMovies.length, "film")}</span>
                                </DropdownMenuItem>
                                {hasTv && (
                                    <DropdownMenuItem asChild>
                                        <Link href="/settings/kodi">
                                            <Settings />
                                            Réglages Kodi
                                        </Link>
                                    </DropdownMenuItem>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </StickyToolbar>

                {/* ── Filtres : feuille iOS (bas de l'écran sur mobile, fenêtre sur ordinateur) ── */}
                <Dialog open={showFilters} onOpenChange={setShowFilters}>
                    <DialogContent className="sm:max-w-xl">
                        <DialogHeader>
                            <DialogTitle>Filtres</DialogTitle>
                            <DialogDescription>
                                Disponibilité, genre, qualité et surveillance filtrent toute la bibliothèque ; ST&nbsp;FR et Lecture Kodi
                                s&apos;appliquent à la page affichée.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-3 sm:grid-cols-2">
                                    <FilterSelect
                                        id="f-avail"
                                        label="Disponibilité"
                                        value={availability}
                                        onChange={(v) => setFilter("avail", v)}
                                        choices={AVAIL_CHOICES}
                                    />
                                    <FilterSelect
                                        id="f-genre"
                                        label="Genre"
                                        value={genre}
                                        onChange={(v) => setFilter("genre", v)}
                                        choices={[{ value: "all", label: "Tous" }, ...(facets?.genres ?? []).map((g) => ({ value: g, label: translateGenre(g) }))]}
                                    />
                                    <FilterSelect
                                        id="f-quality"
                                        label="Qualité"
                                        value={quality}
                                        onChange={(v) => setFilter("quality", v)}
                                        choices={[{ value: "all", label: "Toutes" }, ...(facets?.qualities ?? []).map((q) => ({ value: q, label: q }))]}
                                    />
                                    <FilterSelect
                                        id="f-mon"
                                        label="Surveillance"
                                        value={monitored}
                                        onChange={(v) => setFilter("mon", v)}
                                        choices={MONITOR_CHOICES}
                                    />
                                    <FilterSelect
                                        id="f-sub"
                                        label="Sous-titres FR"
                                        value={subFilter}
                                        onChange={(v) => setFilter("sub", v)}
                                        choices={SUB_CHOICES}
                                        disabled={!subtitlesAvailable}
                                        hint={subtitlesAvailable ? undefined : "Bazarr non configuré"}
                                    />
                                    <FilterSelect
                                        id="f-watch"
                                        label="Lecture Kodi"
                                        value={watchFilter}
                                        onChange={(v) => setFilter("watch", v)}
                                        choices={WATCH_CHOICES}
                                        disabled={!kodiAvailable}
                                        hint={kodiAvailable ? undefined : "Aucune TV n'a encore partagé son vu"}
                                    />
                                </div>
                        <DialogFooter>
                            <Button variant="secondary" onClick={resetFilters} disabled={filterCount === 0}>
                                Réinitialiser
                            </Button>
                            <Button onClick={() => setShowFilters(false)}>Terminé</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* ── Chips des filtres actifs ── */}
                <AnimatePresence initial={false}>
                    {filterCount > 0 && (
                        <motion.div
                            key="chips"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.3, ease: EASE_OUT }}
                            className="-mt-2 overflow-hidden"
                        >
                            <div className="flex flex-wrap items-center gap-2 pt-1">
                                <AnimatePresence>
                                    {activeChips.map((chip) => (
                                        <RemovableChip key={chip.key} label={chip.label} onRemove={chip.clear} />
                                    ))}
                                </AnimatePresence>
                                <Button variant="ghost" size="sm" onClick={resetFilters} className="text-primary">
                                    Tout effacer
                                </Button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* ── Résumé ── */}
                {data && !isError && (
                    <div className="-mb-3 flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted-foreground">
                        <p>
                            <span className="font-semibold tabular-nums text-foreground">{formatNumber(total)}</span>{" "}
                            {total > 1 ? "résultats" : "résultat"}
                            {urlQuery && (
                                <>
                                    {" "}
                                    pour <span className="text-foreground">« {urlQuery} »</span>
                                </>
                            )}
                            {totalPages > 1 && (
                                <span className="tabular-nums">
                                    {" "}
                                    · page {page} / {totalPages}
                                </span>
                            )}
                            {hasClientFilters && data.items.length > 0 && (
                                <span className="text-primary/90">
                                    {" "}
                                    · {visibleItems.length} sur {data.items.length} affichés (filtre de page)
                                </span>
                            )}
                        </p>
                        <AnimatePresence>
                            {isFetching && !isLoading && (
                                <motion.span
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="flex items-center gap-1.5"
                                >
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Mise à jour…
                                </motion.span>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* ── Contenu ── */}
                {isError ? (
                    <div className="rounded-2xl bg-card">
                        <ErrorState error={error} onRetry={() => refetch()} title="Impossible de charger la médiathèque" />
                    </div>
                ) : isLoading ? (
                    view === "list" ? (
                        <div className="space-y-px overflow-hidden rounded-xl">
                            {Array.from({ length: 10 }).map((_, i) => (
                                <Shimmer key={i} className="h-[72px] w-full rounded-none" />
                            ))}
                        </div>
                    ) : (
                        <PosterGridSkeleton count={16} />
                    )
                ) : total === 0 ? (
                    <div className="rounded-2xl bg-card">
                        {urlQuery ? (
                            <EmptyState
                                icon={Search}
                                title={`Aucun résultat pour « ${urlQuery} »`}
                                description="Ce titre n'est pas (encore) dans ta médiathèque. Tu peux le chercher pour l'ajouter."
                                action={{ label: `Chercher « ${urlQuery} » pour l'ajouter`, href: `/search?q=${encodeURIComponent(urlQuery)}` }}
                            />
                        ) : hasServerFilters || type !== "all" ? (
                            <EmptyState
                                icon={SlidersHorizontal}
                                title="Aucun média ne correspond"
                                description="Aucun titre de ta bibliothèque ne coche tous ces critères."
                                action={{ label: "Réinitialiser les filtres", onClick: resetEverything }}
                            />
                        ) : downSources.length ? (
                            <EmptyState
                                icon={Library}
                                title={`${downSources.map((source) => source.name).join(" et ")} ${
                                    downSources.length > 1 ? "ne répondent pas" : "ne répond pas"
                                }`}
                                description="Ta médiathèque n'est pas vide : ArrMada n'arrive pas à la lire et n'en a encore aucune copie. Il réessaie toutes les 30\u00a0s ; vérifie que le conteneur tourne et que son port répond."
                                action={{ label: "Voir les services", href: "/settings/services" }}
                            />
                        ) : (
                            <EmptyState
                                icon={Library}
                                title="Ta médiathèque est vide"
                                description="Connecte Radarr et Sonarr pour voir apparaître tes films et séries ici."
                                action={{ label: "Configurer les services", href: "/settings/services" }}
                            />
                        )}
                    </div>
                ) : visibleItems.length === 0 ? (
                    <div className="rounded-2xl bg-card">
                        <EmptyState
                            compact
                            icon={SlidersHorizontal}
                            title="Rien sur cette page avec ces filtres"
                            description="Les filtres ST FR et Lecture Kodi ne s'appliquent qu'à la page affichée : essaie la page suivante ou retire-les."
                            action={
                                page < totalPages
                                    ? { label: "Page suivante", onClick: () => goToPage(page + 1) }
                                    : { label: "Retirer ces filtres", onClick: () => writeParams({ sub: null, watch: null }) }
                            }
                        />
                    </div>
                ) : view === "list" ? (
                    <div className={cn("overflow-hidden rounded-xl bg-card transition-opacity duration-300", isPlaceholderData && "opacity-60")}>
                        <MediaListHeader selectable={selectMode} />
                        <motion.div key={gridKey} variants={stagger(0, 0.012)} initial="hidden" animate="show" className="[&>*+*]:shadow-[inset_0_0.5px_0_hsl(0_0%_100%/0.1)]">
                            {visibleItems.map((item) => (
                                <MediaListRow
                                    key={mediaKey(item)}
                                    item={item}
                                    sub={subStateFor(item)}
                                    watch={watchStateFor(item)}
                                    selectable={selectMode}
                                    selected={selected.has(mediaKey(item))}
                                    onToggleSelect={() => toggleItem(item)}
                                />
                            ))}
                        </motion.div>
                    </div>
                ) : (
                    <motion.div
                        key={gridKey}
                        variants={stagger(0, 0.02)}
                        initial="hidden"
                        animate="show"
                        className={cn(GRID, "transition-opacity duration-300", isPlaceholderData && "opacity-60")}
                    >
                        {visibleItems.map((item) => (
                            <MediaPosterCard
                                key={mediaKey(item)}
                                item={item}
                                sub={subStateFor(item)}
                                watch={watchStateFor(item)}
                                selectable={selectMode}
                                selected={selected.has(mediaKey(item))}
                                onToggleSelect={() => toggleItem(item)}
                            />
                        ))}
                    </motion.div>
                )}

                {data && !isError && (
                    <SmartPagination page={page} totalPages={totalPages} onChange={goToPage} layoutId="media-page-pill" className="pt-2" />
                )}
            </PageContainer>

            {/* ── Barre de sélection flottante (hors des conteneurs animés) ── */}
            <FloatingBar open={selectMode}>
                <SelectionCount count={selected.size} />
                <Button variant="ghost" size="sm" onClick={toggleAllPage} disabled={visibleItems.length === 0}>
                    <CheckSquare />
                    <span className="sm:hidden">{allPageSelected ? "Aucun" : "Page"}</span>
                    <span className="hidden sm:inline">{allPageSelected ? "Désélectionner la page" : "Tout sélectionner (page)"}</span>
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => scrape(selectedMovies)}
                    disabled={selectedMovies.length === 0}
                    title="Génère NFO et artworks Kodi (films uniquement)"
                >
                    <CloudDownload />
                    Scraper
                    {selectedMovies.length > 0 && <span className="tabular-nums text-muted-foreground">({selectedMovies.length})</span>}
                </Button>
                <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)} disabled={selected.size === 0}>
                    <Trash2 />
                    Supprimer
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={exitSelection} aria-label="Quitter la sélection (Échap)">
                    <X />
                </Button>
            </FloatingBar>

            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                destructive
                title={`Supprimer ${plural(selected.size, "média")} ?`}
                description={`${selected.size > 1 ? "Ils seront retirés" : "Il sera retiré"} de Radarr / Sonarr. Cette action est irréversible.`}
                confirmLabel="Supprimer"
                onConfirm={handleBulkDelete}
            >
                <div className="space-y-3 rounded-xl bg-white/[0.05] p-3.5">
                    <div className="flex items-start justify-between gap-3">
                        <Label htmlFor="del-files" className="text-sm leading-snug">
                            Effacer aussi les fichiers du disque
                            <span className="block text-xs font-normal text-muted-foreground">Sinon, les fichiers restent dans ton dossier média.</span>
                        </Label>
                        <Switch id="del-files" checked={deleteFiles} onCheckedChange={setDeleteFiles} />
                    </div>
                    <div className="flex items-start justify-between gap-3">
                        <Label htmlFor="del-dl" className="text-sm leading-snug">
                            Retirer de la file et de l&apos;historique
                            <span className="block text-xs font-normal text-muted-foreground">SABnzbd, torrents… (téléchargements liés).</span>
                        </Label>
                        <Switch id="del-dl" checked={deleteDownloads} onCheckedChange={setDeleteDownloads} />
                    </div>
                </div>
                {selectedItems.length > 0 && (
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                        {selectedItems
                            .slice(0, 6)
                            .map((i) => i.title)
                            .join(" · ")}
                        {selectedItems.length > 6 && ` · +${selectedItems.length - 6}`}
                    </p>
                )}
            </ConfirmDialog>
        </>
    );
}
