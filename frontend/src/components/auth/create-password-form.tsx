"use client";

/**
 * Création du mot de passe administrateur (premier lancement).
 * ----------------------------------------------------------------
 * Utilisé par l'assistant d'installation (étape « Sécurité ») et par la
 * page de connexion quand l'instance n'a pas encore de mot de passe
 * (ex : installation existante qui tournait avec la valeur d'exemple du
 * .env, désormais refusée). L'API n'accepte cette création qu'UNE fois :
 * ensuite, changement uniquement depuis Paramètres (mot de passe actuel
 * exigé) ou via `arrmada-cli` dans le conteneur.
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, Loader2, Lock, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormField, SecretInput } from "@/components/settings/form-field";
import { createAdminPassword } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export const MIN_PASSWORD_LENGTH = 8;

/** Indication de robustesse très simple (longueur + variété). */
function strength(pw: string): { score: 0 | 1 | 2 | 3; label: string } {
    if (pw.length < MIN_PASSWORD_LENGTH) return { score: 0, label: `${MIN_PASSWORD_LENGTH} caractères minimum` };
    const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
    if (pw.length >= 14 && kinds >= 2) return { score: 3, label: "Solide" };
    if (pw.length >= 10 || kinds >= 3) return { score: 2, label: "Correct" };
    return { score: 1, label: "Faible — allonge-le" };
}

/** Traduit l'erreur de l'API en message compréhensible. */
function explain(err: unknown): string {
    const msg = err instanceof Error ? err.message : String(err);
    if (/already exists|409/i.test(msg)) return "Un mot de passe existe déjà : recharge la page et connecte-toi.";
    if (/rate|429|too many/i.test(msg)) return "Trop de tentatives. Patiente une minute.";
    if (/unavailable|502|failed to fetch|network|load failed/i.test(msg)) return "Backend injoignable. Vérifie que le conteneur arrmada tourne.";
    return msg || "Création impossible.";
}

export function CreatePasswordForm({
    onCreated,
    submitLabel = "Créer le mot de passe",
    className,
}: {
    /** Appelé une fois le mot de passe créé ET la session ouverte. */
    onCreated: () => void;
    submitLabel?: string;
    className?: string;
}) {
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const s = strength(password);
    const tooShort = password.length < MIN_PASSWORD_LENGTH;
    const mismatch = confirm !== password;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        setError("");
        if (tooShort || mismatch) return;
        setLoading(true);
        try {
            await createAdminPassword(password);
            onCreated();
        } catch (err) {
            setError(explain(err));
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={cn("space-y-4", className)} noValidate>
            <FormField
                id="new-password"
                label="Mot de passe administrateur"
                error={submitted && tooShort ? `Au moins ${MIN_PASSWORD_LENGTH} caractères.` : null}
            >
                <SecretInput
                    id="new-password"
                    icon={Lock}
                    value={password}
                    placeholder="Choisis un mot de passe"
                    autoFocus
                    onChange={(e) => {
                        setPassword(e.target.value);
                        if (error) setError("");
                    }}
                    aria-invalid={submitted && tooShort}
                />
            </FormField>

            {/* Jauge de robustesse */}
            <div className="flex items-center gap-2" aria-live="polite">
                <div className="flex flex-1 gap-1">
                    {[1, 2, 3].map((i) => (
                        <span
                            key={i}
                            className={cn(
                                "h-1 flex-1 rounded-full bg-white/10 transition-colors duration-300",
                                s.score >= i && (s.score === 1 ? "bg-warning" : s.score === 2 ? "bg-primary" : "bg-success"),
                            )}
                        />
                    ))}
                </div>
                <span className="w-36 text-right text-[11px] text-muted-foreground">{password ? s.label : ""}</span>
            </div>

            <FormField
                id="confirm-password"
                label="Confirmation"
                error={submitted && !tooShort && mismatch ? "Les deux saisies diffèrent." : null}
            >
                <SecretInput
                    id="confirm-password"
                    icon={ShieldCheck}
                    value={confirm}
                    placeholder="Retape-le"
                    onChange={(e) => setConfirm(e.target.value)}
                    aria-invalid={submitted && mismatch}
                />
            </FormField>

            <AnimatePresence>
                {error && (
                    <motion.p
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        role="alert"
                        className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
                    >
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
                    </motion.p>
                )}
            </AnimatePresence>

            <Button type="submit" size="lg" className="w-full" disabled={loading || !password}>
                {loading ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
                {loading ? "Enregistrement…" : submitLabel}
            </Button>

            <p className="text-center text-[11px] leading-relaxed text-muted-foreground/80">
                Stocké haché (scrypt) dans le dossier <span className="font-mono">data</span> du conteneur. Oublié ? <span className="font-mono">docker exec -it arrmada arrmada-cli set-password</span>
            </p>
        </form>
    );
}
