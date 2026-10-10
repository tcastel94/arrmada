"use client";

/**
 * Chemins NAS : où atterrissent les téléchargements, les films et les séries
 * côté hôte, + les montages Docker de chaque service (repliables).
 * ----------------------------------------------------------------
 * Corrections : la carte était masquée quand SEUL le chemin des
 * téléchargements était défini ; libellés FR (plus de « 📥 Downloads ») ;
 * bouton « copier » pour coller le chemin dans un terminal.
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Copy, Download, Film, HardDrive, Tv, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { usePathMappings } from "@/hooks/use-files";
import { Panel } from "@/components/shared/panel";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

async function copy(text: string) {
    try {
        await navigator.clipboard.writeText(text);
        toast.success("Chemin copié", { description: text });
    } catch {
        toast.error("Copie impossible", { description: "Ton navigateur bloque l'accès au presse-papiers." });
    }
}

export function NasPaths() {
    const { data, isLoading, isError, error, refetch } = usePathMappings();
    const [showMounts, setShowMounts] = useState(false);

    if (isLoading) {
        return (
            <div className="grid gap-3 sm:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                    <Shimmer key={i} className="h-[74px] rounded-2xl" />
                ))}
            </div>
        );
    }

    if (isError) {
        return (
            <Panel title="Chemins NAS" icon={HardDrive}>
                <ErrorState compact error={error} onRetry={() => refetch()} title="Impossible de lire les chemins NAS" />
            </Panel>
        );
    }

    const tiles: Array<{ label: string; path: string; icon: LucideIcon; tone: string }> = [
        { label: "Téléchargements", path: data?.downloads_host_path ?? "", icon: Download, tone: "text-primary" },
        { label: "Films", path: data?.movies_host_path ?? "", icon: Film, tone: "text-violet-300" },
        { label: "Séries", path: data?.series_host_path ?? "", icon: Tv, tone: "text-sky-300" },
    ].filter((t) => t.path);

    const mounts = Object.entries(data?.service_mounts ?? {}).filter(([, list]) => list && list.length > 0);

    // Rien de configuré : inutile d'afficher une carte vide.
    if (tiles.length === 0 && mounts.length === 0) return null;

    return (
        <Panel
            title="Chemins NAS"
            icon={HardDrive}
            iconClassName="text-sky-300"
            action={
                mounts.length > 0 ? (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowMounts((s) => !s)}
                        aria-expanded={showMounts}
                        className="h-7 text-xs"
                    >
                        Montages Docker
                        <ChevronDown className={cn("transition-transform duration-300", showMounts && "rotate-180")} />
                    </Button>
                ) : null
            }
        >
            {tiles.length > 0 && (
                <div className={cn("grid gap-3", tiles.length === 3 ? "sm:grid-cols-3" : tiles.length === 2 ? "sm:grid-cols-2" : "")}>
                    {tiles.map((t) => (
                        <div
                            key={t.label}
                            className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-background/40 p-3 transition-colors hover:border-white/[0.12]"
                        >
                            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ring-white/[0.06]">
                                <t.icon className={cn("h-4 w-4", t.tone)} />
                            </span>
                            <div className="min-w-0 flex-1">
                                <p className="text-[11px] text-muted-foreground">{t.label}</p>
                                <code className="block truncate font-mono text-xs text-foreground" title={t.path}>
                                    {t.path}
                                </code>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Copier le chemin ${t.label}`}
                                onClick={() => copy(t.path)}
                                className="text-muted-foreground opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
                            >
                                <Copy />
                            </Button>
                        </div>
                    ))}
                </div>
            )}

            <AnimatePresence initial={false}>
                {showMounts && mounts.length > 0 && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.35, ease: EASE_OUT }}
                        className="overflow-hidden"
                    >
                        <div className={cn("grid gap-3 md:grid-cols-2", tiles.length > 0 && "mt-4")}>
                            {mounts.map(([service, list]) => (
                                <div key={service} className="rounded-xl border border-white/[0.06] bg-background/30 p-3">
                                    <p className="mb-2 text-xs font-semibold capitalize">{service}</p>
                                    <ul className="space-y-1.5">
                                        {list.map((m) => (
                                            <li key={`${m.host}→${m.container}`} className="flex items-center gap-2 text-[11px]">
                                                <code className="min-w-0 flex-1 truncate font-mono text-muted-foreground" title={m.host}>
                                                    {m.host}
                                                </code>
                                                <span className="text-muted-foreground/50">→</span>
                                                <code className="min-w-0 flex-1 truncate font-mono text-foreground/85" title={m.container}>
                                                    {m.container}
                                                </code>
                                                <span
                                                    className={cn(
                                                        "shrink-0 rounded px-1 text-[9px] font-semibold uppercase",
                                                        m.rw ? "bg-emerald-500/15 text-emerald-300" : "bg-white/[0.06] text-muted-foreground",
                                                    )}
                                                    title={m.rw ? "Lecture / écriture" : "Lecture seule"}
                                                >
                                                    {m.rw ? "rw" : "ro"}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </Panel>
    );
}
