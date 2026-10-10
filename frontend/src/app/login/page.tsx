"use client";

/**
 * Page de connexion — fond aurora, emblème en orbite, carte en verre.
 * ----------------------------------------------------------------
 * Messages d'erreur distincts (avant : tout affichait « Mot de passe
 * incorrect », y compris un backend éteint ou l'anti brute-force) :
 *   - 401 → mot de passe incorrect (+ secousse de la carte)
 *   - 429 → trop de tentatives (limite 5/min côté API)
 *   - réseau → backend injoignable
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrandIcon } from "@/components/brand/brand-mark";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, Loader2, Lock, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuroraBackground } from "@/components/fx/aurora-background";
import { login, isAuthenticated } from "@/lib/api-client";
import { useSetupStatus } from "@/hooks/use-setup";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Traduit l'erreur technique en message compréhensible. */
function explain(err: unknown): string {
    const msg = err instanceof Error ? err.message : String(err);
    if (/not authenticated|401|incorrect|invalid/i.test(msg)) return "Mot de passe incorrect.";
    if (/rate|429|too many/i.test(msg)) return "Trop de tentatives. Patiente une minute avant de réessayer.";
    if (/failed to fetch|network|load failed/i.test(msg)) return "Backend injoignable. Vérifie que le conteneur arrmada-backend tourne.";
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
        // Installation non faite → assistant ; déjà connecté → dashboard.
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
            // Laisse jouer l'animation de sortie avant de changer de page.
            setTimeout(() => router.push("/dashboard"), 550);
        } catch (err) {
            setError(explain(err));
            setShakeKey((k) => k + 1);
            setLoading(false);
        }
    };

    return (
        <div className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden px-4 py-10">
            <AuroraBackground intense />

            <AnimatePresence>
                {!success && (
                    <motion.div
                        key="card"
                        initial={{ opacity: 0, y: 24, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, scale: 1.06, filter: "blur(8px)" }}
                        transition={{ duration: 0.6, ease: EASE_OUT }}
                        className="w-full max-w-sm"
                    >
                        <div key={shakeKey} className={cn(shakeKey > 0 && "animate-shake")}>
                            <div className="glass-strong border-gradient relative overflow-hidden rounded-[28px] px-7 pb-7 pt-9">
                                {/* Halo interne */}
                                <div aria-hidden className="pointer-events-none absolute -top-24 left-1/2 h-48 w-72 -translate-x-1/2 rounded-full bg-primary/25 blur-3xl" />

                                {/* Emblème en orbite */}
                                <div className="relative mx-auto mb-6 h-28 w-28">
                                    <svg className="absolute inset-0 h-full w-full animate-spin-slow" viewBox="0 0 100 100" aria-hidden>
                                        <circle cx="50" cy="50" r="48" fill="none" stroke="hsl(var(--brand) / 0.45)" strokeWidth="0.8" strokeDasharray="2 5" />
                                    </svg>
                                    <svg className="absolute inset-0 h-full w-full animate-spin-slow [animation-direction:reverse] [animation-duration:18s]" viewBox="0 0 100 100" aria-hidden>
                                        <circle cx="50" cy="50" r="42" fill="none" stroke="hsl(var(--primary) / 0.5)" strokeWidth="0.8" strokeDasharray="20 12" />
                                    </svg>
                                    <motion.div
                                        initial={{ scale: 0.5, rotate: -20, opacity: 0 }}
                                        animate={{ scale: 1, rotate: 0, opacity: 1 }}
                                        transition={{ type: "spring", stiffness: 180, damping: 14, delay: 0.15 }}
                                        className="absolute inset-[14%]"
                                    >
                                        <div className="absolute -inset-3 rounded-full bg-brand/30 blur-xl animate-pulse-glow" aria-hidden />
                                        <div className="relative h-full w-full overflow-hidden rounded-[26%] ring-1 ring-brand/40 shadow-[0_0_36px_-6px_hsl(var(--brand)/0.9)]">
                                            <BrandIcon title="ArrMada" animated delay={0.35} />
                                        </div>
                                    </motion.div>
                                </div>

                                <div className="relative text-center">
                                    <h1 className="text-gradient-animated text-3xl font-bold tracking-tight">ArrMada</h1>
                                    <p className="mt-1.5 text-sm text-muted-foreground">Le poste de commandement de ta flotte *arr</p>
                                </div>

                                <form onSubmit={handleSubmit} className="relative mt-7 space-y-4">
                                    <div className="relative">
                                        <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            id="password"
                                            type={show ? "text" : "password"}
                                            placeholder="Mot de passe"
                                            value={password}
                                            onChange={(e) => {
                                                setPassword(e.target.value);
                                                if (error) setError("");
                                            }}
                                            className={cn("h-12 pl-10 pr-11 text-base", error && "border-red-500/50 focus-visible:border-red-500/60 focus-visible:ring-red-500/20")}
                                            autoFocus
                                            autoComplete="current-password"
                                            required
                                            aria-invalid={!!error}
                                            aria-describedby={error ? "login-error" : undefined}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShow((s) => !s)}
                                            className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                                            aria-label={show ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                                        >
                                            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
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
                                                className="flex items-start gap-2 overflow-hidden text-sm text-red-400"
                                            >
                                                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                                                {error}
                                            </motion.p>
                                        )}
                                    </AnimatePresence>

                                    <Button type="submit" size="lg" className="shine group w-full" disabled={loading || !password}>
                                        {loading ? <Loader2 className="animate-spin" /> : null}
                                        {loading ? "Connexion…" : "Monter à bord"}
                                        {!loading && <ArrowRight className="transition-transform group-hover:translate-x-1" />}
                                    </Button>
                                </form>

                                <p className="relative mt-6 text-center text-[11px] leading-relaxed text-muted-foreground/70">
                                    Mot de passe = variable <span className="font-mono text-muted-foreground">ARRMADA_AUTH_SECRET</span> du fichier <span className="font-mono text-muted-foreground">.env</span>
                                </p>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Flash de succès */}
            <AnimatePresence>
                {success && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.6 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="absolute flex flex-col items-center gap-3"
                    >
                        <div className="h-16 w-16 rounded-full bg-primary/30 blur-xl animate-pulse-glow" />
                        <p className="text-gradient text-lg font-semibold">Bienvenue à bord, capitaine</p>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
