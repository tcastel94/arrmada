"use client";

/**
 * Changement du mot de passe administrateur (Paramètres → Général).
 * ----------------------------------------------------------------
 * Le mot de passe actuel est exigé (une session volée ne suffit pas).
 * L'API répond 403 si l'actuel est faux — pas 401, qui déconnecterait.
 * Si l'instance tournait encore avec ARRMADA_AUTH_SECRET (.env), ce
 * formulaire la migre vers un mot de passe haché : la variable peut
 * ensuite être retirée du .env.
 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Lock, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/shared/panel";
import { FormField, SecretInput } from "@/components/settings/form-field";
import { MIN_PASSWORD_LENGTH } from "@/components/auth/create-password-form";
import { changeAdminPassword } from "@/lib/api-client";

function explain(err: unknown): string {
    const msg = err instanceof Error ? err.message : String(err);
    if (/current password|403/i.test(msg)) return "Mot de passe actuel incorrect.";
    if (/rate|429|too many/i.test(msg)) return "Trop de tentatives. Patiente une minute.";
    return msg || "Changement impossible.";
}

export function PasswordPanel({ source }: { source?: "file" | "env" | "none" }) {
    const queryClient = useQueryClient();
    const [current, setCurrent] = useState("");
    const [next, setNext] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const tooShort = next.length < MIN_PASSWORD_LENGTH;
    const mismatch = confirm !== next;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        setError("");
        if (!current || tooShort || mismatch) return;
        setLoading(true);
        try {
            await changeAdminPassword(current, next);
            toast.success("Mot de passe modifié");
            // L'origine du mot de passe a pu passer de "env" à "file".
            void queryClient.invalidateQueries({ queryKey: ["settings"] });
            setCurrent("");
            setNext("");
            setConfirm("");
            setSubmitted(false);
        } catch (err) {
            setError(explain(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <Panel title="Mot de passe administrateur" icon={KeyRound} iconClassName="text-primary" className="h-full">
            <form onSubmit={handleSubmit} className="space-y-3" noValidate>
                {source === "env" && (
                    <p className="rounded-xl border border-warning/25 bg-warning/10 px-3.5 py-2.5 text-xs text-warning/90">
                        Ton mot de passe vient encore de <span className="font-mono">ARRMADA_AUTH_SECRET</span> (en clair dans le
                        .env). Définis-en un ici : il sera stocké haché et la variable pourra être supprimée.
                    </p>
                )}
                <FormField id="pw-current" label="Mot de passe actuel" error={submitted && !current ? "Obligatoire." : null}>
                    <SecretInput
                        id="pw-current"
                        icon={Lock}
                        value={current}
                        autoComplete="current-password"
                        onChange={(e) => setCurrent(e.target.value)}
                    />
                </FormField>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <FormField
                        id="pw-new"
                        label="Nouveau"
                        error={submitted && tooShort ? `${MIN_PASSWORD_LENGTH} caractères minimum.` : null}
                    >
                        <SecretInput id="pw-new" icon={ShieldCheck} value={next} onChange={(e) => setNext(e.target.value)} />
                    </FormField>
                    <FormField
                        id="pw-confirm"
                        label="Confirmation"
                        error={submitted && !tooShort && mismatch ? "Les deux saisies diffèrent." : null}
                    >
                        <SecretInput id="pw-confirm" icon={ShieldCheck} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
                    </FormField>
                </div>
                {error && (
                    <p role="alert" className="text-sm text-destructive">
                        {error}
                    </p>
                )}
                <Button type="submit" disabled={loading || !next} className="w-full sm:w-auto">
                    {loading ? <Loader2 className="animate-spin" /> : <KeyRound />}
                    {loading ? "Enregistrement…" : "Changer le mot de passe"}
                </Button>
            </form>
        </Panel>
    );
}
