"use client";

/**
 * Formulaire d'un lecteur Kodi (ajout ET modification).
 * ----------------------------------------------------------------
 * - Placeholders génériques (avant : nom, IP et utilisateur PERSONNELS
 *   pré-remplis dans le code : « Kodi Salon », 192.168.2.140, « kodi »).
 * - Mot de passe : laissé vide = conservé (le backend ne l'écrase plus) ;
 *   il n'est jamais renvoyé au navigateur.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Lock, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { FormField, SecretInput, validateHttpUrl } from "@/components/settings/form-field";
import { kodiUsername, type KodiInstance, type KodiSettingsPayload } from "@/hooks/use-kodi";

interface KodiFormProps {
    /** Instance à modifier (null = ajout). */
    initial?: KodiInstance | null;
    /** Pré-remplissage depuis la détection réseau ; `nonce` change à chaque clic. */
    prefill?: { name: string; url: string; nonce: number } | null;
    submitLabel: string;
    submitIcon?: React.ReactNode;
    pending?: boolean;
    onSubmit: (payload: KodiSettingsPayload) => Promise<unknown>;
    onCancel?: () => void;
    /** Vide le formulaire après un ajout réussi. */
    resetOnSuccess?: boolean;
    /** Préfixe des id HTML (deux formulaires peuvent coexister). */
    idPrefix: string;
}

export function KodiForm({
    initial,
    prefill,
    submitLabel,
    submitIcon,
    pending,
    onSubmit,
    onCancel,
    resetOnSuccess,
    idPrefix,
}: KodiFormProps) {
    const [name, setName] = useState(initial?.name ?? "");
    const [url, setUrl] = useState(initial?.url ?? "");
    const [username, setUsername] = useState(initial ? kodiUsername(initial) : "");
    const [password, setPassword] = useState("");
    const [enabled, setEnabled] = useState(initial?.is_enabled ?? true);
    const [submitted, setSubmitted] = useState(false);

    // Clic sur un Kodi détecté → on remplit nom + URL.
    useEffect(() => {
        if (!prefill) return;
        setName(prefill.name);
        setUrl(prefill.url);
    }, [prefill]);

    const urlErr = validateHttpUrl(url, "http://192.168.1.20:8080");
    const hasStoredPassword = !!initial?.has_password;

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        if (urlErr) return;
        try {
            await onSubmit({
                name: name.trim() || "Kodi",
                url: url.trim().replace(/\/+$/, ""),
                username: username.trim(),
                password,
                is_enabled: enabled,
            });
            setPassword("");
            if (resetOnSuccess) {
                setName("");
                setUrl("");
                setUsername("");
                setSubmitted(false);
            }
        } catch {
            // Le parent affiche le toast d'erreur ; on garde la saisie.
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField id={`${idPrefix}-name`} label="Nom">
                    <Input id={`${idPrefix}-name`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Kodi du salon" />
                </FormField>
                <FormField
                    id={`${idPrefix}-url`}
                    label="Adresse"
                    error={submitted ? urlErr : null}
                    hint="Port 8080 par défaut (serveur web de Kodi)."
                >
                    <Input
                        id={`${idPrefix}-url`}
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="http://192.168.1.20:8080"
                        inputMode="url"
                        spellCheck={false}
                        autoComplete="off"
                        className="font-mono text-sm"
                        aria-invalid={submitted && !!urlErr}
                    />
                </FormField>
                <FormField id={`${idPrefix}-user`} label="Utilisateur" hint="Celui défini dans Kodi (souvent « kodi »).">
                    <Input
                        id={`${idPrefix}-user`}
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="kodi"
                        autoComplete="off"
                        spellCheck={false}
                    />
                </FormField>
                <FormField
                    id={`${idPrefix}-pass`}
                    label="Mot de passe"
                    hint={hasStoredPassword ? "Un mot de passe est enregistré : laisse vide pour le conserver." : "Laisse vide si Kodi n'en demande pas."}
                >
                    <SecretInput
                        id={`${idPrefix}-pass`}
                        icon={Lock}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder={hasStoredPassword ? "•••••••• (inchangé)" : "Mot de passe"}
                    />
                </FormField>
            </div>

            {initial && (
                <div className="flex items-center justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/30 px-3.5 py-3">
                    <div>
                        <Label htmlFor={`${idPrefix}-enabled`} className="text-sm">
                            Lecteur actif
                        </Label>
                        <p className="text-xs text-muted-foreground">Désactivé, il n&apos;est plus piloté ni scanné.</p>
                    </div>
                    <Switch id={`${idPrefix}-enabled`} checked={enabled} onCheckedChange={setEnabled} />
                </div>
            )}

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
