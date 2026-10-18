"use client";

/**
 * Écran d'appoint → « Mode kiosk pendant un média » (Fully Kiosk Browser).
 * ----------------------------------------------------------------
 * Quand la TV de la pièce lance un film ou un épisode, le SERVEUR demande à
 * la tablette (API « Remote Admin » de Fully, licence PLUS) de passer au
 * premier plan sur /ecran et de se verrouiller en mode kiosk. À l'arrêt
 * (20 s après, pour laisser l'épisode suivant démarrer), il la déverrouille
 * et la renvoie en arrière-plan.
 *
 * Pourquoi le serveur et pas la page /ecran elle-même : une page en
 * arrière-plan est endormie par Android, elle ne peut pas se réveiller
 * toute seule. Le serveur, lui, reçoit déjà le suivi de lecture de la TV.
 *
 * Le mot de passe Remote Admin est envoyé une fois, gardé chiffré par le
 * serveur, et ne revient jamais ici (on sait seulement s'il est réglé).
 */
import { useState } from "react";
import { Loader2, Lock, LockOpen, PlugZap, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { FormField, SecretInput } from "@/components/settings/form-field";
import { useKioskAction, useUpdateKiosk, type PairedDevice } from "@/hooks/use-devices";

const DEFAULT_PORT = 2323;

export function KioskSection({ device }: { device: PairedDevice }) {
    const update = useUpdateKiosk();
    const action = useKioskAction();
    const [enabled, setEnabled] = useState(device.kiosk_control);
    const [host, setHost] = useState(device.kiosk_host);
    const [port, setPort] = useState(String(device.kiosk_port || DEFAULT_PORT));
    const [password, setPassword] = useState("");

    const portNumber = Number(port);
    const portError = !Number.isInteger(portNumber) || portNumber < 1 || portNumber > 65535 ? "Port entre 1 et 65535" : null;
    const missingPassword = enabled && !device.kiosk_password_set && !password;

    const save = async () => {
        if (portError) return;
        try {
            await update.mutateAsync({
                id: device.id,
                kiosk_control: enabled,
                kiosk_host: host.trim(),
                kiosk_port: portNumber,
                // Vide : on garde le mot de passe déjà enregistré
                ...(password ? { kiosk_password: password } : {}),
            });
            setPassword("");
            toast.success(enabled ? "Mode kiosk activé" : "Mode kiosk désactivé", {
                description: enabled ? "La tablette se verrouillera au prochain média." : undefined,
            });
        } catch (e) {
            toast.error("Réglage refusé", { description: e instanceof Error ? e.message : undefined });
        }
    };

    const run = async (kind: "test" | "lock" | "release") => {
        try {
            const r = await action.mutateAsync({ id: device.id, action: kind });
            const detail =
                kind === "test"
                    ? [r.device?.deviceName, r.device?.appVersionName && `Fully ${r.device.appVersionName}`].filter(Boolean).join(" · ")
                    : r.results?.find((x) => !x.ok)?.message;
            if (r.ok) {
                toast.success(
                    kind === "test" ? "La tablette répond" : kind === "lock" ? "Tablette verrouillée" : "Tablette libérée",
                    { description: detail || undefined },
                );
            } else {
                toast.error("La tablette ne répond pas comme prévu", { description: detail || r.message });
            }
        } catch (e) {
            toast.error("Action impossible", { description: e instanceof Error ? e.message : undefined });
        }
    };

    return (
        <div className="space-y-3 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-sm font-semibold">Mode kiosk pendant un média</p>
                    <p className="text-[11px] leading-relaxed text-muted-foreground">
                        Fully Kiosk passe au premier plan et se verrouille quand la TV de la pièce lance un média, puis se libère à
                        l&apos;arrêt. Dans Fully : licence PLUS, <span className="text-foreground">Remote Administration</span> et{" "}
                        <span className="text-foreground">Remote Admin from Local Network</span> activés, mode kiosk configuré.
                    </p>
                </div>
                <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Mode kiosk pendant un média" />
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
                <FormField
                    id={`kiosk-host-${device.id}`}
                    label="Adresse de la tablette"
                    hint={device.last_ip ? `Vide : la dernière adresse vue (${device.last_ip}).` : "IP du réseau local (ex. 192.168.1.50)."}
                >
                    <Input
                        id={`kiosk-host-${device.id}`}
                        value={host}
                        onChange={(e) => setHost(e.target.value)}
                        placeholder={device.last_ip || "192.168.1.50"}
                        autoComplete="off"
                        className="font-mono text-sm"
                    />
                </FormField>
                <FormField id={`kiosk-port-${device.id}`} label="Port" error={portError}>
                    <Input
                        id={`kiosk-port-${device.id}`}
                        value={port}
                        onChange={(e) => setPort(e.target.value.replace(/\D/g, "").slice(0, 5))}
                        inputMode="numeric"
                        className="font-mono text-sm"
                    />
                </FormField>
            </div>
            <FormField
                id={`kiosk-password-${device.id}`}
                label="Mot de passe Remote Admin"
                error={missingPassword ? "Mot de passe nécessaire pour piloter la tablette" : null}
                hint={device.kiosk_password_set ? "Déjà enregistré (chiffré sur le serveur). Laisse vide pour le garder." : "Celui réglé dans Fully → Remote Administration."}
            >
                <SecretInput
                    id={`kiosk-password-${device.id}`}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={device.kiosk_password_set ? "••••••••" : "Mot de passe"}
                    icon={Lock}
                />
            </FormField>
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <p className="text-[11px] text-muted-foreground">
                    {device.kiosk_locked ? "Verrouillée en ce moment (média en cours)." : "Libre en ce moment."}
                </p>
                <div className="flex flex-wrap gap-2">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={action.isPending || !device.kiosk_password_set}
                        onClick={() => run("test")}
                    >
                        <PlugZap />
                        Tester
                    </Button>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={action.isPending || !device.kiosk_password_set}
                        onClick={() => run("release")}
                        title="Issue de secours : déverrouille la tablette et la renvoie en arrière-plan"
                    >
                        <LockOpen />
                        Libérer
                    </Button>
                    <Button type="button" variant="glow" size="sm" disabled={update.isPending || !!portError || missingPassword} onClick={save}>
                        {update.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                        Enregistrer
                    </Button>
                </div>
            </div>
        </div>
    );
}
