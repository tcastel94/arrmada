"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ArrowLeft,
    CheckCircle2,
    XCircle,
    Download,
    Shield,
    FolderOpen,
    Settings,
    ToggleRight,
    Layers,
    RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useSabnzbdAudit, useSabnzbdApply, type ConfigCheck } from "@/hooks/use-sabnzbd-config";

export default function SabnzbdConfigPage() {
    const { data: audit, isLoading, isFetching, error, refetch } = useSabnzbdAudit();
    const applyConfig = useSabnzbdApply();

    // Auto-refetch after successful apply
    const handleApply = () => {
        applyConfig.mutate(undefined, {
            onSuccess: () => {
                // Wait a bit for SABnzbd to process, then refetch
                setTimeout(() => refetch(), 1500);
            },
        });
    };

    const categoryIcons: Record<string, any> = {
        categories: FolderOpen,
        switches: ToggleRight,
        sorting: Layers,
        general: Settings,
    };

    const categoryLabels: Record<string, string> = {
        categories: "Catégories",
        switches: "Switches / Post-Processing",
        sorting: "Tri (Sorting)",
        general: "Général",
    };

    // Group checks by category
    const groupedChecks: Record<string, ConfigCheck[]> = {};
    if (audit) {
        for (const check of audit.checks) {
            if (!groupedChecks[check.category]) {
                groupedChecks[check.category] = [];
            }
            groupedChecks[check.category].push(check);
        }
    }

    return (
        <div className="min-h-screen bg-background p-6 space-y-6 max-w-5xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/settings">
                        <Button variant="ghost" size="icon">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Shield className="h-6 w-6 text-orange-400" />
                            SABnzbd — TRaSH Config
                        </h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Audit et optimisation selon les recommandations TRaSH Guides
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetch()}
                        disabled={isFetching}
                    >
                        <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
                        Rafraîchir
                    </Button>
                </div>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-20">
                    <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            )}

            {/* Error */}
            {error && (
                <Card className="border-red-500/50 bg-red-500/10">
                    <CardContent className="pt-6">
                        <p className="text-red-400">❌ {error.message}</p>
                    </CardContent>
                </Card>
            )}

            {/* Audit Results */}
            {audit && (
                <>
                    {/* Compliance Summary */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                    >
                        <Card className="bg-card/50 border-border/50">
                            <CardContent className="pt-6">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-6">
                                        <div className="relative w-20 h-20">
                                            <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                                                <path
                                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                                    fill="none"
                                                    stroke="currentColor"
                                                    strokeWidth="2"
                                                    className="text-muted-foreground/20"
                                                />
                                                <path
                                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                                    fill="none"
                                                    stroke="currentColor"
                                                    strokeWidth="2.5"
                                                    strokeDasharray={`${audit.compliance_pct}, 100`}
                                                    className={
                                                        audit.compliance_pct >= 80
                                                            ? "text-emerald-400"
                                                            : audit.compliance_pct >= 50
                                                                ? "text-amber-400"
                                                                : "text-red-400"
                                                    }
                                                />
                                            </svg>
                                            <span className="absolute inset-0 flex items-center justify-center text-lg font-bold">
                                                {audit.compliance_pct}%
                                            </span>
                                        </div>
                                        <div>
                                            <p className="text-lg font-semibold">{audit.service_name}</p>
                                            <p className="text-sm text-muted-foreground">
                                                {audit.passed}/{audit.total_checks} vérifications OK
                                            </p>
                                        </div>
                                    </div>
                                    <Button
                                        className="gap-2"
                                        onClick={handleApply}
                                        disabled={applyConfig.isPending || audit.compliance_pct === 100}
                                    >
                                        {applyConfig.isPending ? (
                                            <><RefreshCw className="h-4 w-4 animate-spin" /> Application...</>
                                        ) : audit.compliance_pct === 100 ? (
                                            <><CheckCircle2 className="h-4 w-4" /> Tout est OK !</>
                                        ) : (
                                            <><Download className="h-4 w-4" /> Appliquer les recommandations TRaSH</>
                                        )}
                                    </Button>
                                </div>

                                {/* Apply Result */}
                                {applyConfig.isSuccess && (
                                    <div className="mt-4 p-3 rounded-lg border bg-emerald-500/10 text-emerald-400 text-sm">
                                        ✅ Config appliquée ! {applyConfig.data.categories_created} catégories créées,{" "}
                                        {applyConfig.data.settings_updated} réglages mis à jour.
                                        {applyConfig.data.errors.length > 0 && (
                                            <span className="text-amber-400">
                                                {" "}({applyConfig.data.errors.length} erreurs)
                                            </span>
                                        )}
                                    </div>
                                )}
                                {applyConfig.isError && (
                                    <div className="mt-4 p-3 rounded-lg border bg-red-500/10 text-red-400 text-sm">
                                        ❌ Erreur : {applyConfig.error.message}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Checks by Category */}
                    {Object.entries(groupedChecks).map(([category, checks], idx) => {
                        const Icon = categoryIcons[category] || Settings;
                        const passed = checks.filter((c) => c.is_compliant).length;
                        const allOk = passed === checks.length;

                        return (
                            <motion.div
                                key={category}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, delay: (idx + 1) * 0.1 }}
                            >
                                <Card className="bg-card/50 border-border/50">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-base flex items-center justify-between">
                                            <span className="flex items-center gap-2">
                                                <Icon className="h-4 w-4" />
                                                {categoryLabels[category] || category}
                                            </span>
                                            <Badge
                                                variant={allOk ? "default" : "destructive"}
                                                className={allOk ? "bg-emerald-500/20 text-emerald-400" : ""}
                                            >
                                                {passed}/{checks.length}
                                            </Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            {checks.map((check) => (
                                                <div
                                                    key={check.key}
                                                    className={`flex items-center justify-between p-3 rounded-lg border ${check.is_compliant
                                                        ? "border-emerald-500/20 bg-emerald-500/5"
                                                        : "border-red-500/20 bg-red-500/5"
                                                        }`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        {check.is_compliant ? (
                                                            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                                                        ) : (
                                                            <XCircle className="h-4 w-4 text-red-400 shrink-0" />
                                                        )}
                                                        <span className="text-sm">{check.label}</span>
                                                    </div>
                                                    <div className="flex items-center gap-3 text-xs">
                                                        {!check.is_compliant && (
                                                            <>
                                                                <span className="text-red-400">
                                                                    {String(check.current_value)}
                                                                </span>
                                                                <span className="text-muted-foreground">→</span>
                                                            </>
                                                        )}
                                                        <span className={check.is_compliant ? "text-emerald-400" : "text-amber-400"}>
                                                            {String(check.recommended_value)}
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        );
                    })}
                </>
            )}
        </div>
    );
}
