"use client";

/**
 * Page de connexion — sobre, façon écran d'accueil d'une app Apple :
 * icône de l'app, nom, un champ mot de passe, un bouton bleu.
 * ----------------------------------------------------------------
 * Messages d'erreur distincts (avant : tout affichait « Mot de passe
 * incorrect », y compris un backend éteint ou l'anti brute-force) :
 *   - 401 → mot de passe incorrect (+ secousse du champ, comme iOS)
 *   - 429 → trop de tentatives (limite 5/min côté API)
 *   - réseau → backend injoignable
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Eye, EyeOff, Loader2, ShieldAlert } from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login, isAuthenticated } from "@/lib/api-client";
import { useSetupStatus } from "@/hooks/use-setup";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Traduit l'erreur technique en message compréhensible. */
function explain(err: unknown): string {
    const msg = err instanceof Error ? err.message : String(err);
    if (/not authenticated|401|incorrect|invalid/i.test(msg)) return "Mot de passe incorrect.";
    if (/rate|429|too many/i.test(msg)) return "Trop de tentatives. Patiente une minute avant de réessayer.";
    if (/failed to fetch|network|load failed/i.test(msg)) return "Serveur injoignable. Vérifie que le conteneur arrmada-backend tourne.";
    return msg || "Connexion impossible.";
}

export default function LoginPage() {
    const router = useRouter();
    const [password, setPassword] = useState("");
    const [show, setShow] = useState(false);
    const [error, setError] = useState("");
    const [shakeKey, setShakeKey] = useState(0);
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const { data: setupStatus, isLoading: setupLoading } = useSetupStatus();

    useEffect(() => {
        // Installation non faite → assistant ; déjà connecté → accueil.
        if (!setupLoading && setupStatus && !setupStatus.is_configured) {
            router.replace("/setup");
            return;
        }
        if (isAuthenticated()) router.replace("/dashboard");
    }, [router, setupStatus, setupLoading]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(password);
            setSuccess(true);
            // Laisse jouer le fondu de sortie avant de changer de page.
            setTimeout(() => router.push("/dashboard"), 300);
        } catch (err) {
            setError(explain(err));
            setShakeKey((k) => k + 1);
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-[100dvh] items-center justify-center px-6 pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]">
            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={success ? { opacity: 0, scale: 0.98 } : { opacity: 1, y: 0 }}
                transition={{ duration: success ? 0.25 : 0.45, ease: EASE_OUT }}
                className="w-full max-w-[340px]"
            >
                {/* Icône et nom de l'app */}
                <div className="flex flex-col items-center text-center">
                    <div className="h-[76px] w-[76px] overflow-hidden rounded-[18px] shadow-[0_8px_24px_-8px_rgb(0_0_0/0.8)]">
                        <BrandIcon title="ArrMada" />
                    </div>
                    <h1 className="mt-5 text-[28px] font-bold tracking-tight">ArrMada</h1>
                    <p className="mt-1 text-[15px] text-muted-foreground">Connecte-toi pour accéder à ta médiathèque.</p>
                </div>

                <form onSubmit={handleSubmit} className="mt-8 space-y-3">
                    <div key={shakeKey} className={cn("relative", shakeKey > 0 && "animate-shake")}>
                        <Input
                            id="password"
                            type={show ? "text" : "password"}
                            placeholder="Mot de passe"
                            value={password}
                            onChange={(e) => {
                                setPassword(e.target.value);
                                if (error) setError("");
                            }}
                            className={cn("h-12 rounded-[14px] pr-12 text-[17px]", error && "ring-2 ring-destructive/70 focus-visible:ring-destructive/70")}
                            autoFocus
                            autoComplete="current-password"
                            required
                            aria-invalid={!!error}
                            aria-describedby={error ? "login-error" : undefined}
                        />
                        <button
                            type="button"
                            onClick={() => setShow((s) => !s)}
                            className="absolute right-1.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
                            aria-label={show ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                        >
                            {show ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
                        </button>
                    </div>

                    <AnimatePresence mode="wait">
                        {error && (
                            <motion.p
                                id="login-error"
                                role="alert"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                className="flex items-start gap-2 overflow-hidden px-1 text-[14px] text-destructive"
                            >
                                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                                {error}
                            </motion.p>
                        )}
                    </AnimatePresence>

                    <Button type="submit" size="lg" className="w-full rounded-[14px]" disabled={loading || !password}>
                        {loading && <Loader2 className="animate-spin" />}
                        {loading ? "Connexion…" : "Se connecter"}
                    </Button>
                </form>

                <p className="mt-8 text-center text-[12px] leading-relaxed text-muted-foreground/80">
                    Mot de passe = variable <span className="font-mono text-muted-foreground">ARRMADA_AUTH_SECRET</span> du fichier{" "}
                    <span className="font-mono text-muted-foreground">.env</span>
                </p>
            </motion.div>
        </div>
    );
}
