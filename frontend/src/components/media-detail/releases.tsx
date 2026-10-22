"use client";

/**
 * Onglet « Releases » : recherche interactive sur les indexeurs via Radarr /
 * Sonarr, puis envoi d'une release choisie au client de téléchargement.
 * ----------------------------------------------------------------
 * Améliorations :
 *  - tri (score de formats personnalisés, taille, seeders, âge) et filtres
 *    (protocole, texte, rejetées masquées par défaut) ;
 *  - raisons de rejet visibles en dépliant la ligne ;
 *  - lignes empilées sur mobile (bouton pleine largeur) ;
 *  - après un envoi réussi, les autres boutons sont désactivés (évite le
 *    double téléchargement) et la fiche + Téléchargements sont rafraîchis ;
 *  - compteur de temps écoulé pendant la recherche (elle peut durer 2 min).
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import {
    ArrowUp,
    Check,
    ChevronDown,
    Clock,
    HardDrive,
    Loader2,
    Radar,
    RotateCw,
    Search,
    Send,
    TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ClientBadge } from "@/components/shared/download-client";
import { useGrabRelease, useMediaReleases, type Release } from "@/hooks/use-media-actions";
import type { MediaDetail } from "@/hooks/use-media";
import { useDebounce } from "@/hooks/use-debounce";
import { formatBytes } from "@/lib/format";
import { EASE_OUT, SPRING, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { ageLabel, episodeState, pad2, seasonLabel, sortSeasons } from "./labels";

type SortKey = "score" | "size" | "seeders" | "age";
type Protocol = "all" | "usenet" | "torrent";

const SORTS: { value: SortKey; label: string }[] = [
    { value: "score", label: "Meilleur score" },
    { value: "size", label: "Plus grosses" },
    { value: "seeders", label: "Plus de seeders" },
    { value: "age", label: "Plus récentes" },
];

const PAGE = 40;

/** Secondes écoulées depuis que `active` est passé à vrai. */
function useElapsed(active: boolean) {
    const [seconds, setSeconds] = useState(0);
    useEffect(() => {
        if (!active) return;
        setSeconds(0);
        const start = Date.now();
        const t = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
        return () => clearInterval(t);
    }, [active]);
    return seconds;
}

export function ReleasesTab({ media }: { media: MediaDetail }) {
    const router = useRouter();
    const isSeries = media.type === "series";
    const arr = isSeries ? "Sonarr" : "Radarr";
    const seasons = useMemo(() => sortSeasons(media.seasons ?? []), [media.seasons]);

    // Saison par défaut : la plus récente qui a des épisodes manquants, sinon la dernière.
    const defaultSeason = useMemo(() => {
        const regular = seasons.filter((s) => s.season_number > 0);
        const withMissing = [...regular].reverse().find((s) => s.episodes.some((e) => episodeState(e) === "missing"));
        return (withMissing ?? regular[regular.length - 1] ?? seasons[0])?.season_number;
    }, [seasons]);

    const [enabled, setEnabled] = useState(false);
    // "season" = pack saison (lent : éventail sur chaque épisode) ;
    // "episode" = un épisode précis (rapide) — l'échappatoire pour les très
    // grosses saisons d'anime qui expireraient sinon.
    const [mode, setMode] = useState<"season" | "episode">("season");
    const [season, setSeason] = useState<number | undefined>(isSeries ? defaultSeason : undefined);
    const [episodeId, setEpisodeId] = useState<number | undefined>(undefined);

    const episodes = isSeries ? seasons.find((s) => s.season_number === season)?.episodes ?? [] : [];
    // Épisode par défaut : le premier manquant de la saison, sinon le premier.
    const effectiveEpisode =
        episodeId ?? (episodes.find((e) => episodeState(e) === "missing") ?? episodes[0])?.id;

    const releases = useMediaReleases(
        media.type,
        media.id,
        enabled,
        mode === "season" ? season : undefined,
        mode === "episode" ? effectiveEpisode : undefined,
    );
    const elapsed = useElapsed(releases.isFetching);
    const grab = useGrabRelease();
    const [grabbing, setGrabbing] = useState<string | null>(null);
    const [grabbed, setGrabbed] = useState<string | null>(null);

    // Filtres / tri
    const [sort, setSort] = useState<SortKey>("score");
    const [protocol, setProtocol] = useState<Protocol>("all");
    const [showRejected, setShowRejected] = useState(false);
    const [query, setQuery] = useState("");
    const debounced = useDebounce(query, 250);
    const [limit, setLimit] = useState(PAGE);

    const canSearch = !isSeries || (mode === "season" ? season !== undefined : effectiveEpisode !== undefined);

    /** Tout changement de cible impose une nouvelle recherche explicite. */
    const resetSearch = () => {
        setEnabled(false);
        setGrabbed(null);
        setLimit(PAGE);
    };

    const items = useMemo(() => releases.data?.items ?? [], [releases.data]);
    const rejectedCount = items.filter((r) => r.rejected).length;
    const protocols = useMemo(() => new Set(items.map((r) => r.protocol)), [items]);

    const visible = useMemo(() => {
        const q = debounced.trim().toLowerCase();
        const list = items.filter(
            (r) =>
                (showRejected || !r.rejected) &&
                (protocol === "all" || r.protocol === protocol) &&
                (!q || r.title.toLowerCase().includes(q) || r.indexer.toLowerCase().includes(q)),
        );
        const sorted = [...list];
        sorted.sort((a, b) => {
            switch (sort) {
                case "size":
                    return (b.size_bytes || 0) - (a.size_bytes || 0);
                case "seeders":
                    return (b.seeders ?? -1) - (a.seeders ?? -1);
                case "age":
                    return (a.age_days ?? 0) - (b.age_days ?? 0);
                default:
                    // Score CF décroissant, puis acceptées avant rejetées, puis seeders.
                    return (
                        Number(a.rejected) - Number(b.rejected) ||
                        (b.custom_format_score || 0) - (a.custom_format_score || 0) ||
                        (b.seeders ?? 0) - (a.seeders ?? 0)
                    );
            }
        });
        return sorted;
    }, [items, showRejected, protocol, debounced, sort]);

    const handleGrab = (r: Release) => {
        setGrabbing(r.guid);
        grab.mutate(
            { type: media.type, id: media.id, guid: r.guid, indexer_id: r.indexer_id, title: media.title, release_title: r.title },
            {
                onSuccess: () => {
                    setGrabbed(r.guid);
                    toast.success("Release envoyée au client de téléchargement", {
                        description: r.title,
                        action: { label: "Voir", onClick: () => router.push("/downloads") },
                    });
                },
                onError: (e) => toast.error("Envoi impossible", { description: e.message }),
                onSettled: () => setGrabbing(null),
            },
        );
    };

    const launch = () => {
        if (!enabled) setEnabled(true);
        else releases.refetch();
        setGrabbed(null);
        setLimit(PAGE);
    };

    return (
        <div className="space-y-4">
            {/* ── Cible + lancement ─────────────────────────────── */}
            <div className="glass space-y-4 rounded-2xl p-4">
                <p className="text-sm text-muted-foreground">
                    Interroge les indexeurs via {arr} et choisis toi-même la release à télécharger.
                    {isSeries && " Le pack saison est complet mais lent ; l'épisode seul est bien plus rapide sur les grosses saisons."}
                </p>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                    {isSeries && (
                        <>
                            {/* Mode : segmenté avec indicateur animé */}
                            <div className="space-y-1.5">
                                <span className="eyebrow block">Mode</span>
                                <div role="radiogroup" aria-label="Mode de recherche" className="inline-flex rounded-xl border border-white/[0.08] bg-background/50 p-1">
                                    {(["season", "episode"] as const).map((m) => (
                                        <button
                                            key={m}
                                            type="button"
                                            role="radio"
                                            aria-checked={mode === m}
                                            onClick={() => {
                                                setMode(m);
                                                resetSearch();
                                            }}
                                            className={cn(
                                                "relative rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                                                mode === m ? "text-primary" : "text-muted-foreground hover:text-foreground",
                                            )}
                                        >
                                            {mode === m && (
                                                <motion.span
                                                    layoutId="release-mode-pill"
                                                    transition={SPRING}
                                                    className="absolute inset-0 rounded-lg bg-primary/15"
                                                />
                                            )}
                                            <span className="relative">{m === "season" ? "Pack saison" : "Épisode"}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="space-y-1.5 lg:w-44">
                                <Label htmlFor="release-season" className="eyebrow block">
                                    Saison
                                </Label>
                                <Select
                                    value={season !== undefined ? String(season) : undefined}
                                    onValueChange={(v) => {
                                        setSeason(Number(v));
                                        setEpisodeId(undefined);
                                        resetSearch();
                                    }}
                                >
                                    <SelectTrigger id="release-season">
                                        <SelectValue placeholder="Aucune saison" />
                                    </SelectTrigger>
                                    <SelectContent className="max-h-72">
                                        {seasons.map((s) => (
                                            <SelectItem key={s.season_number} value={String(s.season_number)}>
                                                {seasonLabel(s.season_number)}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            {mode === "episode" && (
                                <div className="min-w-0 space-y-1.5 lg:w-72">
                                    <Label htmlFor="release-episode" className="eyebrow block">
                                        Épisode
                                    </Label>
                                    <Select
                                        value={effectiveEpisode !== undefined ? String(effectiveEpisode) : undefined}
                                        onValueChange={(v) => {
                                            setEpisodeId(Number(v));
                                            resetSearch();
                                        }}
                                    >
                                        <SelectTrigger id="release-episode">
                                            <SelectValue placeholder="Aucun épisode" />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-72">
                                            {episodes.map((ep) => {
                                                const st = episodeState(ep);
                                                return (
                                                    <SelectItem key={ep.id} value={String(ep.id)}>
                                                        E{pad2(ep.episode_number)}
                                                        {ep.title ? ` — ${ep.title}` : ""}
                                                        {st === "present" ? " · présent" : st === "upcoming" ? " · à venir" : ""}
                                                    </SelectItem>
                                                );
                                            })}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </>
                    )}
                    <Button
                        size="lg"
                        variant={enabled ? "outline" : "default"}
                        className="lg:ml-auto"
                        disabled={releases.isFetching || !canSearch}
                        onClick={launch}
                    >
                        {releases.isFetching ? <Loader2 className="animate-spin" /> : enabled ? <RotateCw /> : <Search />}
                        {releases.isFetching ? `Recherche… ${elapsed} s` : enabled ? "Relancer" : "Lancer la recherche"}
                    </Button>
                </div>
            </div>

            {/* ── Résultats ─────────────────────────────────────── */}
            {!enabled ? (
                <EmptyState
                    icon={Radar}
                    title="Recherche interactive"
                    description={`Lance la recherche pour voir toutes les releases proposées par tes indexeurs, avec le score ${arr} de chacune.`}
                    action={canSearch ? { label: "Lancer la recherche", onClick: launch } : undefined}
                />
            ) : releases.isError ? (
                <ErrorState error={releases.error} onRetry={() => releases.refetch()} title="La recherche a échoué" />
            ) : releases.isFetching && !releases.data ? (
                <div className="space-y-2" aria-live="polite">
                    <p className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden />
                        Interrogation des indexeurs… {elapsed} s
                        {isSeries && mode === "season" && elapsed > 20 && " (un pack saison peut prendre jusqu'à 4 min)"}
                    </p>
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Shimmer key={i} className="h-24 w-full rounded-2xl sm:h-[4.5rem]" />
                    ))}
                </div>
            ) : items.length === 0 ? (
                <EmptyState compact icon={Search} title="Aucune release trouvée" description="Aucun indexeur n'a renvoyé de résultat. Réessaie plus tard ou vérifie tes indexeurs." />
            ) : (
                <div className="space-y-3">
                    {/* Barre de filtres */}
                    <div className="flex flex-col gap-3 md:flex-row md:items-center">
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Filtrer par titre ou indexeur…"
                            aria-label="Filtrer les releases"
                            className="md:max-w-xs"
                        />
                        <div className="flex flex-wrap items-center gap-2">
                            {(["all", "usenet", "torrent"] as const)
                                .filter((p) => p === "all" || protocols.has(p))
                                .map((p) => (
                                    <button
                                        key={p}
                                        type="button"
                                        className="chip"
                                        data-active={protocol === p}
                                        aria-pressed={protocol === p}
                                        onClick={() => setProtocol(p)}
                                    >
                                        {p === "all" ? "Tous" : p === "usenet" ? "Usenet" : "Torrent"}
                                    </button>
                                ))}
                        </div>
                        <div className="flex flex-wrap items-center gap-3 md:ml-auto">
                            {rejectedCount > 0 && (
                                <div className="flex items-center gap-2">
                                    <Switch id="show-rejected" checked={showRejected} onCheckedChange={setShowRejected} />
                                    <Label htmlFor="show-rejected" className="cursor-pointer text-xs text-muted-foreground">
                                        Rejetées ({rejectedCount})
                                    </Label>
                                </div>
                            )}
                            <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
                                <SelectTrigger className="w-44" aria-label="Trier les releases">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {SORTS.map((s) => (
                                        <SelectItem key={s.value} value={s.value}>
                                            {s.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <p className="text-xs text-muted-foreground" aria-live="polite">
                        {visible.length} release{visible.length > 1 ? "s" : ""} affichée{visible.length > 1 ? "s" : ""} sur {items.length}
                        {!showRejected && rejectedCount > 0 && ` · ${rejectedCount} rejetée${rejectedCount > 1 ? "s" : ""} masquée${rejectedCount > 1 ? "s" : ""}`}
                        {releases.isFetching && " · actualisation…"}
                    </p>

                    {visible.length === 0 ? (
                        <EmptyState compact icon={Search} title="Aucune release ne correspond aux filtres" />
                    ) : (
                        <motion.ul variants={stagger(0, 0.03)} initial="hidden" animate="show" className="space-y-2">
                            {visible.slice(0, limit).map((r, i) => (
                                <ReleaseRow
                                    key={r.guid}
                                    release={r}
                                    animate={i < 15}
                                    arr={arr}
                                    grabbing={grabbing === r.guid}
                                    grabbed={grabbed === r.guid}
                                    locked={!!grabbing || (!!grabbed && grabbed !== r.guid)}
                                    onGrab={() => handleGrab(r)}
                                />
                            ))}
                        </motion.ul>
                    )}
                    {visible.length > limit && (
                        <div className="flex justify-center">
                            <Button variant="outline" onClick={() => setLimit((l) => l + PAGE)}>
                                Afficher {Math.min(PAGE, visible.length - limit)} de plus
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function ScoreBadge({ score }: { score: number }) {
    return (
        <span
            className={cn(
                "inline-flex items-center rounded-md border px-1.5 py-px text-[10px] font-bold tabular-nums",
                score > 0 && "border-success/30 bg-success/10 text-success",
                score < 0 && "border-destructive/30 bg-destructive/10 text-destructive",
                score === 0 && "border-white/10 text-muted-foreground",
            )}
            title="Score des formats personnalisés"
        >
            Score {score > 0 ? `+${score}` : score}
        </span>
    );
}

function ReleaseRow({
    release: r,
    animate,
    arr,
    grabbing,
    grabbed,
    locked,
    onGrab,
}: {
    release: Release;
    animate: boolean;
    arr: string;
    grabbing: boolean;
    grabbed: boolean;
    locked: boolean;
    onGrab: () => void;
}) {
    const [showReasons, setShowReasons] = useState(false);
    const isTorrent = r.protocol === "torrent";
    const reasonsId = `reasons-${r.guid}`;

    return (
        <motion.li
            variants={animate ? fadeUp : undefined}
            className={cn(
                "glass glass-hover rounded-2xl p-3 sm:p-4",
                grabbed && "border-success/40",
                r.rejected && !grabbed && "opacity-80",
            )}
        >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1 space-y-2">
                    <p className="line-clamp-2 text-sm font-medium leading-snug [overflow-wrap:anywhere]" title={r.title}>
                        {r.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                        <Badge variant="default" className="px-1.5 py-px text-[10px]">
                            {r.quality}
                        </Badge>
                        <ClientBadge protocol={r.protocol} client={isTorrent ? "Torrent" : r.protocol === "usenet" ? "Usenet" : r.protocol} />
                        <ScoreBadge score={r.custom_format_score || 0} />
                        <span className="rounded-md bg-white/[0.05] px-1.5 py-px">{r.indexer}</span>
                        <span className="flex items-center gap-1">
                            <HardDrive className="h-3 w-3" aria-hidden /> {formatBytes(r.size_bytes)}
                        </span>
                        {isTorrent && (
                            <span className={cn("flex items-center gap-1", (r.seeders ?? 0) === 0 && "text-warning")}>
                                <ArrowUp className="h-3 w-3" aria-hidden /> {r.seeders ?? 0} seeder{(r.seeders ?? 0) > 1 ? "s" : ""}
                            </span>
                        )}
                        <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" aria-hidden /> {ageLabel(r.age_days)}
                        </span>
                    </div>
                    {r.custom_formats.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                            {r.custom_formats.slice(0, 6).map((cf) => (
                                <span key={cf} className="rounded-full bg-primary/10 px-2 py-px text-[10px] text-primary/90">
                                    {cf}
                                </span>
                            ))}
                            {r.custom_formats.length > 6 && (
                                <span className="px-1 text-[10px] text-muted-foreground" title={r.custom_formats.slice(6).join(", ")}>
                                    +{r.custom_formats.length - 6}
                                </span>
                            )}
                        </div>
                    )}
                    {r.rejected && (
                        <div>
                            <button
                                type="button"
                                onClick={() => setShowReasons((v) => !v)}
                                aria-expanded={showReasons}
                                aria-controls={reasonsId}
                                className="inline-flex items-center gap-1.5 rounded-md text-xs font-medium text-warning hover:text-warning"
                            >
                                <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
                                Rejetée par {arr} ({r.rejections.length} raison{r.rejections.length > 1 ? "s" : ""})
                                <ChevronDown className={cn("h-3 w-3 transition-transform", showReasons && "rotate-180")} aria-hidden />
                            </button>
                            <AnimatePresence initial={false}>
                                {showReasons && (
                                    <motion.ul
                                        id={reasonsId}
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: "auto", opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.25, ease: EASE_OUT }}
                                        className="mt-1.5 list-disc space-y-0.5 overflow-hidden pl-5 text-xs text-warning/80"
                                    >
                                        {r.rejections.length > 0 ? r.rejections.map((reason) => <li key={reason}>{reason}</li>) : <li>Raison non précisée</li>}
                                    </motion.ul>
                                )}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
                <Button
                    className="w-full shrink-0 sm:w-auto"
                    variant={grabbed ? "secondary" : r.rejected ? "outline" : "default"}
                    disabled={grabbing || grabbed || locked}
                    onClick={onGrab}
                    title={r.rejected ? `${arr} l'a rejetée : la récupérer force le téléchargement` : undefined}
                >
                    {grabbing ? <Loader2 className="animate-spin" /> : grabbed ? <Check className="text-success" /> : <Send />}
                    {grabbed ? "Envoyée" : "Récupérer"}
                </Button>
            </div>
        </motion.li>
    );
}
