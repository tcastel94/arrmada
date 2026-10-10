"use client";

/**
 * « Passerelle de commandement » : bandeau d'accueil du Dashboard.
 * Salutation selon l'heure, résumé vivant de la flotte, actions rapides,
 * et l'emblème ArrMada au centre d'un radar animé.
 */
import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, Search, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { greeting } from "@/lib/format";
import { EASE_OUT, stagger, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface BridgeFact {
    label: string;
    tone?: "default" | "primary" | "success" | "warning" | "danger";
}

export function BridgeHero({ facts }: { facts: BridgeFact[] }) {
    // L'heure n'est calculée que côté navigateur (évite un décalage serveur/client).
    const [now, setNow] = useState<Date | null>(null);
    useEffect(() => {
        setNow(new Date());
        const t = setInterval(() => setNow(new Date()), 60_000);
        return () => clearInterval(t);
    }, []);

    const dateLabel = now?.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }) ?? "";
    const timeLabel = now?.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) ?? "";
    const openPalette = () => window.dispatchEvent(new Event("open-command-palette"));

    return (
        <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: EASE_OUT }}
            className="glass border-gradient relative overflow-hidden rounded-[28px]"
        >
            {/* Décor : halos + grille */}
            <div aria-hidden className="pointer-events-none absolute inset-0">
                <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full bg-primary/20 blur-3xl animate-aurora-1" />
                <div className="absolute -bottom-32 right-10 h-80 w-[28rem] rounded-full bg-brand/10 blur-3xl animate-aurora-2" />
                <div className="absolute inset-0 bg-grid opacity-50 [mask-image:radial-gradient(ellipse_at_80%_50%,#000_10%,transparent_70%)]" />
            </div>

            <div className="relative grid items-center gap-6 p-6 md:grid-cols-[1fr_auto] md:p-8">
                <motion.div variants={stagger(0.15, 0.08)} initial="hidden" animate="show" className="min-w-0">
                    <motion.p variants={fadeUp} className="eyebrow flex items-center gap-2">
                        <span className="capitalize">{dateLabel}</span>
                        {timeLabel && (
                            <>
                                <span className="h-1 w-1 rounded-full bg-muted-foreground/50" />
                                <span className="tabular-nums">{timeLabel}</span>
                            </>
                        )}
                    </motion.p>
                    <motion.h1 variants={fadeUp} className="mt-2 text-3xl font-bold tracking-tight md:text-5xl">
                        {now ? greeting(now) : "Bonjour"}, <span className="text-gradient-animated">capitaine</span>
                    </motion.h1>
                    <motion.p variants={fadeUp} className="mt-2 max-w-xl text-sm text-muted-foreground md:text-base">
                        Voici l&apos;état de ta flotte. Tout est sous contrôle — ou presque.
                    </motion.p>

                    {/* Faits marquants */}
                    {facts.length > 0 && (
                        <motion.div variants={fadeUp} className="mt-5 flex flex-wrap gap-2">
                            {facts.map((f) => (
                                <span
                                    key={f.label}
                                    className={cn(
                                        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium backdrop-blur",
                                        f.tone === "success" && "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
                                        f.tone === "warning" && "border-amber-500/25 bg-amber-500/10 text-amber-300",
                                        f.tone === "danger" && "border-red-500/25 bg-red-500/10 text-red-300",
                                        f.tone === "primary" && "border-primary/25 bg-primary/10 text-primary",
                                        (!f.tone || f.tone === "default") && "border-white/10 bg-white/[0.04] text-foreground/80",
                                    )}
                                >
                                    <span className="h-1.5 w-1.5 rounded-full bg-current shadow-[0_0_6px_currentColor]" />
                                    {f.label}
                                </span>
                            ))}
                        </motion.div>
                    )}

                    {/* Actions rapides */}
                    <motion.div variants={fadeUp} className="mt-6 flex flex-wrap gap-2">
                        <Button asChild>
                            <Link href="/search">
                                <Plus /> Ajouter un titre
                            </Link>
                        </Button>
                        <Button variant="outline" onClick={openPalette}>
                            <Search /> Rechercher
                            <span className="kbd ml-1">⌘K</span>
                        </Button>
                        <Button variant="ghost" asChild className="hidden sm:inline-flex">
                            <Link href="/search?tab=discover">
                                <Sparkles /> Suggestions
                            </Link>
                        </Button>
                    </motion.div>
                </motion.div>

                <RadarEmblem />
            </div>
        </motion.section>
    );
}

/** Emblème dans un radar : anneaux qui tournent + faisceau de balayage. */
function RadarEmblem() {
    return (
        <div className="relative mx-auto hidden h-56 w-56 shrink-0 md:block lg:h-64 lg:w-64" aria-hidden>
            {/* Anneaux concentriques */}
            {[0, 1, 2].map((i) => (
                <div
                    key={i}
                    className="absolute rounded-full border border-primary/15"
                    style={{ inset: `${i * 14}%` }}
                />
            ))}
            {/* Anneau pointillé qui tourne */}
            <svg className="absolute inset-0 h-full w-full animate-spin-slow" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="48" fill="none" stroke="hsl(var(--brand) / 0.35)" strokeWidth="0.4" strokeDasharray="1 3" />
            </svg>
            <svg className="absolute inset-[10%] h-[80%] w-[80%] animate-spin-slow [animation-direction:reverse] [animation-duration:20s]" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="48" fill="none" stroke="hsl(var(--primary) / 0.45)" strokeWidth="0.6" strokeDasharray="12 8" />
            </svg>
            {/* Faisceau radar */}
            <div
                className="absolute inset-0 animate-[spin_5s_linear_infinite] rounded-full"
                style={{
                    background: "conic-gradient(from 0deg, transparent 0deg, hsl(var(--primary) / 0.0) 270deg, hsl(var(--primary) / 0.35) 350deg, hsl(var(--brand) / 0.6) 360deg)",
                    WebkitMaskImage: "radial-gradient(circle, #000 0%, #000 69%, transparent 70%)",
                    maskImage: "radial-gradient(circle, #000 0%, #000 69%, transparent 70%)",
                }}
            />
            {/* Échos (points détectés) */}
            {[
                { top: "18%", left: "68%", d: 0 },
                { top: "70%", left: "22%", d: 1.2 },
                { top: "62%", left: "78%", d: 2.4 },
            ].map((p) => (
                <span
                    key={p.top}
                    className="absolute h-1.5 w-1.5 rounded-full bg-brand shadow-[0_0_10px_hsl(var(--brand))]"
                    style={{ top: p.top, left: p.left, animation: `pulse-glow 2.5s ease-in-out ${p.d}s infinite` }}
                />
            ))}
            {/* Emblème */}
            <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 160, damping: 16, delay: 0.3 }}
                className="absolute inset-[27%]"
            >
                <div className="absolute -inset-4 rounded-full bg-primary/30 blur-2xl animate-pulse-glow" />
                <div className="relative h-full w-full overflow-hidden rounded-[28%] ring-1 ring-brand/40 shadow-[0_0_40px_-6px_hsl(var(--brand)/0.8)] animate-float">
                    <Image src="/logo-mark.png" alt="" width={160} height={160} className="h-full w-full object-cover" priority />
                </div>
            </motion.div>
        </div>
    );
}
