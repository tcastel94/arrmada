"use client";

/**
 * Table unique des indexers Prowlarr : état, statistiques ET actions sur
 * la même ligne (l'ancienne page affichait deux listes des mêmes
 * indexers, l'une pour gérer, l'autre pour les stats).
 * ----------------------------------------------------------------
 * - Tri par colonne (état, nom, requêtes, succès, récupérations, temps
 *   de réponse), filtre (tous / actifs / désactivés / à surveiller) et
 *   recherche par nom.
 * - Un indexer sans aucune requête affiche « — » (et non un faux 0 %
 *   rouge).
 * - Les messages d'erreur Prowlarr sont affichés sous le nom.
 * - Desktop : vraie grille en colonnes ; mobile : cartes empilées
 *   (le conteneur des stats passe en `lg:contents` pour se fondre dans
 *   la grille sur grand écran).
 */
import { forwardRef, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertTriangle,
    ArrowDown,
    ArrowUp,
    ArrowUpDown,
    CheckCircle2,
    FlaskConical,
    Globe,
    Loader2,
    Lock,
    LockOpen,
    Search,
    Trash2,
    XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { EmptyState } from "@/components/shared/empty-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
    useDeleteIndexer,
    useToggleIndexer,
    type IndexerStat,
    type IndexerStatusMessage,
    type ProwlarrIndexer,
} from "@/hooks/use-prowlarr";
import { useDebounce } from "@/hooks/use-debounce";
import { formatNumber } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Segmented } from "@/components/maintenance/segmented";

export type IndexerHealth = "error" | "warning" | "disabled" | "idle" | "ok";

export interface IndexerRow {
    key: string;
    id: number;
    name: string;
    source: string;
    protocol?: string;
    privacy?: string;
    enable: boolean;
    messages: IndexerStatusMessage[];
    stat?: IndexerStat;
    /** Statistiques d'un indexer qui n'existe plus dans Prowlarr. */
    orphan: boolean;
    health: IndexerHealth;
}

/** Résultat du dernier test d'un indexer (affiché sur sa ligne). */
export interface TestOutcome {
    ok: boolean;
    message?: string;
}

/** Ordre de gravité (tri « État » : les problèmes en premier). */
const HEALTH_ORDER: Record<IndexerHealth, number> = { error: 0, warning: 1, disabled: 2, idle: 3, ok: 4 };

const HEALTH_META: Record<IndexerHealth, { label: string; tone: string }> = {
    error: { label: "En erreur", tone: "error" },
    warning: { label: "Peu fiable", tone: "warning" },
    disabled: { label: "Désactivé", tone: "unknown" },
    idle: { label: "Inutilisé", tone: "unknown" },
    ok: { label: "Opérationnel", tone: "online" },
};

const PRIVACY: Record<string, { label: string; icon: typeof Lock }> = {
    private: { label: "Privé : inscription requise", icon: Lock },
    semiPrivate: { label: "Semi-privé : inscription libre", icon: LockOpen },
    public: { label: "Public : accès libre", icon: Globe },
};

/** Fusionne la liste des indexers et leurs statistiques (par instance + ID). */
export function buildRows(indexers: ProwlarrIndexer[], stats: IndexerStat[]): IndexerRow[] {
    const statByKey = new Map(stats.map((s) => [`${s.source}:${s.indexer_id}`, s]));
    const rows: IndexerRow[] = indexers.map((idx) => {
        const key = `${idx.source}:${idx.id}`;
        const stat = statByKey.get(key);
        statByKey.delete(key);
        return {
            key,
            id: idx.id,
            name: idx.name,
            source: idx.source,
            protocol: idx.protocol,
            privacy: idx.privacy,
            enable: idx.enable,
            messages: idx.status_messages ?? [],
            stat,
            orphan: false,
            health: computeHealth(idx.enable, idx.status_messages ?? [], stat),
        };
    });
    // Stats restantes = indexers supprimés depuis (Prowlarr garde l'historique).
    for (const [key, stat] of Array.from(statByKey.entries())) {
        rows.push({
            key,
            id: stat.indexer_id,
            name: stat.indexer_name,
            source: stat.source,
            enable: false,
            messages: [],
            stat,
            orphan: true,
            health: "disabled",
        });
    }
    return rows;
}

function computeHealth(enable: boolean, messages: IndexerStatusMessage[], stat?: IndexerStat): IndexerHealth {
    if (!enable) return "disabled";
    if (messages.length > 0) return "error";
    if (!stat || !stat.queries) return "idle";
    if (stat.success_rate !== null && stat.success_rate < 80) return "warning";
    return "ok";
}

type SortKey = "health" | "name" | "queries" | "success" | "grabs" | "response";
type Filter = "all" | "active" | "disabled" | "issues";

const SORT_LABELS: Record<SortKey, string> = {
    health: "État",
    name: "Nom",
    queries: "Requêtes",
    success: "Taux de succès",
    grabs: "Récupérations",
    response: "Temps de réponse",
};

function sortValue(row: IndexerRow, key: SortKey): number | string {
    switch (key) {
        case "health":
            return HEALTH_ORDER[row.health];
        case "name":
            return row.name.toLowerCase();
        case "queries":
            return row.stat?.queries ?? -1;
        case "success":
            return row.stat?.success_rate ?? -1;
        case "grabs":
            return row.stat?.grabs ?? -1;
        case "response":
            return row.stat?.avg_response_time || Number.MAX_SAFE_INTEGER;
    }
}

function formatMs(ms: number | undefined): string {
    if (!ms) return "—";
    return ms >= 1000 ? `${(ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} s` : `${Math.round(ms)} ms`;
}

const COLS = "lg:grid-cols-[minmax(0,2.4fr)_5.5rem_minmax(0,1.3fr)_6rem_minmax(0,1.3fr)_5rem_13rem]";

export function IndexerTable({
    rows,
    testing,
    outcomes,
    onTest,
    bulkRunning,
}: {
    rows: IndexerRow[];
    testing: Set<string>;
    outcomes: Record<string, TestOutcome | undefined>;
    onTest: (row: IndexerRow) => void;
    bulkRunning: boolean;
}) {
    const toggle = useToggleIndexer();
    const remove = useDeleteIndexer();
    const [search, setSearch] = useState("");
    const debounced = useDebounce(search, 200);
    const [filter, setFilter] = useState<Filter>("all");
    const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "health", dir: 1 });
    const [toggling, setToggling] = useState<Set<string>>(new Set());
    const [toDelete, setToDelete] = useState<IndexerRow | null>(null);
    const [deleteOpen, setDeleteOpen] = useState(false);

    const counts = useMemo(
        () => ({
            all: rows.length,
            active: rows.filter((r) => r.enable).length,
            disabled: rows.filter((r) => !r.enable).length,
            issues: rows.filter((r) => r.health === "error" || r.health === "warning").length,
        }),
        [rows],
    );

    const visible = useMemo(() => {
        const q = debounced.trim().toLowerCase();
        return rows
            .filter((r) => {
                if (filter === "active" && !r.enable) return false;
                if (filter === "disabled" && r.enable) return false;
                if (filter === "issues" && r.health !== "error" && r.health !== "warning") return false;
                return !q || r.name.toLowerCase().includes(q);
            })
            .sort((a, b) => {
                const va = sortValue(a, sort.key);
                const vb = sortValue(b, sort.key);
                const cmp = typeof va === "string" ? va.localeCompare(vb as string, "fr") : (va as number) - (vb as number);
                // Départage stable par nom.
                return cmp * sort.dir || a.name.localeCompare(b.name, "fr");
            });
    }, [rows, debounced, filter, sort]);

    const setSortKey = (key: SortKey) =>
        setSort((s) =>
            s.key === key
                ? { key, dir: (s.dir * -1) as 1 | -1 }
                : // Nom et état : ordre croissant d'abord ; chiffres : plus grand d'abord.
                  { key, dir: key === "name" || key === "health" || key === "response" ? 1 : -1 },
        );

    const handleToggle = (row: IndexerRow) => {
        setToggling((s) => new Set(s).add(row.key));
        toggle.mutate(
            { id: row.id, enable: !row.enable },
            {
                onSuccess: (res) => toast.success(`« ${row.name} » ${res.enable ? "activé" : "désactivé"}`),
                onError: (e) => toast.error(`Impossible de modifier « ${row.name} »`, { description: e.message }),
                onSettled: () =>
                    setToggling((s) => {
                        const next = new Set(s);
                        next.delete(row.key);
                        return next;
                    }),
            },
        );
    };

    const confirmDelete = async () => {
        if (!toDelete) return;
        try {
            await remove.mutateAsync({ id: toDelete.id });
            toast.success(`« ${toDelete.name} » supprimé de Prowlarr`);
        } catch (e) {
            toast.error("Suppression impossible", { description: e instanceof Error ? e.message : undefined });
            throw e;
        }
    };

    return (
        <div>
            {/* Barre d'outils */}
            <div className="flex flex-col gap-3 border-b border-white/[0.05] px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-5">
                <Segmented<Filter>
                    layoutId="indexer-filter"
                    size="sm"
                    ariaLabel="Filtrer les indexers"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: "all", label: "Tous", count: counts.all },
                        { value: "active", label: "Actifs", count: counts.active },
                        { value: "disabled", label: "Désactivés", count: counts.disabled },
                        { value: "issues", label: "À surveiller", count: counts.issues, icon: AlertTriangle, iconClassName: "text-amber-400" },
                    ]}
                />
                <div className="flex gap-2">
                    <div className="relative flex-1 lg:w-56 lg:flex-none">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Chercher un indexer…"
                            aria-label="Chercher un indexer"
                            className="h-8 pl-8 text-xs"
                        />
                    </div>
                    {/* Tri sur mobile (les en-têtes de colonnes ne sont visibles que sur grand écran) */}
                    <Select value={sort.key} onValueChange={(v) => setSortKey(v as SortKey)}>
                        <SelectTrigger className="h-8 w-36 text-xs lg:hidden" aria-label="Trier par">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                                <SelectItem key={k} value={k}>
                                    {SORT_LABELS[k]}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* En-têtes de colonnes (desktop) */}
            <div className={cn("hidden gap-4 border-b border-white/[0.05] px-5 py-2 text-[11px] font-medium text-muted-foreground lg:grid", COLS)}>
                <SortHeader label="Indexer" k="name" sort={sort} onSort={setSortKey} />
                <SortHeader label="Requêtes" k="queries" sort={sort} onSort={setSortKey} align="right" />
                <SortHeader label="Succès" k="success" sort={sort} onSort={setSortKey} />
                <SortHeader label="Récup." k="grabs" sort={sort} onSort={setSortKey} align="right" title="Releases envoyées au client de téléchargement" />
                <span>Taux de récup.</span>
                <SortHeader label="Réponse" k="response" sort={sort} onSort={setSortKey} align="right" />
                <SortHeader label="État · actions" k="health" sort={sort} onSort={setSortKey} align="right" />
            </div>

            {visible.length === 0 ? (
                <EmptyState compact icon={Search} title="Aucun indexer" description="Aucun indexer ne correspond à ces critères." />
            ) : (
                <ul className="divide-y divide-white/[0.04]">
                    <AnimatePresence initial={false} mode="popLayout">
                        {visible.map((row, i) => (
                            <IndexerLine
                                key={row.key}
                                row={row}
                                index={i}
                                testing={testing.has(row.key)}
                                outcome={outcomes[row.key]}
                                toggling={toggling.has(row.key)}
                                locked={bulkRunning}
                                onTest={() => onTest(row)}
                                onToggle={() => handleToggle(row)}
                                onDelete={() => {
                                    setToDelete(row);
                                    setDeleteOpen(true);
                                }}
                            />
                        ))}
                    </AnimatePresence>
                </ul>
            )}

            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                destructive
                title={`Supprimer « ${toDelete?.name ?? ""} » ?`}
                description="L'indexer sera définitivement retiré de Prowlarr (et donc de Sonarr/Radarr après synchronisation). Cette action est irréversible."
                confirmLabel="Supprimer"
                onConfirm={confirmDelete}
            />
        </div>
    );
}

function SortHeader({
    label,
    k,
    sort,
    onSort,
    align,
    title,
}: {
    label: string;
    k: SortKey;
    sort: { key: SortKey; dir: 1 | -1 };
    onSort: (k: SortKey) => void;
    align?: "right";
    title?: string;
}) {
    const active = sort.key === k;
    const Icon = !active ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
    return (
        <button
            type="button"
            title={title}
            onClick={() => onSort(k)}
            aria-label={`Trier par ${label.toLowerCase()}${active ? (sort.dir === 1 ? " (croissant)" : " (décroissant)") : ""}`}
            className={cn(
                "flex items-center gap-1 transition-colors hover:text-foreground",
                align === "right" && "justify-end",
                active && "text-foreground",
            )}
        >
            {label}
            <Icon className={cn("h-3 w-3", !active && "opacity-40")} />
        </button>
    );
}

/** Pourcentage + mini barre ; « — » s'il n'y a rien à mesurer. */
function RateCell({ rate, emptyLabel }: { rate: number | null | undefined; emptyLabel: string }) {
    if (rate === null || rate === undefined) {
        return <span className="text-xs text-muted-foreground">— <span className="text-[10px]">{emptyLabel}</span></span>;
    }
    const tone = rate >= 90 ? "emerald" : rate >= 70 ? "amber" : "rose";
    const text = rate >= 90 ? "text-emerald-300" : rate >= 70 ? "text-amber-300" : "text-rose-300";
    return (
        <div className="flex items-center gap-2">
            <span className={cn("w-12 shrink-0 text-xs font-semibold tabular-nums", text)}>
                {rate.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %
            </span>
            {/* Barre masquée sur petit écran : les cartes restent compactes. */}
            <GradientProgress value={rate} tone={tone} glow={false} className="hidden h-1 sm:block" />
        </div>
    );
}

/** Libellé de cellule visible seulement sur mobile (les en-têtes desktop le remplacent). */
function CellLabel({ children }: { children: string }) {
    return <span className="mb-0.5 block text-[10px] uppercase tracking-wide text-muted-foreground/70 lg:hidden">{children}</span>;
}

interface IndexerLineProps {
    row: IndexerRow;
    index: number;
    testing: boolean;
    outcome?: TestOutcome;
    toggling: boolean;
    locked: boolean;
    onTest: () => void;
    onToggle: () => void;
    onDelete: () => void;
}

/** `forwardRef` : requis par AnimatePresence mode="popLayout" (mesure de la ligne sortante). */
const IndexerLine = forwardRef<HTMLLIElement, IndexerLineProps>(function IndexerLine(
    { row, index, testing, outcome, toggling, locked, onTest, onToggle, onDelete },
    ref,
) {
    const { stat } = row;
    const privacy = row.privacy ? PRIVACY[row.privacy] : undefined;
    const health = HEALTH_META[row.health];
    const errorText = row.messages
        .map((m) => m.message || m.title)
        .filter(Boolean)
        .join(" · ");

    return (
        <motion.li
            ref={ref}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.35, ease: EASE_OUT, delay: Math.min(index, 15) * 0.025 }}
            className={cn("grid gap-3 px-4 py-3.5 transition-colors hover:bg-white/[0.02] lg:items-center lg:gap-4 lg:px-5", COLS, !row.enable && "opacity-70")}
        >
            {/* Nom + infos */}
            <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                    <StatusDot tone={health.tone} pulse={row.health === "error" ? true : undefined} />
                    <span className="truncate text-sm font-semibold">{row.name}</span>
                    {row.protocol && (
                        <span
                            className={cn(
                                "shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
                                row.protocol === "usenet" ? "bg-amber-500/15 text-amber-300" : "bg-sky-500/15 text-sky-300",
                            )}
                        >
                            {row.protocol === "usenet" ? "Usenet" : row.protocol === "torrent" ? "Torrent" : row.protocol}
                        </span>
                    )}
                    {privacy && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <span tabIndex={0} className="shrink-0 text-muted-foreground" aria-label={privacy.label}>
                                    <privacy.icon className="h-3 w-3" />
                                </span>
                            </TooltipTrigger>
                            <TooltipContent className="text-xs">{privacy.label}</TooltipContent>
                        </Tooltip>
                    )}
                </div>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {health.label}
                    {row.orphan ? " · n'existe plus dans Prowlarr" : ""} · {row.source}
                </p>
                {errorText && (
                    <p className="mt-1 line-clamp-2 text-[11px] text-red-300" title={errorText}>
                        <AlertTriangle className="mr-1 inline h-3 w-3" />
                        {errorText}
                    </p>
                )}
                {outcome && (
                    <p className={cn("mt-1 flex items-start gap-1 text-[11px]", outcome.ok ? "text-emerald-300" : "text-red-300")}>
                        {outcome.ok ? <CheckCircle2 className="mt-px h-3 w-3 shrink-0" /> : <XCircle className="mt-px h-3 w-3 shrink-0" />}
                        <span className="line-clamp-2">{outcome.ok ? "Test réussi" : `Test échoué : ${outcome.message ?? "erreur inconnue"}`}</span>
                    </p>
                )}
            </div>

            {/* Statistiques : grille 2×2 / 4 colonnes sur mobile, colonnes de la table sur desktop */}
            <div className="grid grid-cols-3 gap-x-3 gap-y-2.5 rounded-xl bg-white/[0.02] p-3 sm:grid-cols-5 lg:contents">
                <div className="lg:text-right">
                    <CellLabel>Requêtes</CellLabel>
                    <span className="text-sm tabular-nums">{stat ? formatNumber(stat.queries) : "—"}</span>
                    {stat && stat.failed_queries > 0 && (
                        <span className="block text-[10px] text-muted-foreground">{formatNumber(stat.failed_queries)} en échec</span>
                    )}
                </div>
                <div>
                    <CellLabel>Succès</CellLabel>
                    <RateCell rate={stat?.queries ? stat.success_rate : null} emptyLabel="aucune requête" />
                </div>
                <div className="lg:text-right">
                    <CellLabel>Récupérations</CellLabel>
                    <span className="text-sm tabular-nums">{stat ? formatNumber(stat.grabs) : "—"}</span>
                </div>
                <div>
                    <CellLabel>Taux de récup.</CellLabel>
                    <RateCell rate={stat?.grabs ? stat.grab_rate : null} emptyLabel="aucune" />
                </div>
                <div className="lg:text-right">
                    <CellLabel>Réponse</CellLabel>
                    <span className="text-sm tabular-nums text-muted-foreground">{formatMs(stat?.avg_response_time)}</span>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-1.5">
                {!row.orphan && (
                    <>
                        <Button variant="outline" size="sm" disabled={testing || locked} onClick={onTest} aria-label={`Tester ${row.name}`}>
                            {testing ? <Loader2 className="animate-spin" /> : <FlaskConical />}
                            Tester
                        </Button>
                        <Switch
                            checked={row.enable}
                            disabled={toggling || locked}
                            onCheckedChange={onToggle}
                            aria-label={row.enable ? `Désactiver ${row.name}` : `Activer ${row.name}`}
                        />
                        <Button
                            variant="ghost"
                            size="icon-sm"
                            disabled={locked}
                            onClick={onDelete}
                            aria-label={`Supprimer ${row.name}`}
                            className="text-red-400 hover:bg-red-500/10 hover:text-red-300"
                        >
                            <Trash2 />
                        </Button>
                    </>
                )}
            </div>
        </motion.li>
    );
});
