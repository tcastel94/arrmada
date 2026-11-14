"use client";

/**
 * Assistant IA (/assistant) : une demande en clair, des actions vérifiées.
 * ----------------------------------------------------------------
 * « Ajoute le dernier Dune et complète la saga Harry Potter » → l'IA
 * propose des cartes d'action (cible retrouvée par le serveur dans Radarr,
 * Sonarr, Lidarr) ; « Valider » exécute avec les mêmes fonctions que les
 * boutons, « Annuler » écarte. En mode « agir tout de suite » (Paramètres),
 * les cartes arrivent déjà faites. L'assistant ne supprime jamais rien.
 */
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Bot, Check, CircleSlash, Loader2, Send, Sparkles, TriangleAlert, X } from "lucide-react";
import { toast } from "sonner";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAiAct, useAiDecide, useAiSettings, type AiAnswer, type AiProposal } from "@/hooks/use-ai-actions";
import { cn } from "@/lib/utils";

const EXAMPLES = [
    "Ajoute le film Interstellar",
    "Complète la saga Harry Potter",
    "Cherche les épisodes manquants de The Expanse",
    "Débloque les téléchargements en panne",
    "Importe la musique des téléchargements",
];

interface Turn {
    question: string;
    answer: AiAnswer;
}

export default function AssistantPage() {
    const settings = useAiSettings();
    const act = useAiAct();
    const [text, setText] = useState("");
    const [turns, setTurns] = useState<Turn[]>([]);

    const send = (message: string) => {
        const clean = message.trim();
        if (clean.length < 2 || act.isPending) return;
        act.mutate(clean, {
            onSuccess: (answer) => {
                setTurns((t) => [{ question: clean, answer }, ...t]);
                setText("");
            },
            onError: (e) => toast.error("L'assistant n'a pas pu répondre", { description: e.message }),
        });
    };
    const submit = (e: FormEvent) => {
        e.preventDefault();
        send(text);
    };
    const auto = settings.data?.mode === "auto";

    return (
        <>
            <Header title="Assistant" />
            <PageContainer>
                <PageHeader
                    title="Assistant IA"
                    description={
                        <>
                            Demande en clair : ajouter un film, une série, un artiste, compléter une saga, chercher ce qui manque, débloquer les
                            téléchargements. {auto ? "Il agit tout de suite" : "Chaque action attend ta validation"} (
                            <Link href="/settings" className="text-primary hover:opacity-80">
                                Paramètres
                            </Link>
                            ). Il ne supprime jamais rien.
                        </>
                    }
                />

                <form onSubmit={submit} className="flex gap-2">
                    <Input
                        id="assistant-message"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Ex. : ajoute le dernier John Wick"
                        maxLength={500}
                        aria-label="Demande à l'assistant"
                        disabled={settings.data?.configured === false}
                    />
                    <Button type="submit" disabled={act.isPending || text.trim().length < 2}>
                        {act.isPending ? <Loader2 className="animate-spin" /> : <Send />}
                        Demander
                    </Button>
                </form>
                {settings.data?.configured === false && (
                    <p className="text-[13px] text-warning">Aucune IA configurée (Ollama ou OpenRouter dans le .env).</p>
                )}
                {act.isPending && (
                    <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" /> L&apos;IA réfléchit, puis ArrMada vérifie les titres…
                    </p>
                )}

                {turns.length === 0 ? (
                    <div className="flex flex-wrap gap-2">
                        {EXAMPLES.map((ex) => (
                            <button
                                key={ex}
                                type="button"
                                onClick={() => send(ex)}
                                className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5 text-[13px] text-muted-foreground hover:text-foreground"
                            >
                                <Sparkles className="h-3.5 w-3.5" /> {ex}
                            </button>
                        ))}
                    </div>
                ) : (
                    <div className="space-y-5">
                        {turns.map((turn, i) => (
                            <TurnView key={turns.length - i} turn={turn} />
                        ))}
                    </div>
                )}
            </PageContainer>
        </>
    );
}

function TurnView({ turn }: { turn: Turn }) {
    return (
        <section className="space-y-2" aria-label={turn.question}>
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-primary/15 px-3.5 py-2 text-[14px]">{turn.question}</p>
            <div className="flex gap-2.5">
                <Bot className="mt-1 h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0 flex-1 space-y-2">
                    <p className="text-[14px]">{turn.answer.reply}</p>
                    {turn.answer.proposals.map((p) => (
                        <ProposalCard key={p.id} initial={p} />
                    ))}
                </div>
            </div>
        </section>
    );
}

const STATUS: Record<string, { label: string; className: string }> = {
    done: { label: "Fait", className: "text-success" },
    error: { label: "Échec", className: "text-destructive" },
    cancelled: { label: "Annulée", className: "text-muted-foreground" },
    unresolved: { label: "Rien à faire", className: "text-warning" },
};

/** Carte d'une action : résumé vérifié par le serveur, Valider / Annuler si elle attend. */
function ProposalCard({ initial }: { initial: AiProposal }) {
    const [p, setP] = useState(initial);
    const decide = useAiDecide();
    const run = (accept: boolean) =>
        decide.mutate(
            { id: p.id, accept },
            {
                onSuccess: setP,
                onError: (e) => toast.error("Action impossible", { description: e.message }),
            },
        );
    const state = STATUS[p.status];
    return (
        <div
            className={cn(
                "flex flex-wrap items-center gap-3 rounded-xl border p-3",
                p.status === "pending" ? "border-primary/40 bg-primary/[0.06]" : "border-white/[0.08] bg-card",
            )}
        >
            <div className="min-w-0 flex-1">
                <p className={cn("text-[14px] font-medium", p.status === "unresolved" && "text-muted-foreground")}>{p.summary}</p>
                {p.message && (
                    <p className={cn("mt-0.5 flex items-center gap-1 text-[12.5px]", state?.className ?? "text-muted-foreground")}>
                        {p.status === "done" && <Check className="h-3.5 w-3.5" />}
                        {p.status === "error" && <TriangleAlert className="h-3.5 w-3.5" />}
                        {p.status === "unresolved" && <CircleSlash className="h-3.5 w-3.5" />}
                        {p.message}
                    </p>
                )}
            </div>
            {p.status === "pending" ? (
                <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => run(false)} disabled={decide.isPending}>
                        <X /> Annuler
                    </Button>
                    <Button size="sm" onClick={() => run(true)} disabled={decide.isPending}>
                        {decide.isPending ? <Loader2 className="animate-spin" /> : <Check />}
                        Valider
                    </Button>
                </div>
            ) : (
                state && <span className={cn("text-[12.5px] font-semibold", state.className)}>{state.label}</span>
            )}
        </div>
    );
}
