"use client";

/**
 * Panneau « Diagnostic IA » des journaux Docker.
 * ----------------------------------------------------------------
 * Le backend envoie les erreurs/avertissements récents (dédupliqués) à
 * l'IA locale Ollama, ou à OpenRouter en secours, qui regroupe les
 * problèmes et propose une solution pour chacun.
 * États gérés : invitation → analyse en cours (~30 s, annulable, avec
 * progression estimée) → résultat (résumé + cartes par sévérité) ou
 * échec (message spécifique si aucune IA n'est joignable).
 * Le résultat survit à un changement d'onglet (cf. useLastLogAnalysis).
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, BrainCircuit, CheckCircle2, Cpu, Filter, Loader2, RotateCw, Sparkles, Wrench, X } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import {
    cancelLogAnalysis,
    isAbortError,
    useAnalyzeLogs,
    useLastLogAnalysis,
    type LogAnalysis,
    type LogProblem,
} from "@/hooks/use-docker";
import { formatNumber, plural } from "@/lib/format";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { SEVERITY_META, matchService } from "./log-meta";

/** Lignes lues par conteneur pour l'analyse (le backend accepte 20-400). */
const ANALYZE_TAIL = 150;

/** Étapes affichées pendant l'attente : rend les ~30 s moins opaques. */
const STEPS = [
    "Lecture des journaux de tes conteneurs…",
    "Tri des erreurs et des avertissements…",
    "Regroupement des messages répétés…",
    "L'IA cherche les causes probables…",
    "Rédaction des solutions…",
] as const;

const ENGINE_LABELS: Record<string, string> = {
    ollama: "IA locale (Ollama)",
    openrouter: "OpenRouter (cloud)",
};

/**
 * Le backend n'a pas d'état « aucune IA configurée » dédié : quand Ollama
 * ET OpenRouter échouent, il renvoie « Analyse IA échouée (Ollama +
 * OpenRouter) : … ». On reconnaît ce cas pour donner la marche à suivre.
 */
function isNoAiError(analysis: LogAnalysis): boolean {
    return analysis.ai_available === false || /ollama\s*\+\s*openrouter/i.test(analysis.error ?? "");
}

interface LogAnalysisPanelProps {
    /** Services présents dans le flux (pour rendre les services cités cliquables). */
    services: string[];
    /** Filtre le flux de journaux sur un service. */
    onPickService: (service: string) => void;
}

export function LogAnalysisPanel({ services, onPickService }: LogAnalysisPanelProps) {
    const analyze = useAnalyzeLogs();
    const last = useLastLogAnalysis();
    const run = () => analyze.mutate(ANALYZE_TAIL);

    const status = last?.status ?? "idle";
    const result = status === "success" ? last?.data : undefined;
    const aborted = status === "error" && isAbortError(last?.error);
    const hasOutcome = (status === "success" || status === "error") && !aborted;

    // Une seule « vue » affichée à la fois, avec fondu entre deux états.
    let view: ReactNode;
    if (status === "pending") {
        view = <AnalysisLoading startedAt={last?.submittedAt ?? Date.now()} />;
    } else if (status === "error" && !aborted) {
        view = (
            <AnalysisFailure
                title="Analyse impossible"
                message={last?.error?.message ?? "Le backend n'a pas répondu."}
                onRetry={run}
            />
        );
    } else if (result?.error) {
        view = isNoAiError(result) ? (
            <NoAiConfigured detail={result.error} onRetry={run} />
        ) : (
            <AnalysisFailure title="L'IA n'a pas pu conclure" message={result.error} onRetry={run} />
        );
    } else if (result) {
        view = <AnalysisResult analysis={result} startedAt={last?.submittedAt} services={services} onPickService={onPickService} />;
    } else {
        view = <AnalysisIntro onRun={run} aborted={aborted} />;
    }

    return (
        <Panel
            title="Diagnostic IA"
            icon={Sparkles}
            iconClassName="text-violet-300"
            action={
                hasOutcome ? (
                    <Button variant="ghost" size="sm" onClick={run} aria-label="Relancer l'analyse des journaux">
                        <RotateCw />
                        Relancer
                    </Button>
                ) : undefined
            }
        >
            <AnimatePresence mode="wait" initial={false}>
                <motion.div
                    key={status === "pending" ? "pending" : hasOutcome ? `done-${last?.submittedAt}` : "idle"}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.3, ease: EASE_OUT }}
                >
                    {view}
                </motion.div>
            </AnimatePresence>
        </Panel>
    );
}

/* ── Invitation ─────────────────────────────────────────────── */

function AnalysisIntro({ onRun, aborted }: { onRun: () => void; aborted: boolean }) {
    return (
        <div className="space-y-4">
            <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-fuchsia-500/10 text-violet-300 ring-1 ring-violet-400/25 shadow-[0_0_24px_-8px] shadow-violet-500/60">
                    <BrainCircuit className="h-5 w-5" />
                </span>
                <p className="text-sm leading-relaxed text-muted-foreground">
                    L&apos;IA lit les erreurs et avertissements récents de tes conteneurs, regroupe les messages répétés et te propose
                    une <span className="text-foreground">cause probable</span> et une <span className="text-foreground">solution</span> pour
                    chaque problème.
                </p>
            </div>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
                <li className="flex items-center gap-2">
                    <Cpu className="h-3.5 w-3.5 shrink-0 text-violet-300" />
                    IA locale Ollama en priorité, OpenRouter en secours.
                </li>
                <li className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 shrink-0 text-violet-300" />
                    Compte environ 30 secondes.
                </li>
            </ul>
            {aborted && <p className="text-xs text-muted-foreground">Analyse précédente annulée.</p>}
            <Button onClick={onRun} className="w-full sm:w-auto">
                <Sparkles />
                Analyser avec l&apos;IA
            </Button>
        </div>
    );
}

/* ── Analyse en cours ───────────────────────────────────────── */

function AnalysisLoading({ startedAt }: { startedAt: number }) {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const t = window.setInterval(() => setNow(Date.now()), 1000);
        return () => window.clearInterval(t);
    }, []);

    const elapsed = Math.max(0, Math.round((now - startedAt) / 1000));
    // Progression ESTIMÉE (on ne connaît pas la durée réelle) : courbe qui
    // ralentit à l'approche de 100 % sans jamais l'atteindre (~75 % à 30 s).
    const progress = 95 * (1 - Math.exp(-elapsed / 20));
    const step = STEPS[Math.min(STEPS.length - 1, Math.floor(elapsed / 5))];

    return (
        <div className="space-y-4" role="status" aria-live="polite">
            <div className="flex items-center gap-3">
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/35 to-fuchsia-500/15 text-violet-200 ring-1 ring-violet-400/30 animate-pulse-glow">
                    <Sparkles className="h-5 w-5 animate-spin-slow" />
                </span>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">Analyse en cours…</p>
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.p
                            key={step}
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                            transition={{ duration: 0.25 }}
                            className="truncate text-xs text-muted-foreground"
                        >
                            {step}
                        </motion.p>
                    </AnimatePresence>
                </div>
                <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground" aria-label={`${elapsed} secondes écoulées`}>
                    {elapsed} s
                </span>
            </div>
            <GradientProgress value={progress} tone="violet" active />
            {elapsed > 60 && (
                <p className="text-xs text-amber-300">
                    C&apos;est plus long que prévu : l&apos;IA locale charge peut-être son modèle en mémoire (premier appel).
                </p>
            )}
            {/* Aperçu de la forme du résultat */}
            <div className="space-y-2" aria-hidden>
                <Shimmer className="h-12 rounded-xl" />
                <Shimmer className="h-20 rounded-xl" />
                <Shimmer className="h-20 rounded-xl opacity-60" />
            </div>
            <Button variant="ghost" size="sm" onClick={cancelLogAnalysis} className="w-full sm:w-auto">
                <X />
                Annuler
            </Button>
        </div>
    );
}

/* ── Échecs ─────────────────────────────────────────────────── */

function AnalysisFailure({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
    return <EmptyState compact tone="error" icon={AlertTriangle} title={title} description={message} action={{ label: "Réessayer", onClick: onRetry }} />;
}

/** Aucune IA joignable : on explique quoi configurer, sans jargon inutile. */
function NoAiConfigured({ detail, onRetry }: { detail: string; onRetry: () => void }) {
    const code = "rounded bg-white/[0.06] px-1 font-mono text-[11px] text-foreground";
    return (
        <div className="space-y-4">
            <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/30 to-orange-500/10 text-amber-300 ring-1 ring-amber-400/25">
                    <BrainCircuit className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                    <p className="text-sm font-semibold">Aucune IA joignable</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                        ArrMada essaie d&apos;abord l&apos;IA locale Ollama, puis OpenRouter : aucun des deux n&apos;a répondu.
                    </p>
                </div>
            </div>
            <ol className="list-decimal space-y-1.5 pl-5 text-xs leading-relaxed text-muted-foreground marker:text-amber-300">
                <li>
                    IA locale : vérifie qu&apos;Ollama tourne et renseigne <code className={code}>OLLAMA_URL</code> et{" "}
                    <code className={code}>OLLAMA_MODEL</code> dans le <code className={code}>.env</code> du backend.
                </li>
                <li>
                    Ou en secours : renseigne <code className={code}>OPENROUTER_API_KEY</code> (modèle choisi via{" "}
                    <code className={code}>AI_MODEL</code>).
                </li>
                <li>Redémarre le conteneur du backend, puis relance l&apos;analyse.</li>
            </ol>
            <p className="break-words text-[11px] text-muted-foreground/70">Détail technique : {detail}</p>
            <Button variant="outline" size="sm" onClick={onRetry} className="w-full sm:w-auto">
                <RotateCw />
                Réessayer
            </Button>
        </div>
    );
}

/* ── Résultat ───────────────────────────────────────────────── */

function AnalysisResult({
    analysis,
    startedAt,
    services,
    onPickService,
}: {
    analysis: LogAnalysis;
    startedAt?: number;
    services: string[];
    onPickService: (service: string) => void;
}) {
    // Du plus critique au moins critique, puis du plus fréquent au moins fréquent.
    const problems = useMemo(
        () =>
            [...(analysis.problems ?? [])].sort(
                (a, b) => SEVERITY_META[a.severity].rank - SEVERITY_META[b.severity].rank || (b.occurrences ?? 0) - (a.occurrences ?? 0),
            ),
        [analysis.problems],
    );
    const errors = analysis.level_counts?.error ?? 0;
    const warnings = analysis.level_counts?.warning ?? 0;
    const at = startedAt ? new Date(startedAt).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : null;
    const meta = [
        analysis.analyzed_lines !== undefined ? `${plural(analysis.analyzed_lines, "ligne analysée", "lignes analysées")}` : null,
        analysis.engine ? ENGINE_LABELS[analysis.engine] ?? analysis.engine : null,
        at ? `lancée à ${at}` : null,
    ].filter(Boolean);

    return (
        <div className="space-y-4">
            {/* Synthèse */}
            <div className="rounded-xl border border-violet-400/20 bg-violet-500/[0.07] p-4">
                <p className="flex items-start gap-2.5 text-sm leading-relaxed">
                    <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-violet-300" />
                    <span>{analysis.summary || "L'IA n'a pas fourni de synthèse."}</span>
                </p>
                {(meta.length > 0 || errors + warnings > 0) && (
                    <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                        {errors > 0 && <span className="rounded-md bg-red-500/15 px-1.5 py-0.5 font-semibold text-red-300">{plural(errors, "erreur")}</span>}
                        {warnings > 0 && (
                            <span className="rounded-md bg-amber-500/15 px-1.5 py-0.5 font-semibold text-amber-300">{plural(warnings, "avertissement")}</span>
                        )}
                        {meta.length > 0 && <span>{meta.join(" · ")}</span>}
                    </div>
                )}
            </div>

            {problems.length === 0 ? (
                <EmptyState
                    compact
                    tone="success"
                    icon={CheckCircle2}
                    title="Rien d'inquiétant"
                    description="Aucun problème notable dans les journaux récents."
                />
            ) : (
                <>
                    <p className="eyebrow">{plural(problems.length, "problème détecté", "problèmes détectés")}</p>
                    <motion.ul variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-3">
                        {problems.map((p, i) => (
                            <ProblemCard key={`${p.title}-${i}`} problem={p} services={services} onPickService={onPickService} />
                        ))}
                    </motion.ul>
                </>
            )}
        </div>
    );
}

/** Un problème regroupé : sévérité, services touchés, cause, solution. */
function ProblemCard({
    problem: p,
    services,
    onPickService,
}: {
    problem: LogProblem;
    services: string[];
    onPickService: (service: string) => void;
}) {
    const sev = SEVERITY_META[p.severity];
    return (
        <motion.li variants={fadeUp} className="glass relative overflow-hidden rounded-xl p-4 pl-5">
            {/* Liseré coloré : la sévérité se lit d'un coup d'œil */}
            <span aria-hidden className={cn("absolute inset-y-0 left-0 w-1 bg-gradient-to-b", sev.bar)} />

            <div className="flex flex-wrap items-center gap-2">
                <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1", sev.chip)}>
                    <AlertTriangle className="h-3 w-3" />
                    {sev.label}
                </span>
                {p.occurrences !== undefined && (
                    <span className="text-[11px] tabular-nums text-muted-foreground" title="Nombre d'occurrences dans les journaux">
                        × {formatNumber(p.occurrences)}
                    </span>
                )}
            </div>
            <h3 className="mt-2 text-sm font-semibold leading-snug">{p.title}</h3>

            {p.services.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                    {p.services.map((name) => {
                        const match = matchService(name, services);
                        return match ? (
                            <button
                                key={name}
                                type="button"
                                onClick={() => onPickService(match)}
                                aria-label={`Voir les journaux de ${match}`}
                                title="Voir ses journaux"
                                className="chip inline-flex items-center gap-1 text-[11px]"
                            >
                                <Filter className="h-3 w-3" />
                                {name}
                            </button>
                        ) : (
                            <span key={name} className="chip text-[11px]">
                                {name}
                            </span>
                        );
                    })}
                </div>
            )}

            {p.cause && (
                <div className="mt-3">
                    <p className="eyebrow">Cause probable</p>
                    <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">{p.cause}</p>
                </div>
            )}
            {p.solution && (
                <div className="mt-3 rounded-lg bg-emerald-500/[0.07] p-3 ring-1 ring-emerald-400/15">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300">
                        <Wrench className="h-3.5 w-3.5" />
                        Solution
                    </p>
                    <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-foreground/85 [overflow-wrap:anywhere]">{p.solution}</p>
                </div>
            )}
        </motion.li>
    );
}
