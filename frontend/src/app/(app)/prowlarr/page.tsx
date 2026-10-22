"use client";

/**
 * Indexers (/prowlarr) : santé et performances des indexers Prowlarr.
 * ----------------------------------------------------------------
 * - Héros : indexers actifs, requêtes, récupérations, taux de succès
 *   global et nombre d'indexers à surveiller.
 * - Encart « À surveiller » : indexers en erreur (message Prowlarr
 *   affiché) ou peu fiables (< 80 % de succès) — `summary.problematic`
 *   n'était jamais affiché.
 * - Une seule table avec stats + actions ; « Tester tout » teste les
 *   indexers actifs un par un, puis les stats sont relues.
 */
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Download, FlaskConical, Loader2, Radar, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { useProwlarrStats, useTestIndexer, type IndexerTestResult } from "@/hooks/use-prowlarr";
import { plural } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { IndexerTable, buildRows, type IndexerRow, type TestOutcome } from "@/components/prowlarr/indexer-table";

/** Message lisible d'un test échoué (Prowlarr renvoie une liste d'erreurs de validation). */
function testErrorMessage(res: IndexerTestResult): string {
    if (Array.isArray(res.errors)) {
        const msgs = res.errors.map((e) => e.errorMessage).filter(Boolean);
        if (msgs.length) return msgs.join(" · ");
    }
    if (typeof res.errors === "string" && res.errors.trim()) return res.errors.slice(0, 200);
    return `HTTP ${res.status_code}`;
}

export default function ProwlarrPage() {
    const { data, isLoading, isError, error, refetch, isFetching } = useProwlarrStats();
    const testIndexer = useTestIndexer();
    const [testing, setTesting] = useState<Set<string>>(new Set());
    const [outcomes, setOutcomes] = useState<Record<string, TestOutcome | undefined>>({});
    const [bulkRunning, setBulkRunning] = useState(false);

    const rows = useMemo(() => (data ? buildRows(data.indexers, data.stats) : []), [data]);
    const watchlist = useMemo(() => rows.filter((r) => r.health === "error" || r.health === "warning"), [rows]);

    /** Teste un indexer ; renvoie true si OK. `silent` = pas de toast (test groupé). */
    const runTest = async (row: IndexerRow, silent = false): Promise<boolean> => {
        setTesting((s) => new Set(s).add(row.key));
        try {
            const res = await testIndexer.mutateAsync({ id: row.id, skipRefresh: silent });
            const outcome: TestOutcome = res.ok ? { ok: true } : { ok: false, message: testErrorMessage(res) };
            setOutcomes((o) => ({ ...o, [row.key]: outcome }));
            if (!silent) {
                if (res.ok) toast.success(`« ${row.name} » répond correctement`);
                else toast.error(`« ${row.name} » : test échoué`, { description: outcome.message });
            }
            return res.ok;
        } catch (e) {
            const message = e instanceof Error ? e.message : "erreur inconnue";
            setOutcomes((o) => ({ ...o, [row.key]: { ok: false, message } }));
            if (!silent) toast.error(`« ${row.name} » : test impossible`, { description: message });
            return false;
        } finally {
            setTesting((s) => {
                const next = new Set(s);
                next.delete(row.key);
                return next;
            });
        }
    };

    /** Teste tous les indexers actifs, un par un (Prowlarr n'aime pas les rafales). */
    const testAll = async () => {
        const targets = rows.filter((r) => r.enable && !r.orphan);
        if (targets.length === 0) return;
        setBulkRunning(true);
        const id = toast.loading(`Test 0/${targets.length}…`);
        let ok = 0;
        for (let i = 0; i < targets.length; i++) {
            toast.loading(`Test ${i + 1}/${targets.length} : ${targets[i].name}`, { id });
            if (await runTest(targets[i], true)) ok++;
        }
        setBulkRunning(false);
        refetch(); // une seule relecture des stats pour tout le lot
        const failed = targets.length - ok;
        if (failed === 0) toast.success(`Les ${targets.length} indexers actifs répondent`, { id });
        else toast.warning(`${ok}/${targets.length} indexers OK, ${plural(failed, "en échec")}`, { id, description: "Le détail est affiché sur chaque ligne." });
    };

    const summary = data?.summary;
    const rate = summary?.total_queries ? summary.average_success_rate : null;

    return (
        <>
            <Header title="Indexers" />
            <PageContainer>
                <PageHeader
                    icon={Radar}
                    accent="rose"
                    eyebrow="Maintenance"
                    title="Indexers"
                    description="Santé et performances de tes indexers Prowlarr, avec tests et activation en un clic."
                    actions={
                        <>
                            <Button variant="outline" onClick={() => refetch()} disabled={isFetching} aria-label="Actualiser les statistiques">
                                <RefreshCw className={cn(isFetching && "animate-spin")} />
                                <span className="hidden sm:inline">Actualiser</span>
                            </Button>
                            <Button onClick={testAll} disabled={bulkRunning || !rows.some((r) => r.enable)}>
                                {bulkRunning ? <Loader2 className="animate-spin" /> : <FlaskConical />}
                                Tester tout
                            </Button>
                        </>
                    }
                >
                    {summary && (
                        <>
                            <StatPill
                                icon={Radar}
                                label="indexers actifs"
                                value={
                                    <>
                                        <AnimatedNumber value={summary.enabled_indexers} />/{summary.total_indexers}
                                    </>
                                }
                                tone="primary"
                            />
                            <StatPill icon={Search} label="requêtes" value={<AnimatedNumber value={summary.total_queries} />} />
                            <StatPill icon={Download} label="récupérations" value={<AnimatedNumber value={summary.total_grabs} />} />
                            <StatPill
                                icon={CheckCircle2}
                                label="de succès"
                                value={rate === null ? "—" : <AnimatedNumber value={rate} decimals={1} suffix=" %" />}
                                tone={rate === null ? "default" : rate >= 90 ? "success" : rate >= 70 ? "warning" : "danger"}
                            />
                            {watchlist.length > 0 && (
                                <StatPill icon={AlertTriangle} label="à surveiller" value={watchlist.length} tone="warning" />
                            )}
                        </>
                    )}
                </PageHeader>

                {isLoading ? (
                    <div className="space-y-4">
                        <Shimmer className="h-24 w-full rounded-2xl" />
                        <div className="glass space-y-2 rounded-2xl p-4">
                            {Array.from({ length: 6 }).map((_, i) => (
                                <Shimmer key={i} className="h-16 w-full" />
                            ))}
                        </div>
                    </div>
                ) : isError || !data ? (
                    <Panel>
                        <ErrorState error={error} onRetry={() => refetch()} title="Statistiques Prowlarr indisponibles" />
                    </Panel>
                ) : rows.length === 0 ? (
                    <Panel>
                        <EmptyState
                            icon={Radar}
                            title="Aucun indexer"
                            description="Aucun indexer trouvé : vérifie que Prowlarr est ajouté dans les services et qu'il contient des indexers."
                            action={{ label: "Ouvrir les services", href: "/settings/services" }}
                        />
                    </Panel>
                ) : (
                    <motion.div variants={stagger(0, 0.08)} initial="hidden" animate="show" className="space-y-5">
                        {watchlist.length > 0 && (
                            <motion.div variants={fadeUp}>
                                <Panel title="À surveiller" icon={ShieldAlert} iconClassName="text-warning">
                                    <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                                        {watchlist.map((r) => {
                                            const msg = r.messages.map((m) => m.message || m.title).filter(Boolean).join(" · ");
                                            return (
                                                <li
                                                    key={r.key}
                                                    className={cn(
                                                        "flex items-start gap-2.5 rounded-xl p-3 ring-1",
                                                        r.health === "error" ? "bg-destructive/[0.07] ring-destructive/20" : "bg-warning/[0.07] ring-warning/20",
                                                    )}
                                                >
                                                    <StatusDot tone={r.health === "error" ? "error" : "warning"} className="mt-1.5" />
                                                    <div className="min-w-0">
                                                        <p className="truncate text-sm font-semibold">{r.name}</p>
                                                        <p className={cn("line-clamp-2 text-xs", r.health === "error" ? "text-destructive" : "text-warning")} title={msg}>
                                                            {r.health === "error"
                                                                ? msg || "Prowlarr signale une erreur"
                                                                : `${(r.stat?.success_rate ?? 0).toLocaleString("fr-FR")} % de requêtes réussies (${plural(r.stat?.failed_queries ?? 0, "échec")})`}
                                                        </p>
                                                    </div>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                </Panel>
                            </motion.div>
                        )}

                        <motion.div variants={fadeUp}>
                            <Panel
                                title="Tous les indexers"
                                icon={Radar}
                                iconClassName="text-rose-300"
                                bodyClassName="p-0"
                                action={<span className="text-xs text-muted-foreground tabular-nums">{plural(rows.length, "indexer")}</span>}
                            >
                                <IndexerTable
                                    rows={rows}
                                    testing={testing}
                                    outcomes={outcomes}
                                    onTest={(r) => runTest(r)}
                                    bulkRunning={bulkRunning}
                                />
                            </Panel>
                        </motion.div>
                    </motion.div>
                )}
            </PageContainer>
        </>
    );
}
