"use client";

/**
 * Historique de l'auto-import (tâche périodique du backend qui tente
 * d'importer tout seul les téléchargements bloqués).
 * ----------------------------------------------------------------
 * Corrections : « 10 derniers runs » et « toutes les 5 minutes » étaient
 * écrits en dur → le nombre d'exécutions et la fréquence sont maintenant
 * déduits des rapports eux-mêmes ; un type « unknown » n'est plus affiché
 * comme « Série » ; clés React stables (plus de key={idx}) ; succès
 * étiqueté « Import lancé » (l'*arr traite la commande ensuite).
 * Le rafraîchissement 30 s ne tourne que tant que cette section est
 * affichée (le composant n'est monté que quand on l'ouvre).
 */
import { useMemo } from "react";
import { motion } from "framer-motion";
import { Activity, CheckCircle2, Film, HelpCircle, Rocket, ScanSearch, Timer, Tv, XCircle } from "lucide-react";
import { useAutoImportReports, type AutoImportReport, type AutoImportReportItem } from "@/hooks/use-files";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { RingGauge } from "@/components/fx/ring-gauge";
import { formatLongDateTime, parseApiDate, percent, plural, timeAgo } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

const TYPE_BADGE: Record<string, { label: string; icon: typeof Film; cls: string }> = {
    movie: { label: "Film", icon: Film, cls: "bg-primary/15 text-primary ring-primary/25" },
    series: { label: "Série", icon: Tv, cls: "bg-primary/15 text-primary ring-primary/25" },
};
const UNKNOWN_TYPE = { label: "Type inconnu", icon: HelpCircle, cls: "bg-white/[0.06] text-muted-foreground ring-white/[0.1]" };

/** Fréquence observée entre les exécutions (médiane, en minutes). */
function observedInterval(reports: AutoImportReport[]): number | null {
    const times = reports
        .map((r) => parseApiDate(r.timestamp)?.getTime())
        .filter((t): t is number => typeof t === "number")
        .sort((a, b) => a - b);
    if (times.length < 2) return null;
    const diffs = times.slice(1).map((t, i) => (t - times[i]) / 60_000).sort((a, b) => a - b);
    const median = diffs[Math.floor(diffs.length / 2)];
    return median > 0 ? Math.max(1, Math.round(median)) : null;
}

/** 5 → « environ toutes les 5 min », 120 → « … toutes les 2 h », 1440 → « environ une fois par jour ». */
function intervalLabel(minutes: number): string {
    if (minutes >= 1380 && minutes <= 1500) return "environ une fois par jour";
    if (minutes >= 90) return `environ toutes les ${Math.round(minutes / 60)} h`;
    return `environ toutes les ${minutes} min`;
}

export function AutoImportReports() {
    // live = true : ce composant n'est monté que lorsque la section est visible.
    const { data, isLoading, isError, error, refetch } = useAutoImportReports(true);

    // Le fichier de rapports est en ordre chronologique : on affiche le plus récent d'abord.
    const reports = useMemo(() => (data ?? []).slice().reverse(), [data]);
    const interval = useMemo(() => observedInterval(data ?? []), [data]);

    if (isLoading) {
        return (
            <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                    <Shimmer key={i} className="h-28 w-full rounded-2xl" />
                ))}
            </div>
        );
    }
    if (isError) {
        return (
            <SpotlightCard interactive={false}>
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de lire les rapports d'auto-import" />
            </SpotlightCard>
        );
    }
    if (reports.length === 0) {
        return (
            <SpotlightCard interactive={false}>
                <EmptyState
                    icon={Activity}
                    title="Aucun rapport d'auto-import"
                    description="La tâche d'auto-import n'a pas encore tourné. Elle s'exécute toute seule en arrière-plan et ses rapports apparaîtront ici."
                />
            </SpotlightCard>
        );
    }

    return (
        <div className="space-y-3">
            <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                <Activity className="h-3.5 w-3.5 text-success" />
                {reports.length > 1 ? `${reports.length} dernières exécutions` : "Dernière exécution"}
                {interval ? <span>· {intervalLabel(interval)}</span> : null}
                <span>· actualisé toutes les 30 s</span>
            </p>
            <motion.ol variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-3">
                {reports.map((r) => (
                    <motion.li key={r.timestamp} variants={fadeUp}>
                        <ReportCard report={r} />
                    </motion.li>
                ))}
            </motion.ol>
        </div>
    );
}

function ReportCard({ report }: { report: AutoImportReport }) {
    const date = parseApiDate(report.timestamp);
    const empty = report.scanned_count === 0;
    const hasErrors = report.failed_count > 0;
    const ratio = percent(report.imported_count, report.scanned_count);

    return (
        <SpotlightCard interactive={false} className="p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-4">
                <RingGauge value={empty ? 100 : ratio} size={52} stroke={5} tone={empty ? "brand" : hasErrors ? "amber" : "emerald"}>
                    {empty ? (
                        <CheckCircle2 className="h-4 w-4 text-brand" />
                    ) : (
                        <span className="text-[11px] font-bold tabular-nums">{Math.round(ratio)}%</span>
                    )}
                </RingGauge>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold first-letter:uppercase">{date ? formatLongDateTime(date) : report.timestamp}</p>
                    <p className="text-[11px] text-muted-foreground">
                        {date ? timeAgo(date) : ""} · durée {report.duration_seconds.toLocaleString("fr-FR")} s
                    </p>
                </div>
                <span
                    className={cn(
                        "rounded-md px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
                        empty
                            ? "bg-white/[0.05] text-muted-foreground ring-white/[0.08]"
                            : hasErrors
                              ? "bg-destructive/15 text-destructive ring-destructive/25"
                              : "bg-success/15 text-success ring-success/25",
                    )}
                >
                    {empty ? "Rien à importer" : hasErrors ? plural(report.failed_count, "échec") : "Tout est lancé"}
                </span>
            </div>

            {!empty && (
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                        <ScanSearch className="h-3 w-3" /> {plural(report.scanned_count, "élément analysé", "éléments analysés")}
                    </span>
                    <span className="inline-flex items-center gap-1 text-success">
                        <Rocket className="h-3 w-3" /> {plural(report.imported_count, "import lancé", "imports lancés")}
                    </span>
                    {hasErrors && (
                        <span className="inline-flex items-center gap-1 text-destructive">
                            <XCircle className="h-3 w-3" /> {plural(report.failed_count, "échec")}
                        </span>
                    )}
                    <span className="inline-flex items-center gap-1">
                        <Timer className="h-3 w-3" /> {report.duration_seconds.toLocaleString("fr-FR")} s
                    </span>
                </div>
            )}

            {report.items?.length > 0 && (
                <ul className="mt-3 space-y-1.5 border-l-2 border-white/[0.06] pl-3">
                    {report.items.map((it) => (
                        <ReportItemRow key={`${it.storage_path}|${it.name}`} item={it} />
                    ))}
                </ul>
            )}
        </SpotlightCard>
    );
}

function ReportItemRow({ item }: { item: AutoImportReportItem }) {
    const type = TYPE_BADGE[item.media_type] ?? UNKNOWN_TYPE;
    const ok = item.status === "success";
    return (
        <li className="rounded-xl border border-white/[0.05] bg-background/30 p-2.5 text-xs">
            <div className="flex items-start gap-2">
                <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-px text-[10px] font-semibold ring-1 ring-inset", type.cls)}>
                    <type.icon className="h-2.5 w-2.5" />
                    {type.label}
                </span>
                <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-foreground/90" title={item.name}>
                        {item.name}
                    </p>
                    <code className="block truncate font-mono text-[10px] text-muted-foreground" title={item.storage_path}>
                        {item.storage_path}
                    </code>
                </div>
                <span
                    className={cn(
                        "inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-px text-[10px] font-semibold",
                        ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive",
                    )}
                >
                    {ok ? <Rocket className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />}
                    {ok ? "Import lancé" : "Échec"}
                </span>
            </div>
            {!ok && item.message && (
                <p className="mt-1.5 rounded-lg border border-destructive/15 bg-destructive/[0.06] px-2 py-1 text-[10px] text-destructive">{item.message}</p>
            )}
        </li>
    );
}
