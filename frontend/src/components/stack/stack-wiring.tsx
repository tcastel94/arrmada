"use client";

/**
 * Auto-configuration de la stack : lecture des clés + câblage des applis.
 * ----------------------------------------------------------------
 * Utilisé par Paramètres → Auto-configuration ET par l'assistant
 * d'installation (étape Découverte).
 *  1. « Analyser » : ArrMada lit les fichiers de config (appdata monté en
 *     lecture seule), trouve l'adresse de chaque appli et liste les
 *     actions : à faire (cochées), déjà en place, ou bloquées (+ raison).
 *  2. « Appliquer » : exécute les actions cochées une par une. Chaque
 *     ajout est d'abord TESTÉ par l'appli cible (Sonarr teste lui-même sa
 *     connexion à SABnzbd…) avant d'être enregistré. Relancer ne crée
 *     jamais de doublon.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertTriangle,
    Ban,
    CheckCircle2,
    CircleDashed,
    Download,
    FileCog,
    FolderInput,
    KeyRound,
    Loader2,
    Lock,
    RefreshCw,
    Wand2,
    XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormField, SecretInput } from "@/components/settings/form-field";
import { TypeIcon } from "@/components/services/service-config";
import {
    applyStack,
    planStack,
    type DownloaderCredentials,
    type StackAction,
    type StackActionKind,
    type StackActionResult,
    type StackApp,
    type StackPlan,
} from "@/hooks/use-stack";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

type Downloader = "deluge" | "qbittorrent";

const KIND_LABELS: Record<StackActionKind, { title: string; hint: string }> = {
    register: { title: "Ajout dans ArrMada", hint: "Clé API lue dans le fichier de config de l'appli." },
    prowlarr_app: { title: "Indexeurs", hint: "Prowlarr pousse ses indexeurs vers Sonarr, Radarr…" },
    download_client: { title: "Clients de téléchargement", hint: "Catégorie dédiée par appli (tv, movies…)." },
    bazarr_link: { title: "Sous-titres", hint: "Bazarr suit les séries et films de Sonarr / Radarr." },
    root_folder: { title: "Dossiers médias", hint: "Arborescence TRaSH créée par l'installeur (/data/media/…)." },
};

const SOURCE_LABELS: Record<StackApp["source"], string> = {
    arrmada: "Déjà dans ArrMada",
    appdata: "Fichier de config",
    manual: "Saisi à la main",
};

/** Exemples de montage du dossier appdata selon la plateforme. */
const MOUNT_EXAMPLES = [
    { label: "Unraid", line: "- /mnt/user/appdata:/appdata:ro" },
    { label: "Synology", line: "- /volume1/docker:/appdata:ro" },
    { label: "Linux / autre", line: "- /chemin/de/tes/configs:/appdata:ro" },
];

/** Icône : clients torrent absents de SERVICE_META → visuel dédié. */
function AppIcon({ type }: { type: string }) {
    if (type === "deluge" || type === "qbittorrent") {
        const color = type === "deluge" ? "#5b8def" : "#3b82f6";
        return (
            <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ring-white/10"
                style={{ background: `linear-gradient(135deg, ${color}33, ${color}0d)` }}
            >
                <Download className="h-5 w-5" style={{ color }} />
            </span>
        );
    }
    return <TypeIcon type={type} />;
}

export function StackWiring({
    variant = "full",
    onApplied,
}: {
    /** wizard : textes raccourcis, lancement automatique de l'analyse. */
    variant?: "full" | "wizard";
    onApplied?: (results: StackActionResult[], plan: StackPlan) => void;
}) {
    const [plan, setPlan] = useState<StackPlan | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [hosts, setHosts] = useState("");
    const [creds, setCreds] = useState<Record<Downloader, DownloaderCredentials>>({ deluge: {}, qbittorrent: {} });
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [applying, setApplying] = useState(false);
    const [results, setResults] = useState<Record<string, StackActionResult>>({});

    const request = useCallback(
        () => ({ hosts: hosts.split(/[\s,;]+/), credentials: creds }),
        [hosts, creds],
    );

    /** Coche par défaut toutes les actions « à faire ». */
    const adopt = (next: StackPlan) => {
        setPlan(next);
        setSelected(new Set(next.actions.filter((a) => a.status === "todo").map((a) => a.id)));
    };

    const analyse = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            adopt(await planStack(request()));
        } catch (e) {
            setError(e instanceof Error ? e.message : "Analyse impossible.");
        } finally {
            setLoading(false);
        }
    }, [request]);

    // Première analyse automatique (lecture seule : sans risque).
    useEffect(() => {
        void analyse();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const apply = async () => {
        if (!plan || selected.size === 0) return;
        setApplying(true);
        setError("");
        try {
            const res = await applyStack([...selected], request());
            setResults(Object.fromEntries(res.results.map((r) => [r.id, r])));
            adopt(res.plan);
            onApplied?.(res.results, res.plan);
        } catch (e) {
            setError(e instanceof Error ? e.message : "L'application du plan a échoué.");
        } finally {
            setApplying(false);
        }
    };

    const setCred = (dl: Downloader, field: keyof DownloaderCredentials, value: string) =>
        setCreds((c) => ({ ...c, [dl]: { ...c[dl], [field]: value } }));

    const grouped = useMemo(() => {
        const groups = new Map<StackActionKind, StackAction[]>();
        for (const a of plan?.actions ?? []) groups.set(a.kind, [...(groups.get(a.kind) ?? []), a]);
        return [...groups.entries()];
    }, [plan]);

    const counts = useMemo(() => {
        const acts = plan?.actions ?? [];
        return {
            todo: acts.filter((a) => a.status === "todo").length,
            done: acts.filter((a) => a.status === "done").length,
            blocked: acts.filter((a) => a.status === "blocked").length,
        };
    }, [plan]);

    const missingDownloaders = (["deluge", "qbittorrent"] as Downloader[]).filter(
        (dl) => !plan?.apps.some((a) => a.type === dl),
    );

    return (
        <div className="space-y-5">
            {/* ── Dossier appdata non monté ─────────────────────── */}
            {plan && !plan.appdata_mounted && (
                <div className="rounded-2xl border border-primary/25 bg-primary/[0.07] p-4 text-sm">
                    <p className="flex items-center gap-2 font-semibold">
                        <FolderInput className="h-4 w-4 text-primary" /> Laisse ArrMada lire les clés API à ta place
                    </p>
                    <p className="mt-1 text-muted-foreground">
                        Ajoute le dossier qui contient les configs de tes applis au service <span className="font-mono">arrmada</span>{" "}
                        de ton docker-compose.yml (en <span className="font-mono">:ro</span>, lecture seule), puis{" "}
                        <span className="font-mono">docker compose up -d</span> :
                    </p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                        {MOUNT_EXAMPLES.map((m) => (
                            <div key={m.label} className="rounded-xl bg-black/30 px-3 py-2 ring-1 ring-white/[0.06]">
                                <p className="text-[11px] text-muted-foreground">{m.label}</p>
                                <code className="block truncate font-mono text-xs text-brand" title={m.line}>
                                    {m.line}
                                </code>
                            </div>
                        ))}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                        Sans ce montage, le câblage fonctionne quand même avec les services déjà ajoutés à ArrMada.
                    </p>
                </div>
            )}

            {/* ── Applications trouvées ─────────────────────────── */}
            <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="eyebrow">
                        {plan ? plural(plan.apps.length, "application trouvée", "applications trouvées") : "Applications"}
                    </p>
                    <Button size="sm" variant="outline" onClick={analyse} disabled={loading || applying}>
                        <RefreshCw className={loading ? "animate-spin" : ""} /> {loading ? "Analyse…" : "Réanalyser"}
                    </Button>
                </div>

                {loading && !plan ? (
                    <div className="flex items-center gap-2 rounded-2xl border border-white/[0.06] bg-background/30 p-4 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" /> Lecture des configs et recherche des applis sur le réseau…
                    </div>
                ) : plan && plan.apps.length === 0 ? (
                    <p className="rounded-2xl border border-white/[0.06] bg-background/30 p-4 text-sm text-muted-foreground">
                        Aucune application trouvée pour l&apos;instant.
                    </p>
                ) : (
                    <div className="grid gap-2 md:grid-cols-2">
                        {plan?.apps.map((app) => (
                            <AppCard
                                key={app.name}
                                app={app}
                                creds={app.type === "deluge" || app.type === "qbittorrent" ? creds[app.type] : undefined}
                                onCred={(f, v) => setCred(app.type as Downloader, f, v)}
                                onVerify={analyse}
                                busy={loading}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* ── Options : IP de l'hôte, clients torrent saisis à la main ── */}
            {variant === "full" && plan && (
                <details className="group rounded-2xl border border-white/[0.06] bg-background/30 p-4 text-sm">
                    <summary className="cursor-pointer select-none font-medium text-muted-foreground group-open:text-foreground">
                        Une appli manque ou est injoignable ?
                    </summary>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <FormField
                            id="stack-hosts"
                            label="Adresse IP de la machine qui héberge tes applis"
                            hint="ArrMada essaiera aussi cette adresse (ex : 192.168.1.10). Plusieurs : séparées par des espaces."
                        >
                            <Input
                                id="stack-hosts"
                                value={hosts}
                                placeholder="192.168.1.10"
                                className="font-mono text-sm"
                                onChange={(e) => setHosts(e.target.value)}
                            />
                        </FormField>
                        {missingDownloaders.map((dl) => (
                            <div key={dl} className="space-y-2">
                                <FormField id={`${dl}-url`} label={`${dl === "deluge" ? "Deluge" : "qBittorrent"} — adresse de l'interface web`}>
                                    <Input
                                        id={`${dl}-url`}
                                        value={creds[dl].url ?? ""}
                                        placeholder={dl === "deluge" ? "http://192.168.1.10:8112" : "http://192.168.1.10:8080"}
                                        className="font-mono text-sm"
                                        onChange={(e) => setCred(dl, "url", e.target.value)}
                                    />
                                </FormField>
                                <SecretInput
                                    id={`${dl}-manual-pw`}
                                    icon={Lock}
                                    value={creds[dl].password ?? ""}
                                    placeholder="Mot de passe"
                                    onChange={(e) => setCred(dl, "password", e.target.value)}
                                />
                            </div>
                        ))}
                    </div>
                    <Button size="sm" className="mt-4" onClick={analyse} disabled={loading}>
                        <RefreshCw className={loading ? "animate-spin" : ""} /> Relancer l&apos;analyse
                    </Button>
                </details>
            )}

            {/* ── Résultats d'actions qui ne figurent plus dans le plan (ex : ajouts) ── */}
            {plan && Object.keys(results).length > 0 && (
                <ul className="space-y-1 rounded-2xl border border-white/[0.06] bg-background/30 p-3 text-xs">
                    <li className="eyebrow pb-1">Dernière exécution</li>
                    {Object.values(results)
                        .filter((r) => !plan.actions.some((a) => a.id === r.id))
                        .map((r) => (
                            <li key={r.id} className={cn("flex items-start gap-1.5", r.ok ? "text-success" : "text-destructive")}>
                                {r.ok ? <CheckCircle2 className="mt-px h-3 w-3 shrink-0" /> : <XCircle className="mt-px h-3 w-3 shrink-0" />}
                                <span className="break-words">{r.message}</span>
                            </li>
                        ))}
                    <li className="pt-1 text-muted-foreground">
                        {plural(Object.values(results).filter((r) => r.ok).length, "réussite")} ·{" "}
                        {plural(Object.values(results).filter((r) => !r.ok).length, "échec")}
                    </li>
                </ul>
            )}

            {/* ── Plan d'actions ────────────────────────────────── */}
            {plan && plan.actions.length > 0 && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="chip">
                            <CircleDashed className="h-3 w-3 text-primary" /> {plural(counts.todo, "à faire", "à faire")}
                        </span>
                        <span className="chip">
                            <CheckCircle2 className="h-3 w-3 text-success" /> {plural(counts.done, "déjà en place", "déjà en place")}
                        </span>
                        {counts.blocked > 0 && (
                            <span className="chip">
                                <Ban className="h-3 w-3 text-warning" /> {plural(counts.blocked, "bloquée", "bloquées")}
                            </span>
                        )}
                    </div>

                    {grouped.map(([kind, actions]) => (
                        <div key={kind} className="space-y-1.5">
                            <div className="flex items-baseline gap-2">
                                <p className="text-sm font-semibold">{KIND_LABELS[kind].title}</p>
                                <p className="text-[11px] text-muted-foreground">{KIND_LABELS[kind].hint}</p>
                            </div>
                            <ul className="space-y-1.5">
                                {actions.map((a) => (
                                    <ActionRow
                                        key={a.id}
                                        action={a}
                                        checked={selected.has(a.id)}
                                        result={results[a.id]}
                                        onToggle={() =>
                                            setSelected((prev) => {
                                                const next = new Set(prev);
                                                if (next.has(a.id)) next.delete(a.id);
                                                else next.add(a.id);
                                                return next;
                                            })
                                        }
                                    />
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>
            )}

            <AnimatePresence>
                {error && (
                    <motion.p
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        role="alert"
                        className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
                    >
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
                    </motion.p>
                )}
            </AnimatePresence>

            {plan && counts.todo > 0 && (
                <Button onClick={apply} disabled={applying || selected.size === 0} size="lg" className="w-full sm:w-auto">
                    {applying ? <Loader2 className="animate-spin" /> : <Wand2 />}
                    {applying ? "Configuration en cours…" : `Tout connecter · ${plural(selected.size, "action")}`}
                </Button>
            )}
        </div>
    );
}

/* ── Carte d'une application ──────────────────────────────── */

function AppCard({
    app,
    creds,
    onCred,
    onVerify,
    busy,
}: {
    app: StackApp;
    creds?: DownloaderCredentials;
    onCred: (field: keyof DownloaderCredentials, value: string) => void;
    onVerify: () => void;
    busy: boolean;
}) {
    const isTorrent = app.type === "deluge" || app.type === "qbittorrent";
    return (
        <div
            className={cn(
                "glass space-y-2 rounded-2xl p-3",
                app.error && "shadow-[inset_0_0_0_1px_rgb(239_68_68/0.3)]",
                !app.error && app.needs_password && "shadow-[inset_0_0_0_1px_rgb(245_158_11/0.3)]",
            )}
        >
            <div className="flex items-center gap-3">
                <AppIcon type={app.type} />
                <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 truncate text-sm font-semibold">
                        {app.name}
                        {app.version && <span className="font-mono text-[10px] font-normal text-muted-foreground">v{app.version}</span>}
                    </p>
                    <p className="truncate font-mono text-xs text-muted-foreground" title={app.urls.join("\n")}>
                        {app.url ?? "adresse inconnue"}
                    </p>
                </div>
                <span className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
                    <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-muted-foreground" title={app.config_path ?? undefined}>
                        {app.source === "appdata" ? <FileCog className="mr-1 inline h-3 w-3" /> : null}
                        {SOURCE_LABELS[app.source]}
                    </span>
                    {!isTorrent && (
                        <span
                            className={cn(
                                "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                app.has_api_key ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive",
                            )}
                        >
                            <KeyRound className="mr-1 inline h-3 w-3" />
                            {app.has_api_key ? "Clé API trouvée" : "Clé absente"}
                        </span>
                    )}
                </span>
            </div>

            {app.error && <p className="text-xs text-destructive">{app.error}</p>}
            {app.notes.map((n) => (
                <p key={n} className="flex items-start gap-1.5 text-[11px] text-warning/90">
                    <AlertTriangle className="mt-px h-3 w-3 shrink-0" /> {n}
                </p>
            ))}

            {isTorrent && app.needs_password && creds && (
                <div className="flex flex-wrap gap-2 pt-1">
                    {app.type === "qbittorrent" && (
                        <Input
                            value={creds.username ?? ""}
                            placeholder={app.username ?? "admin"}
                            className="h-9 w-full text-sm"
                            aria-label="Utilisateur qBittorrent"
                            onChange={(e) => onCred("username", e.target.value)}
                        />
                    )}
                    <div className="min-w-[12rem] flex-1">
                        <SecretInput
                            icon={Lock}
                            value={creds.password ?? ""}
                            placeholder={`Mot de passe ${app.name}`}
                            className="h-9"
                            aria-label={`Mot de passe ${app.name}`}
                            onChange={(e) => onCred("password", e.target.value)}
                        />
                    </div>
                    <Button size="sm" variant="outline" onClick={onVerify} disabled={busy || !creds.password}>
                        {busy ? <Loader2 className="animate-spin" /> : <CheckCircle2 />} Vérifier
                    </Button>
                </div>
            )}
        </div>
    );
}

/* ── Ligne d'action du plan ───────────────────────────────── */

function ActionRow({
    action,
    checked,
    result,
    onToggle,
}: {
    action: StackAction;
    checked: boolean;
    result?: StackActionResult;
    onToggle: () => void;
}) {
    const todo = action.status === "todo";
    return (
        <li>
            <button
                type="button"
                role="checkbox"
                aria-checked={todo ? checked : action.status === "done"}
                aria-disabled={!todo}
                onClick={todo ? onToggle : undefined}
                className={cn(
                    "flex w-full items-start gap-3 rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                    todo && checked && "border-primary/30 bg-primary/[0.06]",
                    todo && !checked && "border-white/[0.06] bg-background/30 opacity-70 hover:opacity-100",
                    !todo && "cursor-default border-white/[0.04] bg-background/20",
                )}
            >
                <span className="mt-0.5 shrink-0">
                    {action.status === "done" ? (
                        <CheckCircle2 className="h-4 w-4 text-success" />
                    ) : action.status === "blocked" ? (
                        <Ban className="h-4 w-4 text-warning" />
                    ) : (
                        <span
                            className={cn(
                                "flex h-4 w-4 items-center justify-center rounded border",
                                checked ? "border-primary bg-primary text-primary-foreground" : "border-white/25",
                            )}
                        >
                            {checked && <CheckCircle2 className="h-3 w-3" />}
                        </span>
                    )}
                </span>
                <span className="min-w-0 flex-1">
                    <span className={cn("block", action.status !== "todo" && "text-muted-foreground")}>{action.title}</span>
                    {action.status === "blocked" && action.reason && (
                        <span className="block text-[11px] text-warning/80">Bloqué : {action.reason}</span>
                    )}
                    {result && (
                        <span className={cn("mt-0.5 block break-words text-[11px]", result.ok ? "text-success" : "text-destructive")}>
                            {result.ok ? "✓ " : "✗ "}
                            {result.message}
                        </span>
                    )}
                </span>
            </button>
        </li>
    );
}
