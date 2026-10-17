"use client";

/**
 * Journaux Docker agrégés + diagnostic IA (onglet « Docker » de /system).
 * ----------------------------------------------------------------
 * Porté de l'ancienne page /docker développée sur le serveur, adapté au
 * design system :
 *  - flux de toutes les lignes récentes des conteneurs de tes services,
 *    rafraîchi toutes les 10 s, avec pause ;
 *  - filtre par niveau (seuil : « Avertissements » montre aussi les
 *    erreurs, comme `journalctl -p warning`) et par service ;
 *  - défilement automatique « intelligent » : on reste collé en bas
 *    pour suivre le direct, SAUF si tu es remonté lire une ligne (sinon
 *    chaque rafraîchissement te ramènerait en bas en pleine lecture) ;
 *  - heures affichées en heure locale (le backend fournit de l'UTC) ;
 *  - à côté, le panneau « Diagnostic IA » (log-analysis.tsx). Cliquer un
 *    service cité par l'IA filtre le flux sur ce service.
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowDown, Pause, Play, RefreshCw, ScrollText, SearchX } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Segmented } from "@/components/maintenance/segmented";
import { useMediaQuery } from "@/components/calendar/use-media-query";
import { useDockerLogs, type DockerLogEntry, type DockerLogLevel } from "@/hooks/use-docker";
import { formatLongDateTime, formatNumber, plural } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { LEVEL_META, logClock, logDate, serviceTone } from "./log-meta";
import { LogAnalysisPanel } from "./log-analysis";

type LevelFilter = "error" | "warning" | "info" | "all";

/** Niveaux acceptés par chaque filtre (logique de seuil). */
const LEVEL_FILTERS: Record<LevelFilter, readonly DockerLogLevel[]> = {
    error: ["error"],
    warning: ["error", "warning"],
    info: ["error", "warning", "info"],
    all: ["error", "warning", "info", "other"],
};

/** Valeur sentinelle du Select (Radix interdit la chaîne vide). */
const ALL_SERVICES = "__all__";

/**
 * useLayoutEffect côté navigateur, useEffect côté serveur : React 18
 * avertit si useLayoutEffect est appelé pendant le rendu serveur.
 */
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

/** Tolérance (px) pour considérer qu'on est « en bas » du flux. */
const BOTTOM_SLACK = 40;

interface LogLine extends DockerLogEntry {
    key: string;
    clock: string;
    title: string;
}

/**
 * Section complète : flux + diagnostic. Possède les états partagés
 * (service filtré, pause) pour que le panneau IA puisse piloter le flux.
 */
export function DockerLogsSection() {
    const [live, setLive] = useState(true);
    const [service, setService] = useState<string>(ALL_SERVICES);
    const logs = useDockerLogs({ live });
    const streamRef = useRef<HTMLDivElement>(null);

    // Services présents dans les journaux, avec leur nombre de lignes.
    const services = useMemo(() => {
        const counts = new Map<string, number>();
        for (const l of logs.data?.logs ?? []) counts.set(l.service, (counts.get(l.service) ?? 0) + 1);
        return Array.from(counts, ([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name, "fr"));
    }, [logs.data]);

    const pickService = (name: string) => {
        setService(name);
        // Sur mobile le flux est au-dessus du diagnostic : on y remonte.
        streamRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    return (
        <section aria-label="Journaux et diagnostic des conteneurs" className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <div ref={streamRef} className="min-w-0 scroll-mt-24">
                <LogStream
                    query={logs}
                    live={live}
                    onToggleLive={() => setLive((v) => !v)}
                    service={service}
                    onServiceChange={setService}
                    services={services}
                />
            </div>
            <div className="min-w-0">
                <LogAnalysisPanel services={services.map((s) => s.name)} onPickService={pickService} />
            </div>
        </section>
    );
}

/* ── Flux de journaux ───────────────────────────────────────── */

interface LogStreamProps {
    query: ReturnType<typeof useDockerLogs>;
    live: boolean;
    onToggleLive: () => void;
    service: string;
    onServiceChange: (service: string) => void;
    services: { name: string; count: number }[];
}

function LogStream({ query, live, onToggleLive, service, onServiceChange, services }: LogStreamProps) {
    const { data, isLoading, error, refetch, isFetching, isRefetchError } = query;
    const [level, setLevel] = useState<LevelFilter>("all");
    // Sous ~440 px, « Avertissements » + compteurs dépasserait de l'écran.
    const roomy = useMediaQuery("(min-width: 440px)") !== false;

    // Lignes triées de la plus ANCIENNE à la plus récente (sens de lecture
    // d'un terminal), avec une clé stable et l'heure locale pré-calculée.
    const allLines = useMemo<LogLine[]>(() => {
        const now = new Date();
        const seen = new Map<string, number>();
        return [...(data?.logs ?? [])]
            .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
            .map((l) => {
                // Deux lignes peuvent partager horodatage + conteneur : suffixe d'unicité.
                const base = `${l.ts}|${l.container}`;
                const n = seen.get(base) ?? 0;
                seen.set(base, n + 1);
                return { ...l, key: n ? `${base}|${n}` : base, clock: logClock(l, now), title: formatLongDateTime(logDate(l)) };
            });
    }, [data]);

    const byService = useMemo(
        () => (service === ALL_SERVICES ? allLines : allLines.filter((l) => l.service === service)),
        [allLines, service],
    );
    const counts = useMemo(() => {
        const c: Record<DockerLogLevel, number> = { error: 0, warning: 0, info: 0, other: 0 };
        for (const l of byService) c[l.level]++;
        return c;
    }, [byService]);
    const lines = useMemo(() => {
        const accepted = LEVEL_FILTERS[level];
        return byService.filter((l) => accepted.includes(l.level));
    }, [byService, level]);

    /* ── Défilement automatique intelligent ────────────────────── */
    const viewportRef = useRef<HTMLDivElement>(null);
    // Ref (et non state) : lue pendant le rendu des nouvelles lignes, sans re-rendu.
    const stickRef = useRef(true);
    const seenKeysRef = useRef<Set<string>>(new Set());
    const [detached, setDetached] = useState(false);
    const [unseen, setUnseen] = useState(0);

    const scrollToBottom = (smooth = false) => {
        const el = viewportRef.current;
        if (!el) return;
        stickRef.current = true;
        setDetached(false);
        setUnseen(0);
        el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    };

    const onScroll = () => {
        const el = viewportRef.current;
        if (!el) return;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_SLACK;
        stickRef.current = atBottom;
        setDetached(!atBottom);
        if (atBottom) setUnseen(0);
    };

    // Effet « layout » : on recale le défilement AVANT que le navigateur
    // peigne, donc sans « saut » visible quand de nouvelles lignes arrivent.
    useIsomorphicLayoutEffect(() => {
        const prev = seenKeysRef.current;
        let added = 0;
        for (const l of lines) if (!prev.has(l.key)) added++;
        seenKeysRef.current = new Set(lines.map((l) => l.key));
        const el = viewportRef.current;
        if (!el) return;
        if (stickRef.current) el.scrollTop = el.scrollHeight;
        else if (added > 0 && prev.size > 0) setUnseen((u) => u + added);
    }, [lines]);

    // Changer de filtre = nouvelle vue : on repart du bas.
    const changeLevel = (v: LevelFilter) => {
        stickRef.current = true;
        setUnseen(0);
        setLevel(v);
    };
    const changeService = (v: string) => {
        stickRef.current = true;
        setUnseen(0);
        onServiceChange(v);
    };
    const resetFilters = () => {
        changeLevel("all");
        changeService(ALL_SERVICES);
    };

    const filtered = level !== "all" || service !== ALL_SERVICES;

    return (
        <Panel
            title="Journaux"
            icon={ScrollText}
            iconClassName="text-sky-300"
            bodyClassName="p-0"
            action={
                <>
                    <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex" aria-live="polite">
                        <StatusDot tone={!live ? "unknown" : isRefetchError ? "warning" : "online"} pulse={live && !isRefetchError} size="sm" />
                        {live ? "En direct" : "En pause"}
                    </span>
                    <Button
                        variant={live ? "ghost" : "glow"}
                        size="icon-sm"
                        onClick={onToggleLive}
                        aria-pressed={!live}
                        aria-label={live ? "Mettre le flux en pause" : "Reprendre le flux en direct"}
                        title={live ? "Pause" : "Reprendre"}
                    >
                        {live ? <Pause /> : <Play />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => refetch()}
                        disabled={isFetching}
                        aria-label="Relire les journaux maintenant"
                        title="Relire maintenant"
                    >
                        <RefreshCw className={cn(isFetching && "animate-spin")} />
                    </Button>
                </>
            }
        >
            {/* Barre de filtres */}
            <div className="flex flex-col gap-2.5 border-b border-white/[0.05] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                <Segmented<LevelFilter>
                    layoutId="docker-log-level"
                    size="sm"
                    ariaLabel="Filtrer par niveau"
                    value={level}
                    onChange={changeLevel}
                    options={[
                        { value: "error", label: "Erreurs", count: counts.error, hint: "Erreurs uniquement" },
                        { value: "warning", label: roomy ? "Avertissements" : "Avert.", count: counts.warning + counts.error, hint: "Avertissements et erreurs" },
                        { value: "info", label: "Info", hint: "Info, avertissements et erreurs (sans les lignes non classées)" },
                        { value: "all", label: "Tout", hint: "Toutes les lignes" },
                    ]}
                />
                <Select value={service} onValueChange={changeService} disabled={services.length === 0 && service === ALL_SERVICES}>
                    <SelectTrigger className="h-8 text-xs sm:w-52" aria-label="Filtrer par service">
                        <SelectValue placeholder="Tous les services" />
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                        <SelectItem value={ALL_SERVICES}>Tous les services</SelectItem>
                        {/* Service choisi mais sorti du flux (lignes trop anciennes) : on le garde listé. */}
                        {service !== ALL_SERVICES && !services.some((s) => s.name === service) && (
                            <SelectItem value={service}>{service}</SelectItem>
                        )}
                        {services.map((s) => (
                            <SelectItem key={s.name} value={s.name}>
                                {s.name} <span className="text-muted-foreground">· {formatNumber(s.count)}</span>
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {isRefetchError && data && (
                <p className="flex items-center gap-2 border-b border-amber-400/10 bg-amber-500/[0.07] px-4 py-2 text-xs text-amber-300 sm:px-5">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    Le flux ne répond plus : tu vois les dernières lignes lues.
                </p>
            )}

            {/* Zone de lecture */}
            <div className="relative">
                {isLoading ? (
                    <div className="h-[min(62vh,480px)] space-y-2.5 overflow-hidden p-4 sm:px-5" aria-busy="true" aria-label="Chargement des journaux">
                        {Array.from({ length: 14 }).map((_, i) => (
                            <Shimmer key={i} className="h-3.5 rounded-md" />
                        ))}
                    </div>
                ) : !data ? (
                    <div className="px-4">
                        <ErrorState compact error={error} onRetry={() => refetch()} title="Journaux indisponibles" />
                        <p className="-mt-4 pb-6 text-center text-xs text-muted-foreground">
                            Le backend lit les journaux via le socket Docker : vérifie que{" "}
                            <code className="rounded bg-white/[0.06] px-1 font-mono text-[11px]">/var/run/docker.sock</code> est monté dans son conteneur.
                        </p>
                    </div>
                ) : allLines.length === 0 ? (
                    <EmptyState
                        compact
                        icon={ScrollText}
                        title="Aucune ligne récente"
                        description="Tes conteneurs n'ont rien écrit récemment, ou le socket Docker (/var/run/docker.sock) n'est pas monté dans le conteneur du backend."
                    />
                ) : lines.length === 0 ? (
                    <EmptyState
                        compact
                        icon={SearchX}
                        title={level === "error" ? "Aucune erreur récente" : "Aucune ligne pour ce filtre"}
                        tone={level === "error" ? "success" : "default"}
                        description={level === "error" ? "Bonne nouvelle : aucune erreur dans les dernières lignes lues." : "Élargis le niveau ou choisis un autre service."}
                        action={{ label: "Tout afficher", onClick: resetFilters }}
                    />
                ) : (
                    <>
                        <div
                            ref={viewportRef}
                            onScroll={onScroll}
                            role="log"
                            // Pas d'annonce vocale à chaque rafraîchissement (illisible).
                            aria-live="off"
                            aria-label="Journaux des conteneurs, du plus ancien au plus récent"
                            tabIndex={0}
                            className="h-[min(62vh,480px)] overflow-y-auto overscroll-contain py-2 font-mono text-[11.5px] leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40"
                        >
                            <ul>
                                {lines.map((l) => (
                                    <LogRow key={l.key} line={l} onPickService={changeService} />
                                ))}
                            </ul>
                        </div>

                        {/* Bouton « revenir au direct » quand on est remonté */}
                        <AnimatePresence>
                            {detached && (
                                <motion.div
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 8 }}
                                    transition={{ duration: 0.25, ease: EASE_OUT }}
                                    className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center"
                                >
                                    <JumpButton unseen={unseen} onClick={() => scrollToBottom(true)} />
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </>
                )}
            </div>

            {data && allLines.length > 0 && (
                <p className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-white/[0.05] px-4 py-2 text-[11px] text-muted-foreground sm:px-5">
                    <span>
                        {filtered ? `${formatNumber(lines.length)} sur ${plural(allLines.length, "ligne")}` : plural(allLines.length, "ligne")} · heure locale
                    </span>
                    <span>{live ? "Rafraîchi toutes les 10 s" : "Flux en pause"}</span>
                </p>
            )}
        </Panel>
    );
}

/** Une ligne de journal : pastille de niveau, heure, service, message. */
function LogRow({ line: l, onPickService }: { line: LogLine; onPickService: (service: string) => void }) {
    const meta = LEVEL_META[l.level];
    return (
        <li className={cn("flex gap-2.5 px-4 py-1 transition-colors hover:bg-white/[0.03] sm:px-5", meta.row)}>
            <span aria-hidden className={cn("mt-[0.5em] h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
            {/* Mobile : heure + service au-dessus du message ; desktop : en colonnes. */}
            <div className="min-w-0 flex-1 sm:flex sm:gap-3">
                <div className="flex min-w-0 shrink-0 items-baseline gap-2 sm:w-44">
                    <time dateTime={l.ts} title={l.title} className="shrink-0 tabular-nums text-muted-foreground/60">
                        {l.clock}
                    </time>
                    <button
                        type="button"
                        onClick={() => onPickService(l.service)}
                        title={`Conteneur ${l.container} — cliquer pour ne voir que ${l.service}`}
                        aria-label={`Filtrer sur ${l.service}`}
                        className={cn("min-w-0 truncate rounded font-semibold hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60", serviceTone(l.service))}
                    >
                        {l.service}
                    </button>
                </div>
                <p className={cn("min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]", meta.text)}>
                    {meta.short && <span className="sr-only">{meta.label} : </span>}
                    {l.message}
                </p>
            </div>
        </li>
    );
}

/** « Revenir au direct », avec le nombre de lignes arrivées entre-temps. */
function JumpButton({ unseen, onClick }: { unseen: number; onClick: () => void }) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="glass-strong pointer-events-auto flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium text-foreground shadow-[0_8px_24px_-8px_hsl(var(--primary)/0.6)] ring-1 ring-primary/30 transition-colors hover:text-primary"
        >
            <ArrowDown className="h-3.5 w-3.5" />
            {unseen > 0 ? plural(unseen, "nouvelle ligne", "nouvelles lignes") : "Revenir au direct"}
        </button>
    );
}
