"use client";

/**
 * Paramètres → Ampli Yamaha.
 * ----------------------------------------------------------------
 * La télécommande a déménagé dans le Salon (/remote) : ici on ne fait
 * QUE configurer — les amplis, et les profils audio par pièce (Salon /
 * Salle de cinéma) appliqués par les boutons « Préréglage » du Salon.
 * Corrections : IP personnelle codée en dur retirée,
 * `DeviceRow` partagé avec Kodi (au lieu d'un copier-coller), suppression
 * confirmée, édition sans doublon, tous les amplis détectés sélectionnables
 * (avant : seul le premier pré-remplissait le formulaire).
 */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Plus, Radar, Save, Sofa, Speaker } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { DeviceRow } from "@/components/settings/device-row";
import { useStickyValue } from "@/components/settings/use-sticky-value";
import { DiscoveryResults, type DiscoveredDevice } from "@/components/settings/discovery-results";
import { FormField } from "@/components/settings/form-field";
import { RoomProfilesPanel } from "@/components/settings/room-profiles";
import {
    useAddYamaha,
    useDeleteYamaha,
    useTestYamaha,
    useUpdateYamaha,
    useYamahaDiscover,
    useYamahaSettings,
    type YamahaInstance,
} from "@/hooks/use-yamaha";
import { plural } from "@/lib/format";
import { stagger } from "@/lib/motion";

/** Normalise une adresse (« 192.168.1.30 » → « http://192.168.1.30 ») pour comparer. */
function normalizeAddress(value: string): string {
    const v = value.trim().replace(/\/+$/, "");
    if (!v) return v;
    return v.startsWith("http") ? v : `http://${v}`;
}

export default function YamahaSettingsPage() {
    const { data: instances, isLoading, isError, error, refetch } = useYamahaSettings();
    const add = useAddYamaha();
    const update = useUpdateYamaha();
    const del = useDeleteYamaha();
    const test = useTestYamaha();
    const discover = useYamahaDiscover();

    const [editing, setEditing] = useState<YamahaInstance | null>(null);
    // Reste affiché pendant l'animation de fermeture de la boîte « Modifier ».
    const shownEditing = useStickyValue(editing);
    const [found, setFound] = useState<DiscoveredDevice[] | null>(null);
    const [prefill, setPrefill] = useState<{ name: string; url: string; nonce: number } | null>(null);

    const known = useMemo(() => new Set((instances ?? []).map((y) => normalizeAddress(y.url))), [instances]);

    const runDiscover = () =>
        discover.mutate(undefined, {
            onSuccess: (list) => {
                const devices = (list ?? []).map((d) => ({
                    key: d.device_id || d.url,
                    name: d.model_name || "Ampli Yamaha",
                    url: d.url,
                    known: known.has(normalizeAddress(d.url)),
                }));
                setFound(devices);
                if (devices.length === 1 && !devices[0].known) {
                    // Un seul ampli : on pré-remplit directement (gain d'un clic).
                    setPrefill({ name: devices[0].name, url: devices[0].url, nonce: Date.now() });
                }
                if (devices.length === 0) toast.info("Aucun ampli Yamaha détecté sur le réseau.");
            },
            onError: (e) => toast.error("Détection impossible", { description: e.message }),
        });

    return (
        <>
            {/* Raccourci vers la télécommande (désormais dans le Salon) */}
            <Link href="/remote" className="block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <SpotlightCard interactive className="group flex items-center gap-4 p-4">
                    <span className="relative z-[2] flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-fuchsia-500/10 text-violet-300 ring-1 ring-violet-400/25">
                        <Sofa className="h-5 w-5" />
                    </span>
                    <div className="relative z-[2] min-w-0 flex-1">
                        <p className="text-sm font-semibold">La télécommande est dans le Salon</p>
                        <p className="text-xs text-muted-foreground">Marche/veille, volume, entrées et préréglages Salon / Cinéma, à côté du lecteur Kodi.</p>
                    </div>
                    <ArrowRight className="relative z-[2] h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground" />
                </SpotlightCard>
            </Link>

            {/* ── Amplis configurés ───────────────────────────── */}
            <Panel
                title="Amplis configurés"
                icon={Speaker}
                iconClassName="text-orange-300"
                action={instances && instances.length > 0 ? <span className="text-xs text-muted-foreground">{plural(instances.length, "ampli")}</span> : undefined}
            >
                {isLoading ? (
                    <TableSkeleton rows={1} />
                ) : isError ? (
                    <ErrorState compact error={error} onRetry={() => refetch()} />
                ) : !instances || instances.length === 0 ? (
                    <EmptyState
                        compact
                        icon={Speaker}
                        title="Aucun ampli"
                        description="Détecte ou ajoute ton ampli ci-dessous (MusicCast / YamahaExtendedControl, aucun mot de passe requis)."
                    />
                ) : (
                    <motion.div variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-2">
                        <AnimatePresence>
                            {instances.map((y) => (
                                <DeviceRow
                                    key={y.id}
                                    icon={Speaker}
                                    tone="orange"
                                    name={y.name}
                                    address={y.url}
                                    badges={!y.is_enabled ? <span className="rounded-full bg-slate-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300">Désactivé</span> : null}
                                    autoTest={y.is_enabled}
                                    onTest={async () => {
                                        const r = await test.mutateAsync(y.id);
                                        if (!r.ok) return { ok: false, label: r.detail || "Injoignable" };
                                        const power = r.power === "on" ? "allumé" : r.power === "standby" ? "en veille" : r.power;
                                        return {
                                            ok: true,
                                            label: [r.model, power, r.volume_pct != null ? `volume ${r.volume_pct} %` : null].filter(Boolean).join(" · "),
                                        };
                                    }}
                                    onEdit={() => setEditing(y)}
                                    onDelete={() => del.mutateAsync(y.id)}
                                    deleteDescription="L'ampli disparaîtra de la télécommande du Salon. L'appareil lui-même n'est pas modifié."
                                />
                            ))}
                        </AnimatePresence>
                    </motion.div>
                )}
            </Panel>

            {/* ── Profils audio par pièce ─────────────────────── */}
            <RoomProfilesPanel hasAmp={(instances ?? []).some((y) => y.is_enabled)} />

            {/* ── Ajouter ─────────────────────────────────────── */}
            <Panel
                title="Ajouter un ampli"
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
                <p className="text-xs leading-relaxed text-muted-foreground">
                    L&apos;ampli doit être branché au réseau (Ethernet ou Wi-Fi) et compatible MusicCast. Aucune authentification n&apos;est nécessaire.
                </p>
                <DiscoveryResults
                    devices={found}
                    scanning={discover.isPending}
                    icon={Speaker}
                    selectedKey={prefill ? found?.find((f) => f.url === prefill.url)?.key : null}
                    onPick={(d) => setPrefill({ name: d.name, url: d.url, nonce: Date.now() })}
                />
                <YamahaForm
                    idPrefix="yamaha-add"
                    prefill={prefill}
                    pending={add.isPending}
                    submitLabel="Enregistrer"
                    submitIcon={<Plus />}
                    resetOnSuccess
                    onSubmit={async (payload) => {
                        try {
                            const r = await add.mutateAsync({ ...payload, is_enabled: true });
                            toast.success(r?.message ?? "Ampli enregistré", { description: payload.url });
                            setPrefill(null);
                        } catch (e) {
                            toast.error("Enregistrement impossible", { description: e instanceof Error ? e.message : undefined });
                            throw e;
                        }
                    }}
                />
            </Panel>

            {/* ── Modifier ────────────────────────────────────── */}
            <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Modifier {shownEditing?.name}</DialogTitle>
                        <DialogDescription>Change le nom ou l&apos;adresse de l&apos;ampli sans créer de doublon.</DialogDescription>
                    </DialogHeader>
                    {shownEditing && (
                        <YamahaForm
                            key={shownEditing.id}
                            idPrefix="yamaha-edit"
                            initial={shownEditing}
                            pending={update.isPending}
                            submitLabel="Enregistrer"
                            onCancel={() => setEditing(null)}
                            onSubmit={async (payload) => {
                                try {
                                    await update.mutateAsync({ id: shownEditing.id, ...payload });
                                    toast.success("Ampli mis à jour", { description: payload.name });
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

/* ── Formulaire ampli (ajout + modification) ─────────────────── */

function YamahaForm({
    idPrefix,
    initial,
    prefill,
    pending,
    submitLabel,
    submitIcon,
    resetOnSuccess,
    onSubmit,
    onCancel,
}: {
    idPrefix: string;
    initial?: YamahaInstance | null;
    prefill?: { name: string; url: string; nonce: number } | null;
    pending?: boolean;
    submitLabel: string;
    submitIcon?: React.ReactNode;
    resetOnSuccess?: boolean;
    onSubmit: (payload: { name: string; url: string }) => Promise<unknown>;
    onCancel?: () => void;
}) {
    const [name, setName] = useState(initial?.name ?? "");
    const [url, setUrl] = useState(initial?.url ?? "");
    const [submitted, setSubmitted] = useState(false);

    useEffect(() => {
        if (!prefill) return;
        setName(prefill.name);
        setUrl(prefill.url);
    }, [prefill]);

    // L'ampli accepte une IP seule : on n'exige donc pas « http:// ».
    const urlErr = !url.trim() ? "L'adresse est obligatoire." : /\s/.test(url.trim()) ? "L'adresse ne doit pas contenir d'espace." : null;

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        if (urlErr) return;
        try {
            await onSubmit({ name: name.trim() || "Ampli Yamaha", url: normalizeAddress(url) });
            if (resetOnSuccess) {
                setName("");
                setUrl("");
                setSubmitted(false);
            }
        } catch {
            // Toast affiché par le parent ; on garde la saisie.
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField id={`${idPrefix}-name`} label="Nom">
                    <Input id={`${idPrefix}-name`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Ampli du salon" />
                </FormField>
                <FormField id={`${idPrefix}-url`} label="Adresse IP ou URL" error={submitted ? urlErr : null}>
                    <Input
                        id={`${idPrefix}-url`}
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="192.168.1.30"
                        inputMode="url"
                        spellCheck={false}
                        autoComplete="off"
                        className="font-mono text-sm"
                        aria-invalid={submitted && !!urlErr}
                    />
                </FormField>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                {onCancel && (
                    <Button type="button" variant="ghost" onClick={onCancel} disabled={pending}>
                        Annuler
                    </Button>
                )}
                <Button type="submit" disabled={pending}>
                    {pending ? <Loader2 className="animate-spin" /> : submitIcon ?? <Save />}
                    {submitLabel}
                </Button>
            </div>
        </form>
    );
}
