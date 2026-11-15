"use client";

/**
 * Onglet « Remux » du hub Santé médiathèque (ADR-021).
 * ----------------------------------------------------------------
 * Liste complète des films dont le fichier est un remux que leur profil
 * qualité n'autorise plus, du plus lourd au plus léger, avec le total
 * récupérable. Deux actions :
 *  - « Remplacer » (une ligne ou un lot coché, 10 films au plus) : le
 *    serveur cherche un remplaçant plus léger, le met en téléchargement,
 *    puis seulement supprime le fichier du remux. Toujours après une
 *    confirmation qui récapitule le nombre de films, la place et la corbeille.
 *  - « Garder le remux » : passe le film dans un profil qui l'autorise
 *    (« films d'exception ») ; il sort alors de la liste.
 * Les films non remplaçables (non surveillés, taille incohérente pour un
 * remux) sont affichés avec la raison, sans case à cocher.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertTriangle,
    Check,
    CircleSlash,
    Feather,
    HardDrive,
    Loader2,
    ShieldCheck,
    Square,
    Trash2,
    X,
} from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
    useKeepRemux,
    useRemux,
    useReplaceRemux,
    useStopRemuxJob,
    type RemuxData,
    type RemuxItem,
    type RemuxJob,
} from "@/hooks/use-remux";
import { useUrlState } from "@/hooks/use-url-state";
import { formatBytes, plural } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { HealthTabHeader } from "./tab-header";
import { MediaRow } from "./media-row";
import { qualityBadgeClass, qualityLabel } from "./quality-utils";

/** Phrase sur la corbeille de Radarr : quand la place est réellement libérée. */
function recycleBinText(bin: RemuxData["recycle_bin"]): string {
    if (!bin.enabled) {
        return "Radarr n'a pas de corbeille réglée : les remux sont supprimés définitivement, la place est libérée tout de suite.";
    }
    const when =
        bin.cleanup_days > 0
            ? `Radarr la vide tout seul au bout de ${bin.cleanup_days} jours`
            : "Radarr ne la vide jamais tout seul";
    return `Les remux retirés partent dans la corbeille de Radarr (${bin.path}) : la place n'est libérée qu'à son vidage. ${when} ; pour libérer plus tôt, vide ce dossier à la main ou baisse le délai dans Radarr › Paramètres › Gestion des médias.`;
}

export function RemuxTab() {
    const [with1080, setWith1080] = useUrlState<"0" | "1">("r1080", "0");
    const include1080p = with1080 === "1";
    const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useRemux(include1080p);
    const replace = useReplaceRemux();
    const keep = useKeepRemux();
    const stop = useStopRemuxJob();

    const [selected, setSelected] = useState<Set<number>>(new Set());
    // Films de la confirmation en cours : conservés après fermeture pour que
    // la boîte ne se vide pas pendant son animation de sortie.
    const [toReplace, setToReplace] = useState<RemuxItem[]>([]);
    const [replaceOpen, setReplaceOpen] = useState(false);
    const [toKeep, setToKeep] = useState<RemuxItem | null>(null);
    const [keepOpen, setKeepOpen] = useState(false);
    const [keepProfile, setKeepProfile] = useState<number | null>(null);

    const items = useMemo(() => data?.items ?? [], [data]);
    const ready = useMemo(() => items.filter((i) => i.status === "ready"), [items]);
    const batchMax = data?.batch_max ?? 10;
    const running = data?.job?.state === "running";
    // Une sélection ne garde que des films encore remplaçables.
    const chosen = useMemo(() => ready.filter((i) => selected.has(i.movie_id)), [ready, selected]);
    const full = chosen.length >= batchMax;

    const toggle = (id: number) =>
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else if (next.size < batchMax) next.add(id);
            return next;
        });

    const askReplace = (list: RemuxItem[]) => {
        setToReplace(list);
        setReplaceOpen(true);
    };

    const confirmReplace = async () => {
        try {
            await replace.mutateAsync({ movieIds: toReplace.map((i) => i.movie_id), include1080p });
            setSelected(new Set());
            toast.success(`Lot lancé : ${toReplace.length} ${plural(toReplace.length, "film")}`, {
                description: "L'avancement s'affiche en haut de la liste.",
            });
        } catch (e) {
            toast.error("Lot non lancé", { description: e instanceof Error ? e.message : undefined });
            throw e; // garde la boîte ouverte
        }
    };

    const askKeep = (item: RemuxItem) => {
        const profiles = data?.keep_profiles ?? [];
        // Par défaut : le profil qui garde déjà le plus de remux (« films d'exception »).
        const preferred = [...profiles].sort((a, b) => b.remux_kept - a.remux_kept)[0];
        setKeepProfile(preferred?.id ?? null);
        setToKeep(item);
        setKeepOpen(true);
    };

    const confirmKeep = async () => {
        if (!toKeep || keepProfile === null) return;
        try {
            const done = await keep.mutateAsync({ movieIds: [toKeep.movie_id], profileId: keepProfile });
            setSelected((prev) => {
                const next = new Set(prev);
                next.delete(toKeep.movie_id);
                return next;
            });
            toast.success(`« ${toKeep.title} » garde son remux`, {
                description: `Passé au profil « ${done.profile_name} » : il ne sera plus proposé.`,
            });
        } catch (e) {
            toast.error(`Impossible de changer le profil de « ${toKeep.title} »`, {
                description: e instanceof Error ? e.message : undefined,
            });
            throw e;
        }
    };

    if (isLoading) return <RemuxSkeleton />;
    if (isError || !data) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Liste des remux indisponible" />
            </Panel>
        );
    }

    const replaceSize = toReplace.reduce((s, i) => s + i.size_bytes, 0);
    const replaceGain = toReplace.reduce((s, i) => s + i.gain_bytes, 0);

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="space-y-5">
            <motion.div variants={fadeUp}>
                <HealthTabHeader
                    icon={Feather}
                    title="Remux à alléger"
                    description="Films dont le fichier est un remux que leur profil qualité n'autorise plus. Radarr ne descend jamais en qualité tout seul : c'est ici qu'on les remplace."
                    updatedAt={dataUpdatedAt}
                    isFetching={isFetching}
                    onRescan={() => refetch()}
                >
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                        <Switch
                            checked={include1080p}
                            onCheckedChange={(v) => {
                                setSelected(new Set());
                                setWith1080(v ? "1" : "0");
                            }}
                            aria-label="Inclure les Remux-1080p"
                        />
                        Remux-1080p aussi
                    </label>
                </HealthTabHeader>
            </motion.div>

            <motion.div variants={fadeUp} className="grid gap-3 sm:grid-cols-3">
                <Figure label="Remplaçables" value={`${data.ready} ${plural(data.ready, "film")}`} />
                <Figure label="Place occupée aujourd'hui" value={formatBytes(data.size_bytes)} />
                <Figure label="Gain estimé" value={`≈ ${formatBytes(data.reclaimable_bytes)}`} tone="success" />
            </motion.div>

            {data.job && (
                <motion.div variants={fadeUp}>
                    <JobPanel job={data.job} stopping={stop.isPending} onStop={() => stop.mutate()} />
                </motion.div>
            )}

            <motion.div variants={fadeUp}>
                <Panel
                    title="Films"
                    icon={Feather}
                    bodyClassName="p-0"
                    action={
                        <div className="flex flex-wrap items-center justify-end gap-2">
                            {chosen.length > 0 && (
                                <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                                    <X /> Désélectionner
                                </Button>
                            )}
                            <Button
                                variant="outline"
                                size="sm"
                                disabled={ready.length === 0}
                                onClick={() => setSelected(new Set(ready.slice(0, batchMax).map((i) => i.movie_id)))}
                            >
                                Les {Math.min(batchMax, ready.length)} plus lourds
                            </Button>
                            <Button
                                variant="destructive"
                                size="sm"
                                disabled={chosen.length === 0 || running}
                                onClick={() => askReplace(chosen)}
                            >
                                <Trash2 />
                                Remplacer{chosen.length > 0 ? ` (${chosen.length})` : ""}
                            </Button>
                        </div>
                    }
                >
                    <p className="border-b border-white/[0.05] px-4 py-2.5 text-xs text-muted-foreground sm:px-5">
                        Coche jusqu&apos;à {batchMax} films par lot, pour ne pas saturer les indexeurs et SABnzbd.{" "}
                        {recycleBinText(data.recycle_bin)}
                    </p>
                    {items.length === 0 ? (
                        <EmptyState
                            compact
                            tone="success"
                            icon={Check}
                            title="Aucun remux à alléger"
                            description="Tous les remux présents sont dans un profil qui les autorise."
                        />
                    ) : (
                        <ul className="divide-y divide-white/[0.04]">
                            <AnimatePresence mode="popLayout" initial={false}>
                                {items.map((item) => {
                                    const isReady = item.status === "ready";
                                    const checked = selected.has(item.movie_id);
                                    return (
                                        <MediaRow
                                            key={item.movie_id}
                                            title={item.title}
                                            type="movie"
                                            posterUrl={item.poster_url}
                                            href={`/media/movie/${item.movie_id}`}
                                            meta={[item.year || "·", item.profile_name]}
                                            badges={
                                                <>
                                                    <span
                                                        className={cn(
                                                            "rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                                                            qualityBadgeClass(item.quality),
                                                        )}
                                                    >
                                                        {qualityLabel(item.quality)}
                                                    </span>
                                                    {isReady ? (
                                                        <span className="inline-flex items-center gap-1 rounded-md bg-success/15 px-1.5 py-0.5 text-[10px] font-semibold text-success">
                                                            <HardDrive className="h-3 w-3" /> ≈ {formatBytes(item.gain_bytes)} à gagner
                                                        </span>
                                                    ) : (
                                                        <span className="inline-flex items-center gap-1 rounded-md bg-warning/15 px-1.5 py-0.5 text-[10px] font-semibold text-warning">
                                                            <CircleSlash className="h-3 w-3" /> Non remplaçable
                                                        </span>
                                                    )}
                                                </>
                                            }
                                            description={item.note || undefined}
                                            size={formatBytes(item.size_bytes)}
                                            sizeClassName="text-warning"
                                            actions={
                                                <>
                                                    {isReady && (
                                                        <label className="flex h-8 w-8 cursor-pointer items-center justify-center">
                                                            <input
                                                                type="checkbox"
                                                                className="h-4 w-4 cursor-pointer accent-[#4A9EFF] disabled:cursor-not-allowed"
                                                                checked={checked}
                                                                disabled={!checked && full}
                                                                onChange={() => toggle(item.movie_id)}
                                                                aria-label={`Sélectionner ${item.title}`}
                                                            />
                                                        </label>
                                                    )}
                                                    {data.keep_profiles.length > 0 && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => askKeep(item)}
                                                            aria-label={`Garder le remux de ${item.title}`}
                                                        >
                                                            <ShieldCheck />
                                                            <span className="hidden md:inline">Garder</span>
                                                        </Button>
                                                    )}
                                                    {isReady && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon-sm"
                                                            disabled={running}
                                                            onClick={() => askReplace([item])}
                                                            aria-label={`Remplacer le remux de ${item.title}`}
                                                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                                        >
                                                            <Trash2 />
                                                        </Button>
                                                    )}
                                                </>
                                            }
                                        />
                                    );
                                })}
                            </AnimatePresence>
                        </ul>
                    )}
                </Panel>
            </motion.div>

            <ConfirmDialog
                open={replaceOpen}
                onOpenChange={setReplaceOpen}
                destructive
                title={
                    toReplace.length === 1
                        ? `Remplacer le remux de « ${toReplace[0].title} » ?`
                        : `Remplacer ${toReplace.length} remux ?`
                }
                description={`${formatBytes(replaceSize)} aujourd'hui, environ ${formatBytes(replaceGain)} à récupérer.`}
                confirmLabel={toReplace.length === 1 ? "Remplacer" : `Remplacer ${toReplace.length} films`}
                onConfirm={confirmReplace}
            >
                <ul className="space-y-1.5 rounded-xl bg-white/[0.03] p-3 text-xs text-muted-foreground ring-1 ring-white/[0.06]">
                    <li>Pour chaque film, ArrMada cherche une version plus légère acceptée par son profil et la met en téléchargement.</li>
                    <li>Le fichier du remux n&apos;est supprimé qu&apos;ensuite. Le film reste dans Radarr, surveillé.</li>
                    <li>Un film sans remplaçant plus léger chez les indexeurs garde son remux.</li>
                    <li className="text-warning">{recycleBinText(data.recycle_bin)}</li>
                </ul>
                {toReplace.length > 1 && (
                    <p className="max-h-24 overflow-y-auto text-xs text-muted-foreground">
                        {toReplace.map((i) => i.title).join(" · ")}
                    </p>
                )}
            </ConfirmDialog>

            <ConfirmDialog
                open={keepOpen}
                onOpenChange={setKeepOpen}
                title={`Garder le remux de « ${toKeep?.title ?? ""} » ?`}
                description="Le film passe dans un profil qui autorise le remux : il ne sera plus proposé ici, et aucun fichier n'est touché."
                confirmLabel="Garder le remux"
                onConfirm={confirmKeep}
            >
                <label className="block space-y-1.5 text-sm">
                    <span className="text-xs text-muted-foreground">Profil qualité</span>
                    <select
                        className="w-full rounded-xl bg-white/[0.05] px-3 py-2 text-sm ring-1 ring-white/[0.08] focus:outline-none focus:ring-2 focus:ring-ring/70"
                        value={keepProfile ?? ""}
                        onChange={(e) => setKeepProfile(Number(e.target.value))}
                    >
                        {data.keep_profiles.map((p) => (
                            <option key={p.id} value={p.id} className="bg-background">
                                {p.name}
                                {p.remux_kept > 0 ? ` (${p.remux_kept} remux déjà gardés)` : ""}
                            </option>
                        ))}
                    </select>
                </label>
            </ConfirmDialog>
        </motion.div>
    );
}

/* ── Sous-composants ───────────────────────────────────────── */

function Figure({ label, value, tone }: { label: string; value: string; tone?: "success" }) {
    return (
        <div className="glass rounded-2xl px-4 py-3">
            <p className="text-[11px] text-muted-foreground">{label}</p>
            <p className={cn("text-lg font-semibold tabular-nums tracking-tight", tone === "success" && "text-success")}>{value}</p>
        </div>
    );
}

const RESULT_STYLE = {
    replaced: { icon: Check, className: "text-success", label: "Remplacé" },
    skipped: { icon: CircleSlash, className: "text-muted-foreground", label: "Conservé" },
    error: { icon: AlertTriangle, className: "text-destructive", label: "Erreur" },
} as const;

/** Avancement du lot en cours, ou bilan du dernier. */
function JobPanel({ job, stopping, onStop }: { job: RemuxJob; stopping: boolean; onStop: () => void }) {
    const running = job.state === "running";
    const title = running
        ? `Lot en cours : ${job.done}/${job.total}`
        : job.state === "stopped"
          ? `Lot arrêté : ${job.done}/${job.total} traités`
          : `Dernier lot : ${job.replaced} ${plural(job.replaced, "remplacé")}, ${job.skipped} ${plural(job.skipped, "conservé")}`;
    return (
        <Panel
            title={title}
            icon={running ? Loader2 : Check}
            iconClassName={running ? "animate-spin text-primary" : "text-success"}
            action={
                running ? (
                    <Button variant="outline" size="sm" onClick={onStop} disabled={stopping}>
                        <Square /> Arrêter après ce film
                    </Button>
                ) : job.freed_bytes > 0 ? (
                    <span className="text-xs text-muted-foreground">{formatBytes(job.freed_bytes)} de remux retirés</span>
                ) : undefined
            }
        >
            {running && (
                <div className="mb-3 space-y-1.5">
                    <GradientProgress value={(job.done / Math.max(1, job.total)) * 100} active />
                    <p className="text-xs text-muted-foreground">
                        Recherche d&apos;un remplaçant chez les indexeurs, film par film{job.current ? ` (dernier traité : ${job.current})` : ""}.
                    </p>
                </div>
            )}
            {job.results.length > 0 && (
                <ul className="space-y-1.5">
                    {job.results.map((r, index) => {
                        const style = RESULT_STYLE[r.status];
                        return (
                            <li key={`${r.movie_id}-${index}`} className="flex items-start gap-2 text-xs">
                                <style.icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", style.className)} />
                                <span className="min-w-0">
                                    <span className="font-medium">{r.title}</span>
                                    <span className="text-muted-foreground">
                                        {" "}
                                        · {style.label} · {r.message}
                                        {r.replacement ? ` (${formatBytes(r.replacement.size_bytes)})` : ""}
                                    </span>
                                </span>
                            </li>
                        );
                    })}
                </ul>
            )}
        </Panel>
    );
}

function RemuxSkeleton() {
    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3">
                <Shimmer className="h-9 w-9 rounded-xl" />
                <div className="space-y-2">
                    <Shimmer className="h-4 w-40 rounded-md" />
                    <Shimmer className="h-3 w-72 rounded-md" />
                </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                    <Shimmer key={i} className="h-[62px] w-full rounded-2xl" />
                ))}
            </div>
            <div className="glass space-y-2 rounded-2xl p-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Shimmer key={i} className="h-[72px] w-full" />
                ))}
            </div>
        </div>
    );
}
