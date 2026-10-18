"use client";

/**
 * Onglet « Rechercher » de /search.
 * ----------------------------------------------------------------
 *  - Mode Titre : recherche live (debounce) dans la bibliothèque ET dans
 *    les catalogues Radarr/Sonarr (titres ajoutables).
 *  - Mode IA : question en langage naturel (« films de SF des années 80
 *    que je n'ai pas »), lancée sur Entrée — chaque requête coûte un appel
 *    au modèle, donc pas de recherche à chaque frappe.
 * `?q=` est lu à l'arrivée (la palette ⌘K envoie /search?q=…) et mis à
 * jour pendant la frappe : l'URL est partageable.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Brain, CheckCircle2, PenLine, Plus, Search, Sparkles, Wand2, type LucideIcon } from "lucide-react";
import { useAISearch, useDiscoverLookup, useUnifiedSearch } from "@/hooks/use-search";
import type { MediaItem } from "@/hooks/use-media";
import { useDebounce } from "@/hooks/use-debounce";
import { PosterBadge, PosterCard } from "@/components/shared/poster-card";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { PosterGridSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { EASE_OUT, fadeUp, stagger } from "@/lib/motion";
import { SegmentedControl } from "./segmented-control";
import { SearchField } from "./toolbar";
import { useParamState, writeParams } from "./use-param-state";
import { AddButton } from "./add-button";
import { fromLookup, useAdder, type AddableItem } from "./adder";
import { mediaHref, mediaKey, qualityLabel } from "./media-card";

const GRID = "grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8";

const AI_EXAMPLES = [
    "Films de science-fiction des années 80",
    "Séries en 4K que je n'ai pas finies",
    "Comédies françaises récentes",
    "Les plus gros films de ma bibliothèque",
];

export function SearchTab({
    onPreview,
    onOpenManual,
    onGoDiscover,
}: {
    onPreview: (item: AddableItem) => void;
    onOpenManual: (title?: string) => void;
    onGoDiscover: () => void;
}) {
    const params = useSearchParams();
    const urlQuery = (params.get("q") ?? "").trim();
    const [mode, setMode] = useParamState("mode", "title", ["title", "ai"] as const);
    const { stateOf, add } = useAdder();

    /* ── Mode Titre : champ ↔ ?q= ── */
    const [input, setInput] = useState(urlQuery);
    const lastSynced = useRef(urlQuery);
    const debounced = useDebounce(input.trim(), 350);
    useEffect(() => {
        // Navigation externe (palette ⌘K…) → on reprend la requête de l'URL.
        if (urlQuery !== lastSynced.current) {
            lastSynced.current = urlQuery;
            setInput(urlQuery);
        }
    }, [urlQuery]);
    useEffect(() => {
        if (mode !== "title" || debounced === lastSynced.current) return;
        lastSynced.current = debounced;
        writeParams({ q: debounced || null });
    }, [debounced, mode]);
    const titleQuery = mode === "title" ? urlQuery : "";

    /* ── Mode IA : lancé explicitement ── */
    const [aiQuery, setAiQuery] = useState("");
    const runAi = (q = input) => {
        const clean = q.trim();
        if (clean.length >= 3) setAiQuery(clean);
    };

    const library = useUnifiedSearch(titleQuery);
    const lookup = useDiscoverLookup(titleQuery, mode === "title");
    const ai = useAISearch(mode === "ai" ? aiQuery : "");

    const libraryItems: MediaItem[] = mode === "ai" ? ai.data?.items ?? [] : library.data?.library.items ?? [];
    const addable = useMemo(
        () => (mode === "title" ? (lookup.data ?? []).filter((x) => !x.in_library).map(fromLookup) : []),
        [lookup.data, mode],
    );

    const active = mode === "ai" ? aiQuery.length >= 3 : titleQuery.length >= 2;
    const loading = mode === "ai" ? ai.isLoading : (library.isLoading || lookup.isLoading) && !library.data && !lookup.data;
    const fetching = mode === "ai" ? ai.isFetching : library.isFetching || lookup.isFetching;
    // Le lookup ne lève jamais d'erreur (chaque service est rattrapé) : on ne
    // montre l'écran d'erreur que si la bibliothèque échoue ET qu'il n'y a rien à ajouter.
    const failed = mode === "ai" ? ai.isError : library.isError && addable.length === 0;
    const nothing = !loading && !failed && libraryItems.length === 0 && addable.length === 0;
    const shownQuery = mode === "ai" ? aiQuery : titleQuery;

    return (
        <motion.div variants={stagger(0, 0.08)} initial="hidden" animate="show" className="space-y-6">
            {/* ── Champ « hero » ── */}
            <motion.div variants={fadeUp} className="glass border-gradient relative overflow-hidden rounded-3xl p-4 md:p-6">
                <div aria-hidden className="pointer-events-none absolute -left-20 -top-24 h-64 w-64 rounded-full bg-brand/20 blur-3xl" />
                <div aria-hidden className="pointer-events-none absolute -bottom-24 right-0 h-56 w-72 rounded-full bg-primary/15 blur-3xl" />
                <div className="relative space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <SegmentedControl
                            layoutId="search-mode-pill"
                            ariaLabel="Mode de recherche"
                            value={mode}
                            onChange={(v) => {
                                setMode(v);
                                // ?q= ne concerne que le mode Titre. On note l'URL comme « déjà
                                // synchronisée » pour que le champ ne soit pas vidé au passage.
                                if (v === "ai") {
                                    lastSynced.current = "";
                                    writeParams({ q: null });
                                }
                            }}
                            options={[
                                { value: "title", label: "Titre", icon: Search },
                                { value: "ai", label: "IA", icon: Brain },
                            ]}
                        />
                        <p className="text-xs text-muted-foreground">
                            {mode === "ai" ? "Recherche dans ta bibliothèque, en langage naturel" : "Bibliothèque + catalogues Radarr / Sonarr"}
                        </p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row">
                        <SearchField
                            size="lg"
                            className="flex-1"
                            autoFocus
                            value={input}
                            onChange={setInput}
                            onSubmit={() => (mode === "ai" ? runAi() : undefined)}
                            loading={fetching && active}
                            ariaLabel={mode === "ai" ? "Question pour la recherche IA" : "Titre d'un film ou d'une série"}
                            placeholder={mode === "ai" ? "Ex : films de SF des années 80 que je n'ai pas…" : "Titre d'un film ou d'une série…"}
                        />
                        {mode === "ai" && (
                            <Button size="lg" onClick={() => runAi()} disabled={input.trim().length < 3 || ai.isFetching} className="h-14 rounded-2xl">
                                <Wand2 /> Analyser
                            </Button>
                        )}
                    </div>
                    <AnimatePresence initial={false} mode="wait">
                        {mode === "ai" ? (
                            <motion.div
                                key="ai-hints"
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                transition={{ duration: 0.25, ease: EASE_OUT }}
                                className="flex flex-wrap items-center gap-2"
                            >
                                <span className="eyebrow mr-1">Idées</span>
                                {AI_EXAMPLES.map((ex) => (
                                    <button
                                        key={ex}
                                        type="button"
                                        className="chip"
                                        onClick={() => {
                                            setInput(ex);
                                            runAi(ex);
                                        }}
                                    >
                                        <Sparkles className="h-3 w-3" /> {ex}
                                    </button>
                                ))}
                            </motion.div>
                        ) : (
                            <motion.p
                                key="title-hint"
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                transition={{ duration: 0.25, ease: EASE_OUT }}
                                className="text-xs text-muted-foreground"
                            >
                                Résultats en direct : ce que tu possèdes déjà, et ce que tu peux ajouter en un clic à Radarr ou Sonarr.
                            </motion.p>
                        )}
                    </AnimatePresence>
                </div>
            </motion.div>

            {/* ── Résultats ── */}
            {!active ? (
                <motion.div variants={fadeUp} className="glass rounded-2xl">
                    <EmptyState
                        icon={mode === "ai" ? Brain : Search}
                        title={mode === "ai" ? "Pose ta question à l'IA" : "Que veux-tu regarder ?"}
                        description={
                            mode === "ai"
                                ? "Décris ce que tu cherches dans ta bibliothèque : genre, époque, qualité, taille… puis appuie sur Entrée."
                                : "Tape au moins deux lettres. Pas d'idée ? Les suggestions TMDB t'attendent."
                        }
                        action={mode === "title" ? { label: "Voir les suggestions", onClick: onGoDiscover } : undefined}
                    />
                </motion.div>
            ) : loading ? (
                <PosterGridSkeleton count={14} />
            ) : failed ? (
                <div className="glass rounded-2xl">
                    <ErrorState
                        error={mode === "ai" ? ai.error : library.error}
                        onRetry={() => (mode === "ai" ? ai.refetch() : (library.refetch(), lookup.refetch()))}
                        title="La recherche a échoué"
                    />
                </div>
            ) : (
                <div className="space-y-8">
                    {/* Retour de l'IA : interprétation ou configuration manquante */}
                    {mode === "ai" && ai.data && (
                        <AiNotice available={ai.data.ai_available} error={ai.data.error} description={ai.data.description} total={ai.data.total} />
                    )}

                    {libraryItems.length > 0 && (
                        <section className="space-y-3">
                            <SectionTitle
                                icon={CheckCircle2}
                                iconClassName="text-emerald-400"
                                title="Dans ta bibliothèque"
                                count={libraryItems.length}
                            />
                            <motion.div key={`lib:${shownQuery}`} variants={stagger(0, 0.03)} initial="hidden" animate="show" className={GRID}>
                                {libraryItems.slice(0, 48).map((m) => (
                                    <PosterCard
                                        key={mediaKey(m)}
                                        title={m.title}
                                        subtitle={`${m.year ?? "—"} · ${m.type === "movie" ? "Film" : "Série"}`}
                                        posterUrl={m.poster_url}
                                        type={m.type}
                                        href={mediaHref(m)}
                                        dimmed={!m.has_file}
                                        badges={qualityLabel(m) ? <PosterBadge>{qualityLabel(m)}</PosterBadge> : undefined}
                                        corner={
                                            m.has_file ? (
                                                <PosterBadge tone="success" title="Dans ta bibliothèque">
                                                    <CheckCircle2 className="h-2.5 w-2.5" /> À toi
                                                </PosterBadge>
                                            ) : (
                                                <PosterBadge tone="danger">Manquant</PosterBadge>
                                            )
                                        }
                                    />
                                ))}
                            </motion.div>
                        </section>
                    )}

                    {addable.length > 0 && (
                        <section className="space-y-3">
                            <SectionTitle
                                icon={Plus}
                                iconClassName="text-primary"
                                title="À ajouter"
                                count={addable.length}
                                action={
                                    <Button variant="ghost" size="sm" onClick={() => onOpenManual(shownQuery)} className="text-muted-foreground">
                                        <PenLine /> Pas le bon ? Ajout manuel
                                    </Button>
                                }
                            />
                            <motion.div key={`add:${shownQuery}`} variants={stagger(0, 0.03)} initial="hidden" animate="show" className={GRID}>
                                {addable.map((it) => (
                                    <PosterCard
                                        key={it.key}
                                        title={it.title}
                                        subtitle={`${it.year ?? "—"} · ${it.type === "movie" ? "Film" : "Série"}`}
                                        posterUrl={it.poster_url}
                                        type={it.type}
                                        // Fiche détaillée (TMDB si l'ID est connu) ; le « + » ajoute sans l'ouvrir.
                                        onClick={() => onPreview(it)}
                                        badges={<PosterBadge tone={it.type === "series" ? "violet" : "primary"}>{it.type === "series" ? "Série" : "Film"}</PosterBadge>}
                                        corner={<AddButton state={stateOf(it.key)} onAdd={() => add(it)} title={it.title} />}
                                        meta={
                                            it.overview ? (
                                                <p className="line-clamp-3 text-[11px] leading-snug text-white/75">{it.overview}</p>
                                            ) : undefined
                                        }
                                    />
                                ))}
                            </motion.div>
                        </section>
                    )}

                    {nothing && (
                        <div className="glass rounded-2xl">
                            <EmptyState
                                icon={mode === "ai" ? Brain : Search}
                                title={`Rien trouvé pour « ${shownQuery} »`}
                                description={
                                    mode === "ai"
                                        ? "Aucun titre de ta bibliothèque ne correspond. Reformule ta question ou passe en mode Titre pour en ajouter."
                                        : "Ni dans ta bibliothèque, ni chez Radarr / Sonarr. Vérifie l'orthographe ou ajoute-le avec son ID exact."
                                }
                                action={mode === "title" ? { label: "Ajouter manuellement", onClick: () => onOpenManual(shownQuery) } : undefined}
                            />
                        </div>
                    )}
                </div>
            )}
        </motion.div>
    );
}

/** Titre de section avec icône, compteur et action optionnelle. */
function SectionTitle({
    icon: Icon,
    iconClassName,
    title,
    count,
    action,
}: {
    icon: LucideIcon;
    iconClassName?: string;
    title: string;
    count: number;
    action?: ReactNode;
}) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <h3 className="flex items-center gap-2 text-base font-semibold tracking-tight">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.04] ring-1 ring-white/[0.08]">
                    <Icon className={cn("h-4 w-4", iconClassName)} />
                </span>
                {title}
                <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">{count}</span>
            </h3>
            {action}
        </div>
    );
}

/** Bandeau d'interprétation de la recherche IA (ou guide de configuration). */
function AiNotice({
    available,
    error,
    description,
    total,
}: {
    available: boolean;
    error?: string;
    description?: string;
    total?: number;
}) {
    if (!available) {
        return (
            <div className="glass rounded-2xl border border-amber-500/20 p-4 text-sm">
                <p className="font-semibold text-amber-300">Recherche IA non configurée</p>
                <p className="mt-1 text-muted-foreground">
                    Ajoute <code className="kbd">OPENROUTER_API_KEY</code> dans le fichier <code className="kbd">.env</code> du backend, puis redémarre
                    le conteneur. En attendant, le mode Titre fonctionne sans IA.
                </p>
            </div>
        );
    }
    if (error) {
        return (
            <div className="glass rounded-2xl border border-red-500/20 p-4 text-sm">
                <p className="font-semibold text-red-300">L&apos;IA n&apos;a pas pu interpréter ta demande</p>
                <p className="mt-1 break-words text-muted-foreground">{error}</p>
            </div>
        );
    }
    if (!description) return null;
    return (
        <div className="glass flex items-start gap-3 rounded-2xl p-4 text-sm">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300 ring-1 ring-violet-400/30">
                <Brain className="h-4 w-4" />
            </span>
            <div>
                <p className="eyebrow">Compris comme</p>
                <p className="mt-0.5">{description}</p>
                {typeof total === "number" && total > 48 && (
                    <p className="mt-1 text-xs text-muted-foreground">{total} correspondances — les 48 premières sont affichées.</p>
                )}
            </div>
        </div>
    );
}
