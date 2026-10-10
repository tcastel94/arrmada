"use client";

/**
 * Kit graphique de la page Statistiques.
 * ----------------------------------------------------------------
 * - Couleurs : uniquement les variables CSS --chart-1..5 (palette du
 *   design system), assignées dans un ordre FIXE. Une série unique prend
 *   toujours --chart-1. Films = violet (--chart-3), séries = bleu
 *   (--chart-1), comme partout ailleurs dans l'app.
 * - `ChartTooltip` : UNE seule info-bulle pour tous les graphes (l'ancien
 *   style était recopié 4 fois), valeur en gras d'abord, libellé ensuite,
 *   « Nombre » au lieu de « count ».
 * - `ChartPanel` : panneau avec bascule Graphique / Tableau — chaque
 *   graphe a son équivalent tableau (lisible sans survol, accessible).
 */
import { useState, type ReactNode } from "react";
import { BarChart3, Table2, type LucideIcon } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { cn } from "@/lib/utils";

/** Teintes de la palette graphes (ordre fixe, jamais recyclé au-delà de 5). */
export const CHART = {
    c1: "hsl(var(--chart-1))",
    c2: "hsl(var(--chart-2))",
    c3: "hsl(var(--chart-3))",
    c4: "hsl(var(--chart-4))",
    c5: "hsl(var(--chart-5))",
    other: "hsl(215 20% 55%)",
} as const;
export const CATEGORICAL = [CHART.c1, CHART.c2, CHART.c3, CHART.c4, CHART.c5];
export const MOVIE_COLOR = CHART.c3;
export const SERIES_COLOR = CHART.c1;

/** Style commun des axes : discret, sans trait, chiffres alignés. */
export const AXIS_TICK = { fill: "hsl(var(--muted-foreground))", fontSize: 11 } as const;
export const GRID_STROKE = "hsl(var(--border))";

interface TooltipEntry {
    value?: number | string | ReadonlyArray<number | string>;
    name?: string | number;
    color?: string;
    payload?: Record<string, unknown>;
}

/**
 * Contenu d'info-bulle recharts. Passé en élément (`content={<ChartTooltip />}`) :
 * recharts lui injecte `active`, `payload` et `label`.
 */
export function ChartTooltip({
    active,
    payload,
    label,
    valueLabel = "Nombre",
    formatValue = (v) => v.toLocaleString("fr-FR"),
    labelKey,
}: {
    active?: boolean;
    payload?: ReadonlyArray<TooltipEntry>;
    label?: string | number;
    valueLabel?: string;
    formatValue?: (v: number) => string;
    /** Clé de la donnée à utiliser comme titre (sinon `label`). */
    labelKey?: string;
}) {
    if (!active || !payload?.length) return null;
    const entry = payload[0];
    const title = labelKey ? String(entry.payload?.[labelKey] ?? label ?? "") : String(label ?? entry.name ?? "");
    const raw = Array.isArray(entry.value) ? entry.value[0] : entry.value;
    const num = typeof raw === "number" ? raw : Number(raw);
    return (
        <div className="glass-strong min-w-[8rem] rounded-xl px-3 py-2 text-xs">
            <p className="text-base font-bold tabular-nums">{Number.isFinite(num) ? formatValue(num) : String(raw ?? "—")}</p>
            <p className="flex items-center gap-1.5 text-muted-foreground">
                {/* Clé de série en trait court (pas de pavé plein) */}
                <span className="h-0.5 w-3 rounded-full" style={{ background: entry.color ?? CHART.c1 }} />
                {valueLabel} · <span className="text-foreground">{title}</span>
            </p>
        </div>
    );
}

export interface TableColumn<Row> {
    header: string;
    cell: (row: Row) => ReactNode;
    align?: "right";
}

/** Panneau graphique avec bascule vers un tableau équivalent. */
export function ChartPanel<Row>({
    title,
    icon,
    iconClassName,
    description,
    rows,
    columns,
    rowKey,
    children,
    className,
}: {
    title: string;
    icon: LucideIcon;
    iconClassName?: string;
    description?: ReactNode;
    rows: Row[];
    columns: TableColumn<Row>[];
    rowKey: (row: Row) => string;
    children: ReactNode;
    className?: string;
}) {
    const [view, setView] = useState<"chart" | "table">("chart");
    return (
        <Panel
            title={title}
            icon={icon}
            iconClassName={iconClassName}
            className={cn("h-full", className)}
            action={
                <div className="flex rounded-lg border border-white/[0.06] bg-background/40 p-0.5" role="group" aria-label="Affichage">
                    {(
                        [
                            ["chart", BarChart3, "Graphique"],
                            ["table", Table2, "Tableau"],
                        ] as const
                    ).map(([v, Icon, label]) => (
                        <button
                            key={v}
                            type="button"
                            onClick={() => setView(v)}
                            aria-pressed={view === v}
                            aria-label={label}
                            title={label}
                            className={cn(
                                "flex h-6 w-7 items-center justify-center rounded-md transition-colors",
                                view === v ? "bg-white/[0.1] text-foreground" : "text-muted-foreground hover:text-foreground",
                            )}
                        >
                            <Icon className="h-3.5 w-3.5" />
                        </button>
                    ))}
                </div>
            }
        >
            {description && <p className="-mt-1 mb-3 text-xs text-muted-foreground">{description}</p>}
            {view === "chart" ? (
                children
            ) : (
                <div className="max-h-[320px] overflow-auto rounded-xl ring-1 ring-white/[0.05]">
                    <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-card/95 backdrop-blur">
                            <tr>
                                {columns.map((c) => (
                                    <th
                                        key={c.header}
                                        className={cn("px-3 py-2 text-left font-medium text-muted-foreground", c.align === "right" && "text-right")}
                                    >
                                        {c.header}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                            {rows.map((r) => (
                                <tr key={rowKey(r)} className="hover:bg-white/[0.02]">
                                    {columns.map((c) => (
                                        <td key={c.header} className={cn("px-3 py-1.5", c.align === "right" && "text-right tabular-nums")}>
                                            {c.cell(r)}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </Panel>
    );
}
