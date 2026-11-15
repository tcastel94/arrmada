"use client";

/**
 * Journal de l'agent IA (/copilot/journal) : chaque action de l'agent, avec
 * la demande qui l'a provoquée et, quand l'action a un contraire sûr, un
 * bouton « Annuler ». Comme un `auditd` sur le compte de service de l'agent.
 *
 * Une annulation ne supprime jamais rien : un titre ajouté n'est plus suivi
 * (plus de recherche automatique), il reste dans Radarr / Sonarr.
 */
import Link from "next/link";
import { CheckCircle2, ChevronLeft, MessageSquareQuote, RotateCcw, ScrollText, Undo2, XCircle } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { useAiJournal, useUndoAiAction, type AiJournalEntry } from "@/hooks/use-ai-journal";
import { formatLongDateTime, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Qui a lancé l'action : l'agent (conversation) ou l'assistant (TV, web, Telegram). */
const SOURCES: Record<string, string> = {
    copilot: "Agent IA",
    "ai-web": "Assistant (web)",
    "ai-tv": "Assistant (TV)",
    "ai-telegram": "Assistant (Telegram)",
    "ai-copilot": "Agent IA",
    web: "Toi, depuis ce journal",
};

export default function AiJournalPage() {
    const journal = useAiJournal();
    return (
        <>
            <Header title="Journal de l'agent" />
            <PageContainer size="narrow" className="space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <Link href="/copilot" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                        <ChevronLeft className="h-4 w-4" /> Agent IA
                    </Link>
                    <p className="text-[13px] text-muted-foreground">
                        Ce que l&apos;agent a fait, et pourquoi. « Annuler » ne supprime jamais rien.
                    </p>
                </div>
                {journal.isLoading ? (
                    <div className="space-y-3">
                        {[0, 1, 2].map((i) => (
                            <Shimmer key={i} className="h-24 rounded-2xl" />
                        ))}
                    </div>
                ) : journal.isError ? (
                    <ErrorState error={journal.error} onRetry={() => journal.refetch()} />
                ) : !journal.data?.length ? (
                    <EmptyState
                        icon={ScrollText}
                        title="Aucune action pour l'instant"
                        description="Dès que l'agent débloque, importe ou ajoute quelque chose, la ligne apparaît ici."
                        action={{ label: "Parler à l'agent", href: "/copilot" }}
                    />
                ) : (
                    <ol className="space-y-3">
                        {journal.data.map((entry) => (
                            <JournalRow key={entry.id} entry={entry} />
                        ))}
                    </ol>
                )}
            </PageContainer>
        </>
    );
}

function JournalRow({ entry }: { entry: AiJournalEntry }) {
    const undo = useUndoAiAction();
    const failed = entry.status !== "ok" && entry.status !== "info";
    const isUndo = entry.action === "undo";
    const Icon = isUndo ? Undo2 : failed ? XCircle : CheckCircle2;
    const when = entry.ts * 1000;
    return (
        <li className="rounded-2xl border border-white/10 bg-card/60 p-4">
            <div className="flex items-start gap-3">
                <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", failed ? "text-destructive" : isUndo ? "text-warning" : "text-success")} />
                <div className="min-w-0 flex-1 space-y-1.5">
                    <p className="font-medium leading-snug">{entry.title || entry.action}</p>
                    {entry.detail && <p className="text-sm text-muted-foreground">{entry.detail}</p>}
                    {entry.why && (
                        <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
                            <MessageSquareQuote className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>
                                Demande : <span className="italic text-foreground/80">« {entry.why} »</span>
                            </span>
                        </p>
                    )}
                    <p className="text-xs text-muted-foreground" title={formatLongDateTime(when)}>
                        {timeAgo(when)} · {SOURCES[entry.source] ?? entry.source}
                    </p>
                    {entry.undone && (
                        <p className="flex items-start gap-1.5 text-sm text-warning">
                            <RotateCcw className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>
                                Annulée {timeAgo(entry.undone.at * 1000)} : {entry.undone.message}
                            </span>
                        </p>
                    )}
                    {undo.isError && (
                        <p className="text-sm text-destructive">
                            {undo.error instanceof Error ? undo.error.message : "Annulation impossible"}
                        </p>
                    )}
                </div>
                {entry.undo_label && (
                    <Button
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        disabled={undo.isPending}
                        onClick={() => {
                            if (window.confirm(`${entry.undo_label} ?\n\n${entry.title}`)) undo.mutate(entry.id);
                        }}
                    >
                        <Undo2 />
                        {undo.isPending ? "Annulation…" : entry.undo_label}
                    </Button>
                )}
            </div>
        </li>
    );
}
