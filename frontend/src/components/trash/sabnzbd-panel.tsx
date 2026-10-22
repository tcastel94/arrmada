"use client";

/**
 * Onglet « SABnzbd » de /trash-guides (ex-page /settings/sabnzbd-config).
 * ----------------------------------------------------------------
 * Audit des réglages SABnzbd face aux recommandations TRaSH, puis
 * application. Corrections :
 *  - « Appliquer » passe par une confirmation qui LISTE les changements ;
 *  - retours par toasts (plus de bandeaux emoji) et erreurs détaillées
 *    (avant : seulement « (3 erreurs) ») ;
 *  - une seule relecture de l'audit après application ;
 *  - libellés en français, valeurs lisibles (Activé / Désactivé…).
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    ArrowRight,
    CheckCircle2,
    Download,
    FolderOpen,
    Layers,
    Loader2,
    RefreshCw,
    Settings2,
    ShieldCheck,
    ToggleRight,
    XCircle,
    type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { RingGauge } from "@/components/fx/ring-gauge";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { Button } from "@/components/ui/button";
import { useSabnzbdApply, useSabnzbdAudit, type ConfigCheck, type ConfigValue } from "@/hooks/use-sabnzbd-config";
import { plural } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Segmented } from "@/components/maintenance/segmented";

const CATEGORY_META: Record<string, { label: string; icon: LucideIcon; help: string }> = {
    categories: { label: "Catégories", icon: FolderOpen, help: "Une catégorie par application (sonarr, radarr…) pour ranger les téléchargements." },
    switches: { label: "Post-traitement", icon: ToggleRight, help: "Décompression, vérification et nettoyage après téléchargement." },
    sorting: { label: "Tri automatique", icon: Layers, help: "Le tri de SABnzbd doit être désactivé : Sonarr/Radarr s'en chargent." },
    general: { label: "Général", icon: Settings2, help: "Réglages divers." },
};

/** Valeur brute → texte lisible. */
function formatValue(v: ConfigValue): string {
    if (v === true) return "Activé";
    if (v === false) return "Désactivé";
    if (v === null || v === undefined || v === "") return "—";
    if (Array.isArray(v)) return v.length ? v.map(formatValue).join(", ") : "—";
    if (typeof v === "number") return v.toLocaleString("fr-FR");
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
}

type Filter = "all" | "issues";

export function SabnzbdPanel() {
    const { data: audit, isLoading, isError, error, refetch, isFetching } = useSabnzbdAudit();
    const apply = useSabnzbdApply();
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [filter, setFilter] = useState<Filter>("all");
    const [lastErrors, setLastErrors] = useState<string[]>([]);

    const failing = useMemo(() => (audit?.checks ?? []).filter((c) => !c.is_compliant), [audit]);
    const grouped = useMemo(() => {
        const groups = new Map<string, ConfigCheck[]>();
        for (const c of audit?.checks ?? []) {
            if (filter === "issues" && c.is_compliant) continue;
            const list = groups.get(c.category) ?? [];
            list.push(c);
            groups.set(c.category, list);
        }
        return Array.from(groups.entries());
    }, [audit, filter]);

    const runApply = async () => {
        try {
            const res = await apply.mutateAsync();
            setLastErrors(res.errors);
            const summary = `${plural(res.categories_created, "catégorie créée", "catégories créées")}, ${plural(res.settings_updated, "réglage mis à jour", "réglages mis à jour")}.`;
            if (res.success && res.errors.length === 0) toast.success("SABnzbd configuré selon TRaSH", { description: summary });
            else toast.warning(`Appliqué avec ${plural(res.errors.length, "erreur")}`, { description: `${summary} Détail sous le score.` });
        } catch (e) {
            toast.error("Impossible d'appliquer la configuration", { description: e instanceof Error ? e.message : undefined });
            throw e; // la confirmation reste ouverte
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Shimmer className="h-36 w-full rounded-2xl" />
                <Shimmer className="h-56 w-full rounded-2xl" />
            </div>
        );
    }
    if (isError || !audit) {
        return (
            <Panel>
                <ErrorState
                    error={error}
                    onRetry={() => refetch()}
                    title="Audit SABnzbd impossible"
                />
                <p className="-mt-6 pb-4 text-center text-xs text-muted-foreground">
                    Vérifie que SABnzbd est ajouté et joignable dans Paramètres › Services.
                </p>
            </Panel>
        );
    }

    const pct = Math.round(audit.compliance_pct);
    const tone = pct >= 90 ? "emerald" : pct >= 60 ? "amber" : "rose";
    const allGood = failing.length === 0;

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            {/* Synthèse */}
            <motion.div variants={fadeUp}>
                <Panel>
                    <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-center gap-5">
                            <RingGauge value={pct} size={96} stroke={8} tone={tone}>
                                <span className="text-xl font-bold">
                                    <AnimatedNumber value={pct} suffix=" %" />
                                </span>
                            </RingGauge>
                            <div>
                                <p className="eyebrow">Conformité TRaSH</p>
                                <p className="text-lg font-semibold">{audit.service_name}</p>
                                <p className="text-sm text-muted-foreground">
                                    {audit.passed}/{audit.total_checks} réglages conformes
                                    {!allGood && <span className="text-warning"> · {plural(failing.length, "écart")}</span>}
                                </p>
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
                                <RefreshCw className={cn(isFetching && "animate-spin")} />
                                Relancer l&apos;audit
                            </Button>
                            <Button onClick={() => setConfirmOpen(true)} disabled={allGood || apply.isPending}>
                                {apply.isPending ? <Loader2 className="animate-spin" /> : allGood ? <CheckCircle2 /> : <Download />}
                                {allGood ? "Tout est conforme" : "Corriger les écarts…"}
                            </Button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {lastErrors.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                className="overflow-hidden"
                            >
                                <div className="mt-4 rounded-xl bg-destructive/10 p-3 ring-1 ring-destructive/20">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-sm font-medium text-destructive">Erreurs de la dernière application</p>
                                        <Button variant="ghost" size="sm" onClick={() => setLastErrors([])}>
                                            Masquer
                                        </Button>
                                    </div>
                                    <ul className="mt-1 space-y-1 text-xs text-destructive/90">
                                        {lastErrors.map((err, i) => (
                                            <li key={`${i}:${err}`} className="flex gap-1.5">
                                                <XCircle className="mt-0.5 h-3 w-3 shrink-0" />
                                                <span className="break-words">{err}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </Panel>
            </motion.div>

            <motion.div variants={fadeUp}>
                <Segmented<Filter>
                    layoutId="sab-filter"
                    size="sm"
                    ariaLabel="Filtrer les réglages"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: "all", label: "Tous les réglages", count: audit.total_checks },
                        { value: "issues", label: "À corriger", count: failing.length, icon: XCircle, iconClassName: "text-destructive" },
                    ]}
                />
            </motion.div>

            {grouped.length === 0 ? (
                <motion.div variants={fadeUp}>
                    <Panel>
                        <div className="flex flex-col items-center gap-2 py-8 text-center">
                            <ShieldCheck className="h-8 w-8 text-success" />
                            <p className="font-semibold">Aucun écart</p>
                            <p className="text-sm text-muted-foreground">SABnzbd suit déjà toutes les recommandations TRaSH.</p>
                        </div>
                    </Panel>
                </motion.div>
            ) : (
                // Colonnes CSS (et non grille) : les panneaux de hauteurs
                // différentes s'empilent sans laisser de grands trous.
                <div className="gap-5 lg:columns-2 [&>*]:mb-5 [&>*]:break-inside-avoid">
                    {grouped.map(([category, checks]) => {
                        const meta = CATEGORY_META[category] ?? { label: category, icon: Settings2, help: "" };
                        const all = audit.checks.filter((c) => c.category === category);
                        const passed = all.filter((c) => c.is_compliant).length;
                        const ok = passed === all.length;
                        return (
                            <motion.div key={category} variants={fadeUp}>
                                <Panel
                                    title={meta.label}
                                    icon={meta.icon}
                                    iconClassName="text-orange-300"
                                    bodyClassName="p-0"
                                    action={
                                        <span
                                            className={cn(
                                                "rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums",
                                                ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive",
                                            )}
                                        >
                                            {passed}/{all.length}
                                        </span>
                                    }
                                >
                                    {meta.help && <p className="border-b border-white/[0.05] px-5 py-2.5 text-xs text-muted-foreground">{meta.help}</p>}
                                    <ul className="divide-y divide-white/[0.04]">
                                        {checks.map((check) => (
                                            <CheckRow key={check.key} check={check} />
                                        ))}
                                    </ul>
                                </Panel>
                            </motion.div>
                        );
                    })}
                </div>
            )}

            <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                title="Appliquer la configuration TRaSH ?"
                description={`${plural(failing.length, "réglage sera modifié", "réglages seront modifiés")} dans ${audit.service_name}.`}
                confirmLabel="Appliquer"
                onConfirm={runApply}
            >
                <ul className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
                    {failing.map((c) => (
                        <li key={c.key} className="rounded-xl bg-white/[0.03] px-3 py-2 text-xs ring-1 ring-white/[0.06]">
                            <p className="font-medium">{c.label}</p>
                            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-muted-foreground">
                                <span className="text-destructive line-through decoration-red-400/60">{formatValue(c.current_value)}</span>
                                <ArrowRight className="h-3 w-3" />
                                <span className="font-semibold text-success">{formatValue(c.recommended_value)}</span>
                            </p>
                        </li>
                    ))}
                </ul>
            </ConfirmDialog>
        </motion.div>
    );
}

function CheckRow({ check }: { check: ConfigCheck }) {
    return (
        <li className="flex flex-col gap-1.5 px-5 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <div className="flex min-w-0 items-start gap-2.5">
                {check.is_compliant ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-label="Conforme" />
                ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-label="Non conforme" />
                )}
                <div className="min-w-0">
                    <p className="text-sm">{check.label}</p>
                    <p className="font-mono text-[10px] text-muted-foreground/70">{check.key}</p>
                </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 pl-6 text-xs sm:pl-0">
                {check.is_compliant ? (
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 font-medium text-success">
                        {formatValue(check.current_value)}
                    </span>
                ) : (
                    <>
                        <span className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-destructive">{formatValue(check.current_value)}</span>
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <span className="rounded-md bg-warning/10 px-1.5 py-0.5 font-semibold text-warning">
                            {formatValue(check.recommended_value)}
                        </span>
                    </>
                )}
            </div>
        </li>
    );
}
