"use client";

/**
 * Paramètres → Kodi.
 * ----------------------------------------------------------------
 * - Lecteurs : test automatique (pastille d'état), « Modifier » dans une
 *   boîte (avant : changer l'URL créait un doublon), suppression confirmée.
 * - Ajout : détection mDNS listant TOUS les Kodi trouvés (avant : seul le
 *   premier était utilisé), placeholders génériques.
 * - Maintenance : scan (succès ET échecs signalés), nettoyage confirmé,
 *   cohérence Radarr ↔ Kodi avec jauge, liste complète et liens.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertTriangle,
    Brush,
    CheckCircle2,
    ChevronDown,
    ExternalLink,
    Lock,
    Loader2,
    MonitorPlay,
    Plus,
    Radar,
    RefreshCw,
    Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer, TableSkeleton } from "@/components/shared/loading-skeleton";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { RingGauge } from "@/components/fx/ring-gauge";
import { DeviceRow } from "@/components/settings/device-row";
import { useStickyValue } from "@/components/settings/use-sticky-value";
import { DiscoveryResults, type DiscoveredDevice } from "@/components/settings/discovery-results";
import { KodiForm } from "@/components/settings/kodi-form";
import {
    kodiUsername,
    useAddKodi,
    useDeleteKodi,
    useKodiClean,
    useKodiDiscover,
    useKodiDrift,
    useKodiSettings,
    useKodiSync,
    useTestKodi,
    useUpdateKodi,
    type KodiInstance,
} from "@/hooks/use-kodi";
import { formatNumber, percent, plural } from "@/lib/format";
import { stagger } from "@/lib/motion";

/** Nombre de films manquants affichés avant « Afficher tout ». */
const DRIFT_PREVIEW = 24;

export default function KodiSettingsPage() {
    const { data: instances, isLoading, isError, error, refetch } = useKodiSettings();
    const add = useAddKodi();
    const update = useUpdateKodi();
    const del = useDeleteKodi();
    const test = useTestKodi();
    const discover = useKodiDiscover();

    const [editing, setEditing] = useState<KodiInstance | null>(null);
    // Reste affiché pendant l'animation de fermeture de la boîte « Modifier ».
    const shownEditing = useStickyValue(editing);
    const [found, setFound] = useState<DiscoveredDevice[] | null>(null);
    const [prefill, setPrefill] = useState<{ name: string; url: string; nonce: number } | null>(null);

    const knownUrls = useMemo(() => new Set((instances ?? []).map((k) => k.url.replace(/\/+$/, ""))), [instances]);

    const runDiscover = () =>
        discover.mutate(undefined, {
            onSuccess: (list) => {
                const devices = (list ?? []).map((d) => ({
                    key: d.url,
                    name: d.name || "Kodi",
                    url: d.url,
                    known: knownUrls.has(d.url.replace(/\/+$/, "")),
                }));
                setFound(devices);
                if (devices.length === 0) toast.info("Aucun Kodi annoncé sur le réseau (mDNS).");
            },
            onError: (e) => toast.error("Détection impossible", { description: e.message }),
        });

    return (
        <>
            {/* ── Lecteurs configurés ─────────────────────────── */}
            <Panel
                title="Lecteurs Kodi"
                icon={MonitorPlay}
                iconClassName="text-violet-300"
                action={instances && instances.length > 0 ? <span className="text-xs text-muted-foreground">{plural(instances.length, "lecteur")}</span> : undefined}
            >
                {isLoading ? (
                    <TableSkeleton rows={2} />
                ) : isError ? (
                    <ErrorState compact error={error} onRetry={() => refetch()} />
                ) : !instances || instances.length === 0 ? (
                    <EmptyState
                        compact
                        icon={MonitorPlay}
                        title="Aucun Kodi pour l'instant"
                        description="Ajoute ton lecteur ci-dessous pour lancer tes films dessus et piloter la lecture depuis le Salon."
                    />
                ) : (
                    <motion.div variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-2">
                        <AnimatePresence>
                            {instances.map((k) => (
                                <DeviceRow
                                    key={k.id}
                                    icon={MonitorPlay}
                                    tone="violet"
                                    name={k.name}
                                    address={k.url}
                                    badges={!k.is_enabled ? <span className="rounded-full bg-slate-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300">Désactivé</span> : null}
                                    meta={
                                        <span className="flex flex-wrap items-center gap-x-2">
                                            <span>Utilisateur : {kodiUsername(k) || "aucun"}</span>
                                            {k.has_password && (
                                                <span className="inline-flex items-center gap-1">
                                                    <Lock className="h-3 w-3" /> mot de passe enregistré
                                                </span>
                                            )}
                                        </span>
                                    }
                                    autoTest={k.is_enabled}
                                    onTest={async () => {
                                        const r = await test.mutateAsync(k.id);
                                        return r.ok
                                            ? { ok: true, label: `${r.name ?? "Kodi"} ${r.version ?? ""}`.trim() }
                                            : { ok: false, label: r.detail || "Injoignable" };
                                    }}
                                    onEdit={() => setEditing(k)}
                                    onDelete={() => del.mutateAsync(k.id)}
                                    deleteDescription="ArrMada ne pourra plus lancer de lecture ni scanner la bibliothèque de ce Kodi. Kodi lui-même n'est pas modifié."
                                />
                            ))}
                        </AnimatePresence>
                    </motion.div>
                )}
            </Panel>

            {/* ── Ajouter ─────────────────────────────────────── */}
            <Panel
                title="Ajouter un Kodi"
                icon={Plus}
                iconClassName="text-primary"
                action={
                    <Button variant="outline" size="sm" onClick={runDiscover} disabled={discover.isPending}>
                        {discover.isPending ? <Loader2 className="animate-spin" /> : <Radar />}
                        Détecter
                    </Button>
                }
                bodyClassName="space-y-5"
            >
                <div className="rounded-xl border border-white/[0.06] bg-background/30 p-3.5 text-xs leading-relaxed text-muted-foreground">
                    <p className="mb-1.5 flex items-center gap-1.5 font-semibold text-foreground">
                        <Wrench className="h-3.5 w-3.5 text-primary" /> Côté Kodi, une seule fois :
                    </p>
                    <ol className="list-inside list-decimal space-y-0.5">
                        <li>
                            Paramètres → Services → Contrôle : active <span className="text-foreground">« Autoriser le contrôle à distance via HTTP »</span>.
                        </li>
                        <li>Choisis un utilisateur et un mot de passe (et note le port, 8080 par défaut).</li>
                        <li>Clique « Détecter » ci-dessus ou saisis l&apos;adresse à la main.</li>
                    </ol>
                </div>

                <DiscoveryResults
                    devices={found}
                    scanning={discover.isPending}
                    icon={MonitorPlay}
                    selectedKey={prefill ? found?.find((f) => f.url === prefill.url)?.key : null}
                    onPick={(d) => setPrefill({ name: d.name, url: d.url, nonce: Date.now() })}
                />

                <KodiForm
                    idPrefix="kodi-add"
                    prefill={prefill}
                    submitLabel="Enregistrer"
                    submitIcon={<Plus />}
                    pending={add.isPending}
                    resetOnSuccess
                    onSubmit={async (payload) => {
                        try {
                            const r = await add.mutateAsync(payload);
                            toast.success(r?.message ?? "Kodi enregistré", { description: payload.url });
                            setPrefill(null);
                        } catch (e) {
                            toast.error("Enregistrement impossible", { description: e instanceof Error ? e.message : undefined });
                            throw e;
                        }
                    }}
                />
            </Panel>

            {/* ── Maintenance ─────────────────────────────────── */}
            <MaintenancePanel instances={instances ?? []} />

            {/* ── Modifier (boîte) ────────────────────────────── */}
            <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
                <DialogContent className="sm:max-w-xl">
                    <DialogHeader>
                        <DialogTitle>Modifier {shownEditing?.name}</DialogTitle>
                        <DialogDescription>Change l&apos;adresse, les identifiants ou le nom sans créer de doublon.</DialogDescription>
                    </DialogHeader>
                    {shownEditing && (
                        <KodiForm
                            key={shownEditing.id}
                            idPrefix="kodi-edit"
                            initial={shownEditing}
                            submitLabel="Enregistrer"
                            pending={update.isPending}
                            onCancel={() => setEditing(null)}
                            onSubmit={async (payload) => {
                                try {
                                    await update.mutateAsync({ id: shownEditing.id, ...payload });
                                    toast.success("Kodi mis à jour", { description: payload.name });
                                    setEditing(null);
                                } catch (e) {
                                    toast.error("Modification impossible", { description: e instanceof Error ? e.message : undefined });
                                    throw e;
                                }
                            }}
                        />
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}

/* ── Maintenance : scan, nettoyage, cohérence Radarr ↔ Kodi ─── */

function MaintenancePanel({ instances }: { instances: KodiInstance[] }) {
    const sync = useKodiSync();
    const clean = useKodiClean();
    const hasKodi = instances.length > 0;
    const drift = useKodiDrift(hasKodi);
    const [confirmClean, setConfirmClean] = useState(false);
    const [cleanTarget, setCleanTarget] = useState<string>("");
    const [showAll, setShowAll] = useState(false);

    const enabledKodis = instances.filter((k) => k.is_enabled);

    const runSync = () =>
        sync.mutate(undefined, {
            onSuccess: (r) => {
                // Avant : `r.failed` était ignoré → « Scan lancé » même si tout échouait.
                if (r.success === 0 && r.failed === 0) toast.warning("Aucun Kodi actif à scanner.");
                else if (r.success === 0) toast.error(`Échec du scan sur ${plural(r.failed, "Kodi", "Kodi")}`, { description: "Vérifie qu'ils sont allumés et joignables." });
                else if (r.failed > 0) toast.warning(`Scan lancé sur ${r.success} Kodi, ${r.failed} en échec`);
                else toast.success(`Scan lancé sur ${plural(r.success, "Kodi", "Kodi")}`, { description: "Les nouveaux films apparaîtront d'ici quelques minutes." });
            },
            onError: (e) => toast.error("Scan impossible", { description: e.message }),
        });

    const missing = drift.data?.missing_in_kodi ?? [];
    const visible = showAll ? missing : missing.slice(0, DRIFT_PREVIEW);
    const coverage = drift.data ? percent(drift.data.radarr_total - drift.data.missing_count, drift.data.radarr_total) : 0;

    return (
        <Panel title="Bibliothèque & maintenance" icon={Wrench} iconClassName="text-amber-300" bodyClassName="space-y-5">
            <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={runSync} disabled={!hasKodi || sync.isPending}>
                    {sync.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                    Scanner la bibliothèque
                </Button>
                <Button
                    variant="outline"
                    onClick={() => {
                        setCleanTarget(enabledKodis[0] ? String(enabledKodis[0].id) : "");
                        setConfirmClean(true);
                    }}
                    disabled={!hasKodi || clean.isPending}
                >
                    {clean.isPending ? <Loader2 className="animate-spin" /> : <Brush />}
                    Nettoyer…
                </Button>
            </div>

            {/* Cohérence Radarr ↔ Kodi */}
            <div className="rounded-2xl border border-white/[0.06] bg-background/30 p-4">
                {!hasKodi ? (
                    <p className="text-sm text-muted-foreground">Ajoute un Kodi pour comparer sa bibliothèque avec Radarr.</p>
                ) : drift.isLoading ? (
                    <div className="flex items-center gap-4">
                        <Shimmer className="h-16 w-16 rounded-full" />
                        <div className="flex-1 space-y-2">
                            <Shimmer className="h-4 w-48 rounded-md" />
                            <Shimmer className="h-3 w-32 rounded-md" />
                        </div>
                    </div>
                ) : drift.isError || !drift.data ? (
                    <ErrorState compact error={drift.error} onRetry={() => drift.refetch()} title="Comparaison Radarr ↔ Kodi indisponible" />
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center gap-4">
                            <RingGauge value={coverage} size={68} stroke={6} tone={drift.data.missing_count === 0 ? "emerald" : "amber"}>
                                <span className="text-xs font-bold tabular-nums">{Math.floor(coverage)}%</span>
                            </RingGauge>
                            <div className="min-w-0 flex-1">
                                {drift.data.missing_count === 0 ? (
                                    <p className="flex items-center gap-1.5 text-sm font-semibold text-emerald-300">
                                        <CheckCircle2 className="h-4 w-4" /> Radarr et Kodi sont synchronisés
                                    </p>
                                ) : (
                                    <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-300">
                                        <AlertTriangle className="h-4 w-4" />
                                        {plural(drift.data.missing_count, "film absent", "films absents")} de Kodi
                                    </p>
                                )}
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                    {formatNumber(drift.data.radarr_total)} dans Radarr · {formatNumber(drift.data.kodi_total)} dans Kodi
                                </p>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => drift.refetch()}
                                disabled={drift.isFetching}
                                aria-label="Recalculer la comparaison"
                            >
                                <RefreshCw className={drift.isFetching ? "animate-spin" : ""} />
                            </Button>
                        </div>

                        {missing.length > 0 && (
                            <>
                                <ul className="flex flex-wrap gap-1.5">
                                    {visible.map((m) => (
                                        <li key={m.tmdb_id}>
                                            <a
                                                href={`https://www.themoviedb.org/movie/${m.tmdb_id}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="group inline-flex items-center gap-1 rounded-full border border-amber-500/25 bg-amber-500/[0.06] px-2.5 py-1 text-[11px] text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-500/15"
                                                title="Voir sur TMDB"
                                            >
                                                {m.title}
                                                {m.year ? <span className="text-amber-200/60">({m.year})</span> : null}
                                                <ExternalLink className="h-2.5 w-2.5 opacity-50 group-hover:opacity-100" />
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                                <div className="flex flex-wrap items-center gap-2">
                                    {missing.length > DRIFT_PREVIEW && (
                                        <Button variant="ghost" size="sm" onClick={() => setShowAll((s) => !s)}>
                                            <ChevronDown className={showAll ? "rotate-180 transition-transform" : "transition-transform"} />
                                            {showAll ? "Réduire" : `Afficher les ${missing.length - DRIFT_PREVIEW} autres`}
                                        </Button>
                                    )}
                                    <Button variant="glow" size="sm" onClick={runSync} disabled={sync.isPending}>
                                        {sync.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                                        Scanner pour les ajouter
                                    </Button>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>

            <ConfirmDialog
                open={confirmClean}
                onOpenChange={setConfirmClean}
                destructive
                title="Nettoyer la bibliothèque Kodi ?"
                description="Kodi va retirer de sa bibliothèque les films et épisodes dont le fichier est introuvable. Leur progression de lecture sera perdue (aucun fichier n'est supprimé du disque). Si un disque réseau est momentanément déconnecté, attends qu'il revienne."
                confirmLabel="Nettoyer"
                onConfirm={async () => {
                    try {
                        const r = await clean.mutateAsync(cleanTarget ? { service_id: Number(cleanTarget) } : undefined);
                        toast.success(`Nettoyage lancé${r?.kodi ? ` sur ${r.kodi}` : ""}`);
                    } catch (e) {
                        toast.error("Nettoyage refusé", { description: e instanceof Error ? e.message : undefined });
                        throw e;
                    }
                }}
            >
                {enabledKodis.length > 1 && (
                    <div className="space-y-1.5">
                        <p className="text-xs text-muted-foreground">Sur quel lecteur ?</p>
                        <Select value={cleanTarget} onValueChange={setCleanTarget}>
                            <SelectTrigger aria-label="Lecteur à nettoyer">
                                <SelectValue placeholder="Choisis un Kodi" />
                            </SelectTrigger>
                            <SelectContent>
                                {enabledKodis.map((k) => (
                                    <SelectItem key={k.id} value={String(k.id)}>
                                        {k.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}
            </ConfirmDialog>
        </Panel>
    );
}
