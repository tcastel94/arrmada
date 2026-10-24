"use client";

/**
 * Réglages → Kodi → « Appareils » (ADR-003 § 4 et § 6).
 * ----------------------------------------------------------------
 * - Appairer une TV : saisir le code affiché par Kodi (ou scanner son QR
 *   code, qui ouvre cette page avec `?pair=CODE` et pré-remplit la boîte),
 *   puis choisir le nom, la pièce et l'ampli de l'appareil.
 * - Même chose pour un écran d'appoint (tablette sous la TV, page /ecran) :
 *   il affiche ce qui passe sur la TV de SA pièce, sans rien pouvoir piloter.
 * - Liste des appareils : type, pièce, ampli, dernière activité.
 * - Modifier (nom, pièce, ampli) ou révoquer (le jeton cesse de marcher).
 * - Écran d'appoint sous Fully Kiosk : mode kiosk pendant un média
 *   (kiosk-section.tsx), piloté par le serveur.
 *
 * Pourquoi l'ampli est choisi ici : la TV pilote ensuite TOUJOURS l'ampli de
 * sa pièce (écran Salon, préréglage au lancement d'un film). Le backend
 * l'impose, la TV ne peut pas viser un autre ampli.
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Briefcase, Link2, Loader2, Speaker, Tablet, Tv, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { DeviceRow } from "@/components/settings/device-row";
import { KioskSection } from "@/components/settings/kiosk-section";
import { FormField } from "@/components/settings/form-field";
import { useStickyValue } from "@/components/settings/use-sticky-value";
import { ROOM_META } from "@/components/remote/yamaha-audio";
import {
    DEVICE_ROOMS,
    normalizePairCode,
    roomHasAmp,
    usePairDevice,
    useDevices,
    useRevokeDevice,
    useUpdateDevice,
    type DeviceRoom,
    type DeviceSettings,
    type PairedDevice,
} from "@/hooks/use-devices";
import { useYamahaSettings } from "@/hooks/use-yamaha";
import { plural, timeAgo } from "@/lib/format";
import { stagger } from "@/lib/motion";

/** Longueur du code affiché par la TV (voir backend, USER_CODE_LENGTH). */
const CODE_LENGTH = 6;
/** Valeur du menu « ampli » pour « le premier ampli actif ». */
const FIRST_AVR = "auto";
const NO_AVR = "none"; // bureau : choix grisé

export function DevicesPanel() {
    const { data: devices, isLoading, isError, error, refetch } = useDevices();
    const pair = usePairDevice();
    const update = useUpdateDevice();
    const revoke = useRevokeDevice();

    const [pairOpen, setPairOpen] = useState(false);
    const [pairCode, setPairCode] = useState("");
    const [editing, setEditing] = useState<PairedDevice | null>(null);
    const shownEditing = useStickyValue(editing);

    // QR code scanné sur la TV → /settings/kodi?pair=CODE : boîte pré-remplie.
    // (Lecture directe de l'URL : pas besoin de useSearchParams et de son
    // enveloppe <Suspense> obligatoire au moment du build.)
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const code = normalizePairCode(params.get("pair") ?? "");
        if (!code) return;
        setPairCode(code);
        setPairOpen(true);
        params.delete("pair");
        const query = params.toString();
        window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    }, []);

    return (
        <>
            <Panel
                title="Appareils (TV et écrans)"
                icon={Tv}
                iconClassName="text-primary"
                action={
                    <Button
                        variant="glow"
                        size="sm"
                        onClick={() => {
                            setPairCode("");
                            setPairOpen(true);
                        }}
                    >
                        <Link2 />
                        Appairer
                    </Button>
                }
                bodyClassName="space-y-3"
            >
                <p className="text-xs leading-relaxed text-muted-foreground">
                    Chaque Kodi appairé a son propre accès : plus de mot de passe admin dans la TV, et tu peux le révoquer d&apos;un
                    clic. Il pilote toujours l&apos;ampli de sa pièce (aucun au bureau). Sur la TV : <span className="text-foreground">ArrMada → Réglages → Appairer cette TV</span>.
                    Écran d&apos;appoint (tablette sous la TV) : ouvre <span className="font-mono text-foreground">/ecran</span> de la web app sur la
                    tablette, elle affiche un code à valider ici. Elle montre l&apos;heure de fin du film en cours, sans rien pouvoir piloter.
                </p>
                {isLoading ? (
                    <TableSkeleton rows={2} />
                ) : isError ? (
                    <ErrorState compact error={error} onRetry={() => refetch()} />
                ) : !devices || devices.length === 0 ? (
                    <EmptyState
                        compact
                        icon={Tv}
                        title="Aucune TV appairée"
                        description="Lance l'appairage sur la TV : elle affiche un code et un QR code à valider ici."
                    />
                ) : (
                    <motion.div variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-2">
                        <AnimatePresence>
                            {devices.map((d) => (
                                <DeviceRow
                                    key={d.id}
                                    icon={d.kind === "screen" ? Tablet : Tv}
                                    tone="sky"
                                    name={d.name}
                                    badges={
                                        <>
                                            <RoomBadge room={d.room} />
                                            {d.kind === "screen" && (
                                                <span className="inline-flex items-center rounded-full bg-white/5 px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                                                    Écran d&apos;appoint
                                                </span>
                                            )}
                                            {d.kind === "screen" && d.kiosk_control && (
                                                <span className="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                                                    {d.kiosk_locked ? "Kiosk : verrouillée" : "Kiosk pendant un média"}
                                                </span>
                                            )}
                                        </>
                                    }
                                    meta={
                                        <span className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5">
                                            <span className="inline-flex items-center gap-1">
                                                <Speaker className="h-3 w-3" />
                                                {/* Bureau : aucun ampli (le serveur le refuse), pas « premier actif » */}
                                                {(d.has_amp ?? roomHasAmp(d.room))
                                                    ? (d.avr_name ?? "Premier ampli actif")
                                                    : "Pas d'ampli"}
                                            </span>
                                            {d.platform && <span>{d.platform}</span>}
                                            <span>
                                                {d.last_seen_at ? `Vu ${timeAgo(d.last_seen_at)}` : "Jamais connecté"}
                                                {d.last_ip ? ` · ${d.last_ip}` : ""}
                                            </span>
                                        </span>
                                    }
                                    onEdit={() => setEditing(d)}
                                    onDelete={() => revoke.mutateAsync(d.id)}
                                    deleteTitle={`Révoquer ${d.name} ?`}
                                    deleteDescription="Son accès est coupé immédiatement. Pour l'utiliser à nouveau, il faudra relancer l'appairage sur la TV."
                                />
                            ))}
                        </AnimatePresence>
                    </motion.div>
                )}
                {devices && devices.length > 0 && (
                    <p className="text-[11px] text-muted-foreground">{plural(devices.length, "appareil appairé", "appareils appairés")}</p>
                )}
            </Panel>

            {/* ── Appairer ─────────────────────────────────────── */}
            <Dialog open={pairOpen} onOpenChange={setPairOpen}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Appairer un appareil</DialogTitle>
                        <DialogDescription>
                            Saisis le code affiché par Kodi ou par l&apos;écran d&apos;appoint, puis choisis la pièce et l&apos;ampli de cet appareil.
                        </DialogDescription>
                    </DialogHeader>
                    <DeviceForm
                        key={pairCode || "new"}
                        idPrefix="pair"
                        withCode
                        initialCode={pairCode}
                        submitLabel="Appairer"
                        pending={pair.isPending}
                        onCancel={() => setPairOpen(false)}
                        onSubmit={async ({ code, ...settings }) => {
                            try {
                                const r = await pair.mutateAsync({ user_code: code, ...settings });
                                toast.success(`${r.device.name} est appairé`, {
                                    description: "L'appareil le confirme d'ici quelques secondes.",
                                });
                                setPairOpen(false);
                            } catch (e) {
                                toast.error("Appairage impossible", { description: e instanceof Error ? e.message : undefined });
                                throw e;
                            }
                        }}
                    />
                </DialogContent>
            </Dialog>

            {/* ── Modifier ─────────────────────────────────────── */}
            <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
                <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Modifier {shownEditing?.name}</DialogTitle>
                        <DialogDescription>Le changement de pièce ou d&apos;ampli s&apos;applique dès la prochaine action sur la TV.</DialogDescription>
                    </DialogHeader>
                    {shownEditing && (
                        <DeviceForm
                            key={shownEditing.id}
                            idPrefix="device-edit"
                            initial={shownEditing}
                            submitLabel="Enregistrer"
                            pending={update.isPending}
                            onCancel={() => setEditing(null)}
                            onSubmit={async ({ name, room, avr_service_id }) => {
                                try {
                                    await update.mutateAsync({ id: shownEditing.id, name, room, avr_service_id });
                                    toast.success("Appareil mis à jour", { description: name });
                                    setEditing(null);
                                } catch (e) {
                                    toast.error("Modification impossible", { description: e instanceof Error ? e.message : undefined });
                                    throw e;
                                }
                            }}
                        />
                    )}
                    {shownEditing?.kind === "screen" && (
                        // État à jour (verrouillée, mot de passe réglé) : la liste, pas l'instantané du dialogue
                        <KioskSection
                            key={`kiosk-${shownEditing.id}`}
                            device={devices?.find((d) => d.id === shownEditing.id) ?? shownEditing}
                        />
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}

/** Libellé et icône d'une pièce : ceux de la télécommande, plus le bureau (sans ampli). */
function roomMeta(room: DeviceRoom): { label: string; icon: LucideIcon } {
    if (room === "bureau") return { label: "Bureau", icon: Briefcase };
    return ROOM_META[room] ?? ROOM_META.salon;
}

function RoomBadge({ room }: { room: DeviceRoom }) {
    const meta = roomMeta(room);
    const Icon = meta.icon;
    return (
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
            <Icon className="h-3 w-3" />
            {meta.label}
        </span>
    );
}

/* ── Formulaire commun : appairage (avec code) et modification ─── */

function DeviceForm({
    idPrefix,
    withCode = false,
    initialCode = "",
    initial,
    submitLabel,
    pending,
    onSubmit,
    onCancel,
}: {
    idPrefix: string;
    withCode?: boolean;
    initialCode?: string;
    initial?: PairedDevice;
    submitLabel: string;
    pending: boolean;
    onSubmit: (values: DeviceSettings & { code: string }) => Promise<unknown>;
    onCancel: () => void;
}) {
    const { data: amps } = useYamahaSettings();
    const [code, setCode] = useState(initialCode);
    const [name, setName] = useState(initial?.name ?? "");
    const [room, setRoom] = useState<DeviceRoom>(initial?.room ?? "salon");
    const withAmp = roomHasAmp(room);
    const [avr, setAvr] = useState<string>(initial?.avr_service_id ? String(initial.avr_service_id) : FIRST_AVR);
    const [touched, setTouched] = useState(false);

    const codeError = withCode && touched && code.length !== CODE_LENGTH ? `Le code fait ${CODE_LENGTH} caractères` : null;
    const nameError = touched && !name.trim() ? "Donne un nom à l'appareil (ex. « Shield Salon »)" : null;

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setTouched(true);
        if ((withCode && code.length !== CODE_LENGTH) || !name.trim()) return;
        await onSubmit({
            code,
            name: name.trim(),
            room,
            // Bureau : aucun ampli (le serveur l'ignorerait de toute façon)
            avr_service_id: !withAmp || avr === FIRST_AVR ? null : Number(avr),
        }).catch(() => undefined); // l'erreur est déjà affichée (toast)
    };

    return (
        <form onSubmit={submit} className="space-y-4">
            {withCode && (
                <FormField id={`${idPrefix}-code`} label="Code affiché sur l'appareil" error={codeError}>
                    <Input
                        id={`${idPrefix}-code`}
                        value={code}
                        onChange={(e) => setCode(normalizePairCode(e.target.value).slice(0, CODE_LENGTH))}
                        placeholder="K7P4QX"
                        autoComplete="off"
                        autoFocus={!initialCode}
                        className="h-12 text-center font-mono text-2xl tracking-[0.4em]"
                    />
                </FormField>
            )}
            <FormField id={`${idPrefix}-name`} label="Nom de l'appareil" error={nameError}>
                <Input
                    id={`${idPrefix}-name`}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Shield Salon"
                    maxLength={100}
                    autoFocus={!!initialCode}
                />
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                    id={`${idPrefix}-room`}
                    label="Pièce"
                    hint={withAmp ? "Préréglage audio appliqué en lançant un film." : "Pas d'ampli au bureau : aucun préréglage, rien à piloter."}
                >
                    <Select value={room} onValueChange={(v) => setRoom(v as DeviceRoom)}>
                        <SelectTrigger id={`${idPrefix}-room`}>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {DEVICE_ROOMS.map((r) => (
                                <SelectItem key={r} value={r}>
                                    {roomMeta(r).label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FormField>
                <FormField id={`${idPrefix}-avr`} label="Ampli de cette pièce" hint="Celui que la TV pilote (volume, préréglages), ou que l'écran d'appoint affiche.">
                    <Select value={withAmp ? avr : NO_AVR} onValueChange={setAvr} disabled={!withAmp}>
                        <SelectTrigger id={`${idPrefix}-avr`}>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {!withAmp && <SelectItem value={NO_AVR}>Pas d&apos;ampli dans cette pièce</SelectItem>}
                            <SelectItem value={FIRST_AVR}>Premier ampli actif</SelectItem>
                            {(amps ?? []).map((a) => (
                                <SelectItem key={a.id} value={String(a.id)}>
                                    {a.name}
                                    {!a.is_enabled ? " (désactivé)" : ""}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FormField>
            </div>
            <div className="flex justify-end gap-2 pt-1">
                <Button type="button" variant="ghost" onClick={onCancel}>
                    Annuler
                </Button>
                <Button type="submit" variant="glow" disabled={pending}>
                    {pending ? <Loader2 className="animate-spin" /> : <Link2 />}
                    {submitLabel}
                </Button>
            </div>
        </form>
    );
}
