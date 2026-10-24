"use client";

/**
 * Briques de formulaire des pages de réglages.
 * ----------------------------------------------------------------
 * - FormField : libellé + champ + aide OU message d'erreur (en rouge).
 * - SecretInput : champ mot de passe / clé avec bouton « afficher ».
 * Avant : chaque page assemblait Label/Input à la main, sans message
 * d'erreur visible ni bouton pour vérifier ce qu'on a collé.
 */
import { forwardRef, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import { Eye, EyeOff, type LucideIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function FormField({
    id,
    label,
    hint,
    error,
    children,
    className,
}: {
    id: string;
    label: ReactNode;
    hint?: ReactNode;
    error?: string | null;
    children: ReactNode;
    className?: string;
}) {
    return (
        <div className={cn("space-y-1.5", className)}>
            <Label htmlFor={id} className="text-xs">
                {label}
            </Label>
            {children}
            {error ? (
                <p className="text-xs text-destructive" role="alert">
                    {error}
                </p>
            ) : hint ? (
                <p className="text-[11px] leading-relaxed text-muted-foreground">{hint}</p>
            ) : null}
        </div>
    );
}

type SecretInputProps = Omit<ComponentPropsWithoutRef<typeof Input>, "type"> & {
    /** Icône à gauche (ex: KeyRound, Lock). */
    icon?: LucideIcon;
};

/** Champ secret avec bascule afficher / masquer (accessible au clavier). */
export const SecretInput = forwardRef<HTMLInputElement, SecretInputProps>(
    ({ className, icon: Icon, ...props }, ref) => {
        const [visible, setVisible] = useState(false);
        return (
            <div className="relative">
                {Icon && (
                    <Icon className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                )}
                <Input
                    ref={ref}
                    type={visible ? "text" : "password"}
                    autoComplete="new-password"
                    spellCheck={false}
                    className={cn("pr-10 font-mono text-sm placeholder:font-sans", Icon && "pl-9", className)}
                    {...props}
                />
                <button
                    type="button"
                    onClick={() => setVisible((v) => !v)}
                    className="absolute right-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                    aria-label={visible ? "Masquer" : "Afficher"}
                >
                    {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
            </div>
        );
    },
);
SecretInput.displayName = "SecretInput";

/** Valide une URL http(s) ; renvoie un message d'erreur FR ou null. */
export function validateHttpUrl(url: string, example = "http://192.168.1.10:8080"): string | null {
    if (!url.trim()) return "L'adresse est obligatoire.";
    try {
        const u = new URL(url.trim());
        if (u.protocol !== "http:" && u.protocol !== "https:") return "L'adresse doit commencer par http:// ou https://";
        return null;
    } catch {
        return `Adresse invalide (ex : ${example}).`;
    }
}
