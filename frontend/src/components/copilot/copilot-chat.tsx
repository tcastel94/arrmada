"use client";

/**
 * Agent IA : la conversation.
 * ----------------------------------------------------------------
 * - Écran vide : ce que sait faire l'agent + demandes prêtes à envoyer.
 * - Réponse : texte rendu en Markdown, entrecoupé des outils consultés
 *   (« Profils qualité · radarr ✓ 210 ms ») pour voir sur quoi elle s'appuie.
 * - Action : une carte « Débloquer « Dune » → Valider / Annuler » ; l'agent
 *   attend ton clic, puis la carte affiche le résultat (ADR-019).
 * - Pendant la réflexion : son résumé défile sous la réponse.
 * - Sous la réponse : coût estimé du tour et nombre d'étapes.
 * - Zone de saisie collée en bas (au-dessus de la barre d'onglets sur mobile).
 * États gérés : non configuré (clé d'API absente), chargement, erreur du
 * serveur, réponse interrompue, conversation perdue après un redémarrage.
 */
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
    AlertTriangle,
    ArrowUp,
    Check,
    CircleSlash,
    Globe,
    KeyRound,
    Loader2,
    RotateCcw,
    ShieldCheck,
    Sparkles,
    Square,
    Wrench,
    X,
    Zap,
} from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import {
    answerCopilotAction,
    resetCopilot,
    sendCopilotMessage,
    stopCopilot,
    useCopilot,
    useCopilotStatus,
    type CopilotAction,
    type CopilotMessage,
    type CopilotStatus,
    type CopilotTool,
    type CopilotUsage,
} from "@/hooks/use-copilot";
import { formatNumber, plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Markdown } from "./markdown";

/** Demandes d'amorce : d'abord réparer, puis ajouter, puis auditer et anticiper. */
const SUGGESTIONS = [
    "Débloque tous mes téléchargements et imports bloqués.",
    "Pourquoi mes imports Sonarr sont-ils bloqués ? Règle-les.",
    "Des albums sont bloqués dans Lidarr : trouve pourquoi et importe-les.",
    "Ajoute le film Interstellar et complète la saga Harry Potter.",
    "Fais un audit de ma configuration Radarr par rapport aux TRaSH Guides.",
    "Si je passe mon profil films principal en Remux 2160p, qu'est-ce que ça déclenche ?",
    "Mes hardlinks et mes chemins sont-ils bien configurés entre SABnzbd, Radarr et Sonarr ?",
] as const;

export function CopilotChat() {
    const status = useCopilotStatus();
    const { messages, busy } = useCopilot();

    return (
        <>
            <PageHeader
                title="Agent IA"
                description="Décris le problème : l'agent lit l'état réel de ta stack, trouve la cause et la règle avec ta validation."
                actions={
                    messages.length > 0 ? (
                        <Button variant="ghost" size="sm" onClick={resetCopilot}>
                            <RotateCcw />
                            Nouvelle conversation
                        </Button>
                    ) : undefined
                }
            />

            {status.isLoading ? (
                <div className="space-y-3" aria-hidden>
                    <Shimmer className="h-24 rounded-xl" />
                    <Shimmer className="h-12 rounded-xl" />
                </div>
            ) : status.isError ? (
                <ErrorState error={status.error} onRetry={() => status.refetch()} title="Agent injoignable" />
            ) : status.data && !status.data.configured ? (
                <NotConfigured status={status.data} />
            ) : (
                <Conversation messages={messages} busy={busy} status={status.data} />
            )}
        </>
    );
}

/* ── Clé d'API absente ──────────────────────────────────────── */

function NotConfigured({ status }: { status: CopilotStatus }) {
    const code = "rounded bg-white/[0.08] px-1 font-mono text-[13px] text-foreground";
    return (
        <div className="surface space-y-4 rounded-xl p-5">
            <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-warning/15 text-warning">
                    <KeyRound className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                    <p className="text-[17px] font-semibold tracking-tight">Il manque une clé d&apos;API</p>
                    <p className="mt-0.5 text-[15px] leading-snug text-muted-foreground">
                        L&apos;agent s&apos;appuie sur un modèle Claude ({status.model}), appelé par l&apos;API d&apos;Anthropic. La consommation est
                        facturée à l&apos;usage sur ton compte Anthropic.
                    </p>
                </div>
            </div>
            <ol className="list-decimal space-y-2 pl-5 text-[15px] leading-snug text-muted-foreground marker:text-warning">
                <li>
                    Crée une clé sur{" "}
                    <a href="https://platform.claude.com/settings/keys" target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                        platform.claude.com
                    </a>
                    .
                </li>
                <li>
                    Ajoute <code className={code}>ANTHROPIC_API_KEY=…</code> dans le fichier <code className={code}>.env</code> à côté de ton{" "}
                    <code className={code}>docker-compose.yml</code>.
                </li>
                <li>
                    Relance le conteneur : <code className={code}>docker compose up -d</code>, puis reviens ici.
                </li>
            </ol>
            <PrivacyNote webSearch={status.web_search} mode={status.action_mode} />
        </div>
    );
}

/** Ce que l'agent a le droit de faire, et ce qui sort du réseau local, dit une fois, sans détour. */
function PrivacyNote({ webSearch, mode }: { webSearch: boolean; mode?: "confirm" | "auto" }) {
    return (
        <p className="flex items-start gap-2 text-[13px] leading-snug text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <span>
                {mode === "auto"
                    ? "Mode « agir tout de suite » : l'agent exécute ses actions sans attendre ton clic. "
                    : "Chaque action (débloquer, importer, relancer, ajouter) attend ta validation. "}
                Il ne supprime jamais rien de la médiathèque et ne change pas tes réglages (
                <Link href="/settings" className="text-primary hover:underline">
                    Paramètres › Agent IA
                </Link>
                ). Ce qu&apos;il consulte (profils, files, journaux, titres) est envoyé à Anthropic, clés d&apos;API et mots de passe masqués.
                {webSearch && " La recherche web est limitée à la documentation de référence (TRaSH Guides, wiki Servarr…)."}
            </span>
        </p>
    );
}

/* ── Conversation ───────────────────────────────────────────── */

function Conversation({ messages, busy, status }: { messages: CopilotMessage[]; busy: boolean; status?: CopilotStatus }) {
    const endRef = useRef<HTMLDivElement>(null);
    /** Vrai tant que l'utilisateur est en bas de page : on suit alors la réponse qui s'écrit. */
    const pinned = useRef(true);

    useEffect(() => {
        const onScroll = () => {
            pinned.current = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    useEffect(() => {
        if (pinned.current) endRef.current?.scrollIntoView({ block: "end" });
    }, [messages]);

    const send = (text: string) => {
        pinned.current = true;
        void sendCopilotMessage(text);
    };

    return (
        <div className="flex flex-col gap-6">
            {messages.length === 0 ? (
                <Intro onPick={send} webSearch={status?.web_search ?? false} mode={status?.action_mode} />
            ) : (
                <ol className="flex flex-col gap-6" aria-live="polite">
                    {messages.map((message) => (
                        <li key={message.id}>{message.role === "user" ? <UserBubble message={message} /> : <Answer message={message} />}</li>
                    ))}
                </ol>
            )}
            <Composer busy={busy} onSend={send} />
            <div ref={endRef} aria-hidden />
        </div>
    );
}

function Intro({ onPick, webSearch, mode }: { onPick: (text: string) => void; webSearch: boolean; mode?: "confirm" | "auto" }) {
    return (
        <div className="space-y-5">
            <div className="surface space-y-3 rounded-xl p-5">
                <div className="flex items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#BF5AF2]/20 text-[#BF5AF2]">
                        <Sparkles className="h-5 w-5" />
                    </span>
                    <p className="text-[15px] leading-relaxed text-muted-foreground">
                        L&apos;agent connaît la suite *arr, les TRaSH Guides et la documentation d&apos;ArrMada. Il{" "}
                        <span className="text-foreground">lit ton installation</span> (files, journaux, indexeurs, historique d&apos;un titre),
                        trouve la cause et <span className="text-foreground">la règle</span> : débloquer un téléchargement, importer des fichiers
                        refusés, changer une release morte, relancer SABnzbd, ajouter un film ou une saga. Il sait aussi auditer ta configuration et
                        dire ce que déclencherait un changement.
                    </p>
                </div>
                <PrivacyNote webSearch={webSearch} mode={mode} />
            </div>

            <div>
                <p className="eyebrow mb-2 px-0.5">Pour commencer</p>
                <div className="grid gap-2 sm:grid-cols-2">
                    {SUGGESTIONS.map((suggestion) => (
                        <button
                            key={suggestion}
                            type="button"
                            onClick={() => onPick(suggestion)}
                            className="surface glass-hover rounded-xl p-3.5 text-left text-[15px] leading-snug text-foreground/90 transition-transform active:scale-[0.99]"
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}

function UserBubble({ message }: { message: CopilotMessage }) {
    const text = message.parts.map((part) => (part.kind === "text" ? part.text : "")).join("");
    return (
        <div className="flex justify-end">
            <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary/20 px-4 py-2.5 text-[15px] leading-relaxed [overflow-wrap:anywhere]">
                {text}
            </p>
        </div>
    );
}

function Answer({ message }: { message: CopilotMessage }) {
    const streaming = message.state === "streaming";
    const empty = message.parts.length === 0;
    return (
        <div className="min-w-0 space-y-3">
            {message.notices.map((notice) => (
                <p key={notice} className="flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2 text-[13px] leading-snug text-warning">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    {notice}
                </p>
            ))}

            {message.parts.map((part, index) =>
                part.kind === "text" ? (
                    <Markdown key={index}>{part.text}</Markdown>
                ) : part.kind === "action" ? (
                    <ActionCard key={part.action.id} action={part.action} />
                ) : (
                    <ToolGroup key={index} tools={part.tools} />
                ),
            )}

            {streaming && <Thinking text={message.thinking} waiting={empty} />}

            {message.state === "error" && (
                <p className="flex items-start gap-2 rounded-xl bg-destructive/10 px-3 py-2.5 text-[15px] leading-snug text-destructive" role="alert">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span className="[overflow-wrap:anywhere]">{message.error}</span>
                </p>
            )}
            {message.state === "stopped" && (
                <p className="text-[13px] text-muted-foreground">Réponse interrompue. L&apos;agent ne garde pas ce tour en mémoire.</p>
            )}
            {message.usage && !streaming && <UsageLine usage={message.usage} />}
        </div>
    );
}

/* ── Action à valider ───────────────────────────────────────── */

const ACTION_STATE: Record<CopilotAction["state"], { text: string; className: string }> = {
    pending: { text: "En attente de ta validation", className: "text-primary" },
    sending: { text: "Envoi de ta réponse…", className: "text-muted-foreground" },
    running: { text: "En cours…", className: "text-muted-foreground" },
    done: { text: "Fait", className: "text-success" },
    failed: { text: "Échec", className: "text-destructive" },
    refused: { text: "Annulé", className: "text-muted-foreground" },
    expired: { text: "Non faite (sans réponse)", className: "text-muted-foreground" },
};

/** Ce que l'agent veut faire : aperçu, détail, avertissement, puis Valider / Annuler. */
function ActionCard({ action }: { action: CopilotAction }) {
    const state = ACTION_STATE[action.state];
    const waiting = action.state === "pending" || action.state === "sending";
    return (
        <div
            className={cn(
                "space-y-2.5 rounded-xl p-3.5 ring-1",
                waiting ? "bg-primary/[0.08] ring-primary/40" : "bg-white/[0.04] ring-white/[0.06]",
            )}
            aria-label={`Action : ${action.summary}`}
        >
            <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                    <Zap className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">{action.label}</p>
                    <p className="text-[15px] font-semibold leading-snug [overflow-wrap:anywhere]">{action.summary}</p>
                </div>
            </div>
            {action.details.length > 0 && (
                <ul className="space-y-0.5 pl-9 text-[13px] leading-snug text-muted-foreground">
                    {action.details.map((line, index) => (
                        <li key={index} className="[overflow-wrap:anywhere]">
                            {line}
                        </li>
                    ))}
                </ul>
            )}
            {action.warning && (
                <p className="ml-9 flex items-start gap-1.5 text-[13px] leading-snug text-warning">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    {action.warning}
                </p>
            )}
            {waiting ? (
                <div className="flex flex-wrap gap-2 pl-9">
                    <Button size="sm" onClick={() => void answerCopilotAction(action.id, true)} disabled={action.state === "sending"}>
                        {action.state === "sending" ? <Loader2 className="animate-spin" /> : <Check />}
                        Valider
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => void answerCopilotAction(action.id, false)} disabled={action.state === "sending"}>
                        <X />
                        Annuler
                    </Button>
                </div>
            ) : (
                <p className={cn("flex items-start gap-1.5 pl-9 text-[13px] font-medium leading-snug", state.className)} role="status">
                    {action.state === "running" ? (
                        <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" />
                    ) : action.state === "done" ? (
                        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    ) : action.state === "failed" ? (
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    ) : (
                        <CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    )}
                    <span className="[overflow-wrap:anywhere]">
                        {state.text}
                        {action.auto && action.state !== "failed" ? " (sans attendre, mode « agir tout de suite »)" : ""}
                        {action.result ? ` : ${action.result}` : ""}
                    </span>
                </p>
            )}
        </div>
    );
}

/** Outils consultés d'affilée : une ligne par outil, état à gauche. */
function ToolGroup({ tools }: { tools: CopilotTool[] }) {
    return (
        <ul className="space-y-1 rounded-xl bg-white/[0.04] px-3 py-2 ring-1 ring-white/[0.05]">
            {tools.map((tool) => {
                const Icon = tool.name.startsWith("web_") ? Globe : Wrench;
                return (
                    <li key={tool.id} className="flex items-center gap-2 text-[13px] leading-snug">
                        {tool.state === "running" ? (
                            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-label="en cours" />
                        ) : tool.state === "ok" ? (
                            <Check className="h-3.5 w-3.5 shrink-0 text-success" aria-label="lu" />
                        ) : (
                            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning" aria-label="en échec" />
                        )}
                        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                        <span className="shrink-0 font-medium text-foreground/90">{tool.label}</span>
                        {tool.detail && <span className="min-w-0 truncate text-muted-foreground">{tool.detail}</span>}
                        {tool.durationMs !== undefined && tool.state !== "running" && (
                            <span className="ml-auto shrink-0 tabular-nums text-muted-foreground/70">
                                {tool.durationMs < 1000 ? `${tool.durationMs} ms` : `${(tool.durationMs / 1000).toFixed(1).replace(".", ",")} s`}
                            </span>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}

/** Réflexion en cours : son résumé (dernière ligne) plutôt qu'un écran figé. */
function Thinking({ text, waiting }: { text: string; waiting: boolean }) {
    const lines = text.trim().split("\n").filter(Boolean);
    const last = lines[lines.length - 1] ?? "";
    return (
        <p className="flex items-center gap-2 text-[13px] text-muted-foreground" role="status">
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
            <span className="min-w-0 truncate italic">{last || (waiting ? "L'agent regarde ta demande…" : "Réflexion…")}</span>
        </p>
    );
}

function UsageLine({ usage }: { usage: CopilotUsage }) {
    const cost =
        usage.costUsd === null
            ? null
            : `≈ ${usage.costUsd.toLocaleString("fr-FR", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 3 })}`;
    const read = usage.inputTokens + usage.cacheReadTokens;
    const facts = [
        cost,
        plural(usage.modelCalls, "étape"),
        `${formatNumber(read)} jetons lus`,
        usage.webSearches > 0 ? plural(usage.webSearches, "recherche web", "recherches web") : null,
        usage.model,
    ].filter(Boolean);
    return (
        <p className="text-[12px] tabular-nums text-muted-foreground/70" title="Coût estimé de ce tour d'après les tarifs publics (hors recherches web). La facture Anthropic fait foi.">
            {facts.join(" · ")}
        </p>
    );
}

/* ── Saisie ─────────────────────────────────────────────────── */

function Composer({ busy, onSend }: { busy: boolean; onSend: (text: string) => void }) {
    const [value, setValue] = useState("");
    const ref = useRef<HTMLTextAreaElement>(null);

    // Hauteur selon le contenu, de 1 à ~7 lignes
    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        element.style.height = "auto";
        element.style.height = `${Math.min(element.scrollHeight, 176)}px`;
    }, [value]);

    const submit = (event?: FormEvent) => {
        event?.preventDefault();
        if (busy || !value.trim()) return;
        onSend(value);
        setValue("");
    };

    const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        // Entrée envoie, Maj+Entrée va à la ligne ; pas pendant une composition (accents, IME)
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
        }
    };

    return (
        <form
            onSubmit={submit}
            className={cn(
                "sticky z-20 -mx-1 bg-gradient-to-t from-background from-70% to-transparent px-1 pb-2 pt-4",
                "bottom-[calc(var(--tabbar-h)+env(safe-area-inset-bottom)+var(--miniplayer-h,0px))] lg:bottom-[var(--miniplayer-h,0px)]",
            )}
        >
            <div className="surface flex items-end gap-2 rounded-2xl p-2 pl-4 focus-within:ring-2 focus-within:ring-primary/50">
                <textarea
                    ref={ref}
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    maxLength={8000}
                    placeholder="Décris le problème ou ce qu'il faut faire…"
                    aria-label="Ta demande pour l'agent"
                    className="min-h-10 flex-1 resize-none bg-transparent py-2 text-base leading-snug placeholder:text-muted-foreground/80 focus:outline-none md:text-[15px]"
                />
                {busy ? (
                    <Button type="button" size="icon" variant="secondary" onClick={stopCopilot} aria-label="Arrêter la réponse">
                        <Square className="fill-current" />
                    </Button>
                ) : (
                    <Button type="submit" size="icon" disabled={!value.trim()} aria-label="Envoyer">
                        <ArrowUp />
                    </Button>
                )}
            </div>
        </form>
    );
}
