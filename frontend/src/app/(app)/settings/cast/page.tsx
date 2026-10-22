"use client";

/**
 * Paramètres → Cast & Jellyfin.
 * ----------------------------------------------------------------
 * Jellyfin sert de « transcodeur » : il convertit le film dans un format
 * que les Chromecast savent lire, puis ArrMada envoie le flux à l'appareil.
 * Corrections :
 *  - plus d'IP personnelle codée en dur (http://192.168.2.3:8097) ;
 *  - « Enregistré » n'est plus affiché quand le backend répond 200 avec
 *    {status:"error"} (le hook partagé use-cast ne le détecte pas, on le
 *    vérifie ici) ;
 *  - suppression d'appareil confirmée, avec chargement et aria-label.
 */
import { useEffect, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Cast, CheckCircle2, Loader2, Radar, Save, Server, Speaker, Tv, XCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer, TableSkeleton } from "@/components/shared/loading-skeleton";
import { StatusDot } from "@/components/fx/status-dot";
import { DeviceRow } from "@/components/settings/device-row";
import { ScanPulse } from "@/components/settings/discovery-results";
import { FormField, SecretInput, validateHttpUrl } from "@/components/settings/form-field";
import {
    useCastDevices,
    useCastDiscover,
    useDeleteCastDevice,
    useJellyfinConfig,
    useSetJellyfin,
    useTestJellyfin,
    type JellyfinSegmentsSupport,
} from "@/hooks/use-cast";
import { plural } from "@/lib/format";
import { stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

export default function CastSettingsPage() {
    return (
        <>
            <JellyfinPanel />
            <DevicesPanel />
        </>
    );
}

/* ── Jellyfin ───────────────────────────────────────────────── */

/** « Passer l'intro » sur la TV : ce que Jellyfin peut fournir (marqueurs d'épisode). */
function markersLabel(s?: JellyfinSegmentsSupport): string | undefined {
    if (!s) return undefined;
    if (!s.supported) return "Marqueurs d'intro / générique : Jellyfin 10.10 ou plus récent requis.";
    if (s.providers.length > 0) return `Marqueurs d'intro / générique : ${s.providers.join(", ")}.`;
    if (!s.checked) return "Marqueurs d'intro / générique : liste des plugins illisible (clé non administrateur ?).";
    return "Marqueurs d'intro / générique : aucun plugin. Installe Intro Skipper pour « Passer l'intro » sur la TV.";
}

function JellyfinPanel() {
    const { data: jf, isLoading, isError, error, refetch } = useJellyfinConfig();
    const setJf = useSetJellyfin();
    const testJf = useTestJellyfin();

    const [url, setUrl] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [testResult, setTestResult] = useState<{ ok: boolean; label: string; markers?: string } | null>(null);

    // Pré-remplit l'URL enregistrée une fois chargée (sans écraser une saisie).
    useEffect(() => {
        if (jf?.url) setUrl((current) => current || jf.url || "");
    }, [jf?.url]);

    const configured = !!jf?.configured;
    const urlErr = validateHttpUrl(url, "http://192.168.1.10:8096");
    const keyErr = !configured && !apiKey.trim() ? "La clé API est obligatoire pour la première configuration." : null;

    const save = async (e: FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        if (urlErr || keyErr) return;
        try {
            const r = await setJf.mutateAsync({ url: url.trim().replace(/\/+$/, ""), api_key: apiKey.trim(), name: jf?.name || "Jellyfin" });
            // Le backend répond 200 même en cas de refus : on vérifie le statut.
            if (r?.status === "error") {
                toast.error("Jellyfin non enregistré", { description: r.detail ?? "Le backend a refusé la configuration." });
                return;
            }
            toast.success("Jellyfin enregistré", { description: "Teste la connexion pour vérifier la clé." });
            setApiKey("");
            setSubmitted(false);
            setTestResult(null);
        } catch (err) {
            toast.error("Enregistrement impossible", { description: err instanceof Error ? err.message : undefined });
        }
    };

    const runTest = () =>
        testJf.mutate(undefined, {
            onSuccess: (r) =>
                setTestResult(
                    r.ok
                        ? {
                              ok: true,
                              label: [r.server, r.version && `v${r.version}`].filter(Boolean).join(" · ") || "Connexion OK",
                              markers: markersLabel(r.segments),
                          }
                        : { ok: false, label: r.detail || "Jellyfin injoignable" },
                ),
            onError: (e) => setTestResult({ ok: false, label: e.message }),
        });

    return (
        <Panel
            title="Jellyfin (transcodage)"
            icon={Server}
            iconClassName="text-primary"
            action={
                !isLoading && !isError ? (
                    <span
                        className={cn(
                            "flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                            configured ? "bg-success/10 text-success" : "bg-warning/10 text-warning",
                        )}
                    >
                        <StatusDot tone={configured ? "online" : "warning"} size="sm" />
                        {configured ? "Configuré" : "À configurer"}
                    </span>
                ) : undefined
            }
        >
            {isLoading ? (
                <div className="space-y-3">
                    <Shimmer className="h-10 w-full" />
                    <Shimmer className="h-10 w-full" />
                </div>
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} />
            ) : (
                <form onSubmit={save} className="space-y-4" noValidate>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                        Les Chromecast ne lisent pas tous les formats : Jellyfin convertit le film à la volée. Crée une clé dans{" "}
                        <span className="text-foreground">Jellyfin → Tableau de bord → Clés API</span>.
                    </p>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <FormField id="jf-url" label="Adresse de Jellyfin" error={submitted ? urlErr : null}>
                            <Input
                                id="jf-url"
                                value={url}
                                onChange={(e) => {
                                    setUrl(e.target.value);
                                    setTestResult(null);
                                }}
                                placeholder="http://192.168.1.10:8096"
                                inputMode="url"
                                spellCheck={false}
                                autoComplete="off"
                                className="font-mono text-sm"
                                aria-invalid={submitted && !!urlErr}
                            />
                        </FormField>
                        <FormField
                            id="jf-key"
                            label="Clé API"
                            error={submitted ? keyErr : null}
                            hint={configured ? "Laisse vide pour conserver la clé enregistrée." : undefined}
                        >
                            <SecretInput
                                id="jf-key"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder={configured ? "•••••••• (inchangée)" : "Colle la clé ici"}
                                aria-invalid={submitted && !!keyErr}
                            />
                        </FormField>
                    </div>

                    <AnimatePresence initial={false}>
                        {testResult && (
                            <motion.p
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                aria-live="polite"
                                className={cn(
                                    "flex items-center gap-2 overflow-hidden rounded-xl border px-3.5 py-2.5 text-sm",
                                    testResult.ok
                                        ? "border-success/25 bg-success/10 text-success"
                                        : "border-destructive/25 bg-destructive/10 text-destructive",
                                )}
                            >
                                {testResult.ok ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
                                <span>
                                    {testResult.label}
                                    {testResult.markers && (
                                        <span className="block text-xs text-muted-foreground">{testResult.markers}</span>
                                    )}
                                </span>
                            </motion.p>
                        )}
                    </AnimatePresence>

                    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={runTest}
                            disabled={!configured || testJf.isPending}
                            title={!configured ? "Enregistre d'abord Jellyfin" : undefined}
                        >
                            {testJf.isPending ? <Loader2 className="animate-spin" /> : <Zap />}
                            Tester la connexion
                        </Button>
                        <Button type="submit" disabled={setJf.isPending}>
                            {setJf.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                            Enregistrer
                        </Button>
                    </div>
                </form>
            )}
        </Panel>
    );
}

/* ── Appareils Cast ─────────────────────────────────────────── */

function DevicesPanel() {
    const { data: devices, isLoading, isError, error, refetch } = useCastDevices();
    const discover = useCastDiscover();
    const del = useDeleteCastDevice();

    const scan = () =>
        discover.mutate(undefined, {
            onSuccess: (list) =>
                list.length > 0
                    ? toast.success(`${plural(list.length, "appareil détecté", "appareils détectés")}`)
                    : toast.info("Aucun appareil Cast trouvé", { description: "Vérifie qu'ils sont allumés et sur le même réseau." }),
            onError: (e) => toast.error("Scan impossible", { description: e.message }),
        });

    return (
        <Panel
            title="Appareils Cast"
            icon={Cast}
            iconClassName="text-primary"
            action={
                <Button variant="outline" size="sm" onClick={scan} disabled={discover.isPending}>
                    {discover.isPending ? <Loader2 className="animate-spin" /> : <Radar />}
                    {discover.isPending ? "Scan…" : "Scanner le réseau"}
                </Button>
            }
            bodyClassName="space-y-3"
        >
            <p className="text-xs text-muted-foreground">Chromecast, Google TV et enceintes Nest détectés sur ton réseau local.</p>

            <AnimatePresence initial={false}>
                {discover.isPending && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="flex items-center gap-3 overflow-hidden rounded-xl border border-primary/20 bg-primary/[0.06] px-4 py-3 text-sm text-primary"
                    >
                        <ScanPulse /> Recherche des appareils Cast (une dizaine de secondes)…
                    </motion.div>
                )}
            </AnimatePresence>

            {isLoading ? (
                <TableSkeleton rows={2} />
            ) : isError ? (
                <ErrorState compact error={error} onRetry={() => refetch()} />
            ) : !devices || devices.length === 0 ? (
                <EmptyState
                    compact
                    icon={Cast}
                    title="Aucun appareil"
                    description="Lance un scan pour détecter tes Chromecast et Google TV."
                    action={{ label: "Scanner le réseau", onClick: scan }}
                />
            ) : (
                <motion.div variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-2">
                    <AnimatePresence>
                        {devices.map((d) => (
                            <DeviceRow
                                key={d.id}
                                icon={d.video_capable ? Tv : Speaker}
                                tone={d.video_capable ? "sky" : "slate"}
                                name={d.name}
                                address={`${d.ip}${d.port ? `:${d.port}` : ""}`}
                                meta={d.model ?? undefined}
                                badges={
                                    <span
                                        className={cn(
                                            "rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
                                            d.video_capable ? "bg-primary/15 text-primary" : "bg-white/[0.06] text-muted-foreground",
                                        )}
                                    >
                                        {d.video_capable ? "Vidéo" : "Audio"}
                                    </span>
                                }
                                onDelete={() => del.mutateAsync(d.id)}
                                deleteTitle={`Retirer ${d.name} ?`}
                                deleteDescription="L'appareil disparaîtra de la liste « Caster sur… ». Un nouveau scan le fera réapparaître s'il est toujours sur le réseau."
                            />
                        ))}
                    </AnimatePresence>
                </motion.div>
            )}
        </Panel>
    );
}
