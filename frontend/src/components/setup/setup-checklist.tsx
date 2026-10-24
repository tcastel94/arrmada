"use client";

/**
 * « Ce qu'il te reste à faire » : la liste guidée après l'installation.
 * ----------------------------------------------------------------
 * Pour chaque étape : son état RÉEL (vérifié auprès de l'appli), pourquoi
 * elle compte, quoi faire exactement et un bouton qui ouvre la bonne page
 * de la bonne appli. En bas : les mots de passe générés par l'installeur,
 * à copier en un clic (le fichier credentials.txt du serveur n'est pas
 * lisible depuis un NAS Synology sans ligne de commande).
 *
 * « Vérifier à nouveau » relance toutes les sondes ; la liste se met aussi
 * à jour toute seule quand on revient sur l'onglet d'ArrMada.
 */
import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, Check, CheckCircle2, CircleDashed, Copy, ExternalLink, KeyRound, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/empty-state";
import { copyText } from "@/components/media-detail/labels";
import { useSetupChecklist, type ChecklistItem, type InstallerCredential } from "@/hooks/use-setup-checklist";
import { cn } from "@/lib/utils";

const STATUS = {
    done: { icon: CheckCircle2, className: "text-success", label: "Fait" },
    todo: { icon: CircleDashed, className: "text-warning", label: "À faire" },
    error: { icon: AlertTriangle, className: "text-destructive", label: "Injoignable" },
} as const;

export function SetupChecklist({ compact = false }: { compact?: boolean }) {
    const { data, isLoading, isError, error, refetch, isFetching } = useSetupChecklist();

    if (isError) return <ErrorState compact error={error} onRetry={() => refetch()} title="Vérification impossible" />;

    const total = data ? data.items.length : 0;
    const allDone = !!data && data.todo === 0 && data.items.every((i) => i.status === "done");

    return (
        <div className="space-y-4">
            {/* Barre de progression + bouton de vérification */}
            <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                        {isLoading || !data
                            ? "Vérification de tes applications…"
                            : allDone
                              ? "Tout est prêt, rien d'autre à faire !"
                              : `${data.done} sur ${total} terminé${data.done > 1 ? "s" : ""}`}
                    </p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
                        <div
                            className={cn("h-full rounded-full transition-[width] duration-500", allDone ? "bg-success" : "bg-primary")}
                            style={{ width: `${total ? Math.round(((data?.done ?? 0) / total) * 100) : 0}%` }}
                        />
                    </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => refetch()} disabled={isFetching}>
                    {isFetching ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                    Vérifier à nouveau
                </Button>
            </div>

            {isLoading || !data ? (
                <div className="space-y-2">
                    {[0, 1, 2, 3].map((i) => (
                        <Shimmer key={i} className="h-16 w-full rounded-2xl" />
                    ))}
                </div>
            ) : (
                <ol className="space-y-2">
                    {/* Ce qui reste à faire d'abord, ce qui est fait ensuite */}
                    {[...data.items]
                        .sort((a, b) => Number(a.status === "done") - Number(b.status === "done"))
                        .map((item, i) => (
                            <Step key={item.id} item={item} index={i + 1} compact={compact} />
                        ))}
                </ol>
            )}

            {data && data.credentials.length > 0 && <Credentials list={data.credentials} />}
        </div>
    );
}

function Step({ item, index, compact }: { item: ChecklistItem; index: number; compact: boolean }) {
    const s = STATUS[item.status];
    const open = item.status !== "done";
    const external = item.link?.url.startsWith("http");
    return (
        <li
            className={cn(
                "rounded-2xl border p-4",
                item.status === "done" && "border-white/[0.05] bg-white/[0.02]",
                item.status === "todo" && "border-warning/25 bg-warning/[0.05]",
                item.status === "error" && "border-destructive/25 bg-destructive/[0.05]",
            )}
        >
            <div className="flex items-start gap-3">
                <s.icon className={cn("mt-0.5 h-5 w-5 shrink-0", s.className)} aria-label={s.label} />
                <div className="min-w-0 flex-1">
                    <p className={cn("text-[15px] font-semibold", item.status === "done" && "text-foreground/70")}>
                        <span className="mr-1.5 text-muted-foreground tabular-nums">{index}.</span>
                        {item.title}
                    </p>
                    {item.detail && <p className={cn("mt-0.5 text-xs", s.className)}>{item.detail}</p>}
                    {open && !compact && <p className="mt-2 text-sm text-muted-foreground">{item.why}</p>}
                    {open && item.how && (
                        <p className="mt-2 rounded-xl bg-black/30 px-3 py-2 text-sm">
                            <span className="font-semibold text-primary">Quoi faire : </span>
                            {item.how}
                        </p>
                    )}
                    {open && item.link && (
                        <div className="mt-2.5">
                            {external ? (
                                <Button asChild variant="tinted" size="sm">
                                    <a href={item.link.url} target="_blank" rel="noreferrer">
                                        {item.link.label}
                                        <ExternalLink />
                                    </a>
                                </Button>
                            ) : (
                                <Button asChild variant="tinted" size="sm">
                                    <Link href={item.link.url}>{item.link.label}</Link>
                                </Button>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </li>
    );
}

/** Identifiants générés par l'installeur, avec bouton « Copier ». */
function Credentials({ list }: { list: InstallerCredential[] }) {
    const [copied, setCopied] = useState<string | null>(null);
    const copy = async (key: string, text: string) => {
        if (await copyText(text)) {
            setCopied(key);
            window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
        } else {
            toast.error("Copie impossible", { description: "Sélectionne le texte et copie-le à la main." });
        }
    };
    return (
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
            <p className="flex items-center gap-2 text-sm font-semibold">
                <KeyRound className="h-4 w-4 text-primary" />
                Tes mots de passe créés par l&apos;installeur
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
                Garde-les dans un endroit sûr (gestionnaire de mots de passe, carnet). Tu peux les changer dans chaque appli.
            </p>
            <div className="mt-3 divide-y divide-white/[0.05]">
                {list.map((c) => (
                    <div key={c.app} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm">
                        <span className="w-24 shrink-0 font-medium">{c.app}</span>
                        {c.username && (
                            <span className="text-muted-foreground">
                                identifiant <code className="select-all font-mono text-foreground">{c.username}</code>
                            </span>
                        )}
                        <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
                            mot de passe <code className="select-all break-all font-mono text-foreground">{c.password}</code>
                            <button
                                type="button"
                                onClick={() => copy(c.app, c.password)}
                                className="rounded-md p-1 text-muted-foreground hover:bg-white/[0.08] hover:text-foreground"
                                aria-label={`Copier le mot de passe ${c.app}`}
                            >
                                {copied === c.app ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                            </button>
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
