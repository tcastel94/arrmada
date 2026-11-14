"use client";

/**
 * Copilote : la conversation.
 * ----------------------------------------------------------------
 * - Écran vide : ce que sait faire le copilote + questions prêtes à envoyer.
 * - Réponse : texte rendu en Markdown, entrecoupé des outils consultés
 *   (« Profils qualité · radarr ✓ 210 ms ») pour voir sur quoi elle s'appuie.
 * - Pendant la réflexion : son résumé défile sous la réponse.
 * - Sous la réponse : coût estimé du tour et nombre d'étapes.
 * - Zone de saisie collée en bas (au-dessus de la barre d'onglets sur mobile).
 * États gérés : non configuré (clé d'API absente), chargement, erreur du
 * serveur, réponse interrompue, conversation perdue après un redémarrage.
 */
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { AlertTriangle, ArrowUp, Check, Globe, KeyRound, Loader2, RotateCcw, ShieldCheck, Sparkles, Square, Wrench } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import {
    resetCopilot,
    sendCopilotMessage,
    stopCopilot,
    useCopilot,
    useCopilotStatus,
    type CopilotMessage,
    type CopilotStatus,
    type CopilotTool,
    type CopilotUsage,
} from "@/hooks/use-copilot";
import { formatNumber, plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Markdown } from "./markdown";

/** Questions d'amorce : une par grand usage (audit, effet de bord, diagnostic, explication). */
const SUGGESTIONS = [
    "Fais un audit de ma configuration Radarr par rapport aux TRaSH Guides.",
    "Y a-t-il des téléchargements bloqués en ce moment, et pourquoi ?",
    "Si je passe mon profil films principal en Remux 2160p, qu'est-ce que ça déclenche ?",
    "Mes indexeurs sont-ils fiables, et lesquels posent problème ?",
    "Mes hardlinks et mes chemins sont-ils bien configurés entre SABnzbd, Radarr et Sonarr ?",
    "Qu'est-ce qui a changé récemment dans ArrMada côté lecture sur la TV ?",
] as const;

export function CopilotChat() {
    const status = useCopilotStatus();
    const { messages, busy } = useCopilot();

    return (
        <>
            <PageHeader
                title="Copilote"
                description="Pose une question sur ta stack : l'IA lit l'état réel de tes services avant de répondre."
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
                <ErrorState error={status.error} onRetry={() => status.refetch()} title="Copilote injoignable" />
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
                        Le copilote s&apos;appuie sur un modèle Claude ({status.model}), appelé par l&apos;API d&apos;Anthropic. La consommation est
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
            <PrivacyNote webSearch={status.web_search} />
        </div>
    );
}

/** Ce qui sort du réseau local, dit une fois, sans détour. */
function PrivacyNote({ webSearch }: { webSearch: boolean }) {
    return (
        <p className="flex items-start gap-2 text-[13px] leading-snug text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <span>
                Lecture seule : le copilote ne modifie aucun réglage. Ce qu&apos;il consulte pour te répondre (profils, files, journaux, titres) est
                envoyé à Anthropic, clés d&apos;API et mots de passe masqués.
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
                <Intro onPick={send} webSearch={status?.web_search ?? false} />
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

function Intro({ onPick, webSearch }: { onPick: (text: string) => void; webSearch: boolean }) {
    return (
        <div className="space-y-5">
            <div className="surface space-y-3 rounded-xl p-5">
                <div className="flex items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#BF5AF2]/20 text-[#BF5AF2]">
                        <Sparkles className="h-5 w-5" />
                    </span>
                    <p className="text-[15px] leading-relaxed text-muted-foreground">
                        Le copilote connaît la suite *arr, les TRaSH Guides et la documentation d&apos;ArrMada, et il{" "}
                        <span className="text-foreground">va lire ton installation</span> avant de répondre : profils, formats, files, indexeurs,
                        journaux, historique d&apos;un titre. Demande-lui un audit, la cause d&apos;un blocage, ou{" "}
                        <span className="text-foreground">ce que déclencherait un changement</span> avant de le faire.
                    </p>
                </div>
                <PrivacyNote webSearch={webSearch} />
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
                part.kind === "text" ? <Markdown key={index}>{part.text}</Markdown> : <ToolGroup key={index} tools={part.tools} />,
            )}

            {streaming && <Thinking text={message.thinking} waiting={empty} />}

            {message.state === "error" && (
                <p className="flex items-start gap-2 rounded-xl bg-destructive/10 px-3 py-2.5 text-[15px] leading-snug text-destructive" role="alert">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span className="[overflow-wrap:anywhere]">{message.error}</span>
                </p>
            )}
            {message.state === "stopped" && (
                <p className="text-[13px] text-muted-foreground">Réponse interrompue. Le copilote ne garde pas ce tour en mémoire.</p>
            )}
            {message.usage && !streaming && <UsageLine usage={message.usage} />}
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
            <span className="min-w-0 truncate italic">{last || (waiting ? "Le copilote regarde ta question…" : "Réflexion…")}</span>
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
                    placeholder="Pose ta question…"
                    aria-label="Ta question pour le copilote"
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
