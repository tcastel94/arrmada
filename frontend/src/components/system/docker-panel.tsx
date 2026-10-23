"use client";

/**
 * Onglet « Docker » de /system (ex-page /docker).
 * ----------------------------------------------------------------
 * Conteneurs Unraid liés aux services ArrMada. Corrections :
 *  - Arrêter / Redémarrer passent par une confirmation ;
 *  - chaque action affiche un toast (succès OU vraie erreur : le backend
 *    renvoie désormais une erreur HTTP au lieu d'un 200 « Failed: … ») ;
 *  - état « en cours » PAR conteneur (avant : un clic gelait tout) ;
 *  - états « en pause » et « redémarrage » distincts de « arrêté » ;
 *  - ports visibles aussi sur mobile, avec « +N » au-delà de 3 ;
 *  - une erreur de chargement n'est plus affichée « Aucun conteneur » ;
 *  - recherche, filtre par état et lien vers l'interface web du service.
 */
import { forwardRef, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Box, ExternalLink, Loader2, Pause, Play, RotateCw, Search, Square, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { StatusDot } from "@/components/fx/status-dot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDockerAction, useDockerContainers, type DockerActionName, type DockerContainer } from "@/hooks/use-docker";
import { useDebounce } from "@/hooks/use-debounce";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Segmented } from "@/components/maintenance/segmented";

type State = "running" | "paused" | "restarting" | "stopped";
type Filter = "all" | "running" | "stopped";

const STATE_META: Record<State, { label: string; dot: string; chip: string }> = {
    running: { label: "En marche", dot: "online", chip: "bg-success/15 text-success" },
    paused: { label: "En pause", dot: "warning", chip: "bg-warning/15 text-warning" },
    restarting: { label: "Redémarrage…", dot: "primary", chip: "bg-primary/15 text-primary" },
    stopped: { label: "Arrêté", dot: "offline", chip: "bg-destructive/15 text-destructive" },
};

const ACTION_META: Record<DockerActionName, { label: string; doing: string; done: string; icon: LucideIcon }> = {
    start: { label: "Démarrer", doing: "Démarrage", done: "démarré", icon: Play },
    stop: { label: "Arrêter", doing: "Arrêt", done: "arrêté", icon: Square },
    restart: { label: "Redémarrer", doing: "Redémarrage", done: "redémarré", icon: RotateCw },
};

function stateOf(c: DockerContainer): State {
    const s = (c.status || "").toLowerCase();
    if (s === "running" || s === "paused" || s === "restarting") return s;
    // Anciennes réponses : état brut Unraid.
    const raw = (c.state_raw || "").toUpperCase();
    if (raw === "PAUSED") return "paused";
    if (raw === "RESTARTING") return "restarting";
    return "stopped";
}

/** Traduit les unités d'une durée Docker (« 3 days » → « 3 j »). */
function frDuration(text: string): string {
    const unit = (u: string) => {
        const k = u.toLowerCase().replace(/s$/, "");
        return { second: "s", minute: "min", hour: "h", day: "j", week: "sem.", month: "mois", year: "an" }[k] ?? u;
    };
    return text
        .replace(/less than a second/i, "moins d'1 s")
        .replace(/about an? (\w+)/i, (_m, u: string) => `environ 1 ${unit(u)}`)
        .replace(/(\d+)\s+([a-z]+)/gi, (_m, n: string, u: string) => `${n} ${unit(u)}`);
}

/** Texte d'état Docker (« Up 3 days (healthy) ») → français. */
export function translateDockerStatus(text: string | undefined): string {
    if (!text) return "";
    let t = text.trim();
    const health = /\((healthy|unhealthy|health: starting)\)/i.exec(t)?.[1]?.toLowerCase();
    t = t.replace(/\s*\((healthy|unhealthy|health: starting|paused)\)/gi, "");
    let out = t;
    let m: RegExpExecArray | null;
    if ((m = /^up (.+)$/i.exec(t))) out = `En marche depuis ${frDuration(m[1])}`;
    else if ((m = /^exited \((\d+)\) (.+) ago$/i.exec(t))) out = `Arrêté il y a ${frDuration(m[2])} (code ${m[1]})`;
    else if ((m = /^restarting \((\d+)\) (.+) ago$/i.exec(t))) out = `Redémarre (dernier code ${m[1]}, il y a ${frDuration(m[2])})`;
    else if (/^created$/i.test(t)) out = "Créé, jamais démarré";
    if (health === "healthy") out += " · sain";
    else if (health === "unhealthy") out += " · en mauvaise santé";
    else if (health === "health: starting") out += " · vérification en cours";
    return out;
}

const MAX_PORTS = 3;

export function DockerPanel() {
    const { data, isLoading, error, refetch, isRefetchError } = useDockerContainers();
    const action = useDockerAction();
    const [search, setSearch] = useState("");
    const debounced = useDebounce(search, 200);
    const [filter, setFilter] = useState<Filter>("all");
    const [pending, setPending] = useState<Record<string, DockerActionName | undefined>>({});
    const [confirm, setConfirm] = useState<{ container: DockerContainer; action: DockerActionName } | null>(null);
    const [confirmOpen, setConfirmOpen] = useState(false);

    const containers = useMemo(() => data?.containers ?? [], [data]);
    const counts = useMemo(
        () => ({
            all: containers.length,
            running: containers.filter((c) => stateOf(c) === "running").length,
            stopped: containers.filter((c) => stateOf(c) !== "running").length,
        }),
        [containers],
    );
    const visible = useMemo(() => {
        const q = debounced.trim().toLowerCase();
        return containers
            .filter((c) => {
                const st = stateOf(c);
                if (filter === "running" && st !== "running") return false;
                if (filter === "stopped" && st === "running") return false;
                if (!q) return true;
                return [c.name, c.image, c.service_name, c.service_type].some((v) => v?.toLowerCase().includes(q));
            })
            .sort((a, b) => a.name.localeCompare(b.name, "fr"));
    }, [containers, debounced, filter]);

    const run = async (c: DockerContainer, act: DockerActionName) => {
        const meta = ACTION_META[act];
        setPending((p) => ({ ...p, [c.id]: act }));
        const id = toast.loading(`${meta.doing} de ${c.name}…`);
        try {
            await action.mutateAsync({ container_id: c.id, action: act });
            toast.success(`${c.name} ${meta.done}`, { id });
        } catch (e) {
            toast.error(`${meta.label} ${c.name} : échec`, { id, description: e instanceof Error ? e.message : undefined });
            throw e;
        } finally {
            setPending((p) => ({ ...p, [c.id]: undefined }));
        }
    };

    /** Démarrer : direct. Arrêter / redémarrer : confirmation d'abord. */
    const request = (c: DockerContainer, act: DockerActionName) => {
        if (act === "start") {
            run(c, act).catch(() => undefined);
            return;
        }
        setConfirm({ container: c, action: act });
        setConfirmOpen(true);
    };

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Shimmer className="h-10 w-full max-w-lg rounded-2xl" />
                <div className="grid gap-3 lg:grid-cols-2">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Shimmer key={i} className="h-36 rounded-2xl" />
                    ))}
                </div>
            </div>
        );
    }
    // Erreur SANS données : écran d'erreur. Si une relecture échoue alors
    // qu'on a déjà une liste, on la garde affichée avec un avertissement.
    if (!data) {
        return (
            <Panel>
                <ErrorState error={error} onRetry={() => refetch()} title="Impossible de joindre Unraid" />
                <p className="-mt-6 pb-4 text-center text-xs text-muted-foreground">
                    Vérifie l&apos;URL et la clé API Unraid dans la configuration du backend.
                </p>
            </Panel>
        );
    }

    return (
        <div className="space-y-4">
            {isRefetchError && (
                <div className="flex items-center gap-2 rounded-xl bg-warning/10 px-3 py-2 text-xs text-warning ring-1 ring-warning/20">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    Unraid ne répond plus : l&apos;état affiché date de la dernière lecture réussie.
                </div>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Segmented<Filter>
                    layoutId="docker-filter"
                    size="sm"
                    ariaLabel="Filtrer les conteneurs"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: "all", label: "Tous", count: counts.all },
                        { value: "running", label: "En marche", count: counts.running },
                        { value: "stopped", label: "Arrêtés ou en pause", count: counts.stopped },
                    ]}
                />
                <div className="relative sm:w-64">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Nom, image, service…"
                        aria-label="Chercher un conteneur"
                        className="h-8 pl-8 text-xs"
                    />
                </div>
            </div>

            {containers.length === 0 ? (
                <Panel>
                    <EmptyState
                        icon={Box}
                        title="Aucun conteneur lié à tes services"
                        description="ArrMada n'affiche que les conteneurs Unraid dont le nom contient un type de service enregistré (sonarr, radarr…)."
                    />
                </Panel>
            ) : visible.length === 0 ? (
                <Panel>
                    <EmptyState compact icon={Search} title="Aucun conteneur ne correspond" description="Change le filtre ou la recherche." />
                </Panel>
            ) : (
                <ul className="grid gap-3 lg:grid-cols-2">
                    <AnimatePresence initial={false} mode="popLayout">
                        {visible.map((c, i) => (
                            <ContainerCard key={c.id || c.name} container={c} index={i} pending={pending[c.id]} onAction={(act) => request(c, act)} />
                        ))}
                    </AnimatePresence>
                </ul>
            )}

            <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                destructive={confirm?.action === "stop"}
                title={confirm ? `${ACTION_META[confirm.action].label} ${confirm.container.name} ?` : ""}
                description={
                    confirm?.action === "stop"
                        ? `${confirm.container.service_name ?? "Le service"} sera indisponible jusqu'au prochain démarrage (téléchargements et imports en pause).`
                        : `${confirm?.container.service_name ?? "Le service"} sera coupé quelques secondes le temps du redémarrage.`
                }
                confirmLabel={confirm ? ACTION_META[confirm.action].label : "Confirmer"}
                onConfirm={() => (confirm ? run(confirm.container, confirm.action) : undefined)}
            />
        </div>
    );
}

interface ContainerCardProps {
    container: DockerContainer;
    index: number;
    pending?: DockerActionName;
    onAction: (act: DockerActionName) => void;
}

/** `forwardRef` : requis par AnimatePresence mode="popLayout". */
const ContainerCard = forwardRef<HTMLLIElement, ContainerCardProps>(function ContainerCard(
    { container: c, index, pending, onAction },
    ref,
) {
    const st = stateOf(c);
    const meta = STATE_META[st];
    const ports = c.ports ?? [];
    const statusText = translateDockerStatus(c.status_text);
    const busy = !!pending;

    return (
        <motion.li
            ref={ref}
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.35, ease: EASE_OUT, delay: Math.min(index, 12) * 0.03 }}
            className="glass glass-hover spotlight flex flex-col gap-3 rounded-2xl p-4"
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-1.5">
                        <StatusDot tone={meta.dot} size="lg" pulse={st === "running" || st === "restarting"} />
                    </span>
                    <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2">
                            <span className="truncate font-semibold">{c.name}</span>
                            {c.service_type && (
                                <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium capitalize text-muted-foreground">
                                    {c.service_type}
                                </span>
                            )}
                        </p>
                        <p className="truncate font-mono text-[11px] text-muted-foreground/80" title={c.image}>
                            {c.image}
                        </p>
                    </div>
                </div>
                <span className={cn("shrink-0 rounded-lg px-2 py-0.5 text-[11px] font-semibold", meta.chip)}>
                    {busy ? `${ACTION_META[pending].doing}…` : meta.label}
                </span>
            </div>

            {(statusText || ports.length > 0) && (
                <div className="flex flex-wrap items-center gap-1.5">
                    {statusText && (
                        <span
                            className={cn(
                                "mr-1 text-xs",
                                /unhealthy/i.test(c.status_text ?? "") ? "text-warning" : "text-muted-foreground",
                            )}
                        >
                            {statusText}
                        </span>
                    )}
                    {ports.slice(0, MAX_PORTS).map((p) => (
                        <span key={p} className="rounded-md border border-white/[0.08] px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                            {p}
                        </span>
                    ))}
                    {ports.length > MAX_PORTS && (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <button
                                    type="button"
                                    className="rounded-md border border-white/[0.08] px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
                                >
                                    +{ports.length - MAX_PORTS}
                                </button>
                            </TooltipTrigger>
                            <TooltipContent className="font-mono text-xs">{ports.slice(MAX_PORTS).join(", ")}</TooltipContent>
                        </Tooltip>
                    )}
                </div>
            )}

            <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.05] pt-3">
                {c.service_url ? (
                    <Button asChild variant="link" size="sm" className="h-auto px-0">
                        <a href={c.service_url} target="_blank" rel="noopener noreferrer">
                            <ExternalLink />
                            Ouvrir {c.service_name ?? "l'interface"}
                        </a>
                    </Button>
                ) : (
                    <span />
                )}
                <div className="flex gap-1.5">
                    {st === "stopped" ? (
                        <Button size="sm" disabled={busy} onClick={() => onAction("start")}>
                            {pending === "start" ? <Loader2 className="animate-spin" /> : <Play />}
                            Démarrer
                        </Button>
                    ) : (
                        <>
                            <Button variant="outline" size="sm" disabled={busy || st === "restarting"} onClick={() => onAction("restart")}>
                                {pending === "restart" ? <Loader2 className="animate-spin" /> : <RotateCw />}
                                Redémarrer
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() => onAction("stop")}
                                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                            >
                                {pending === "stop" ? <Loader2 className="animate-spin" /> : st === "paused" ? <Pause /> : <Square />}
                                Arrêter
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </motion.li>
    );
});
