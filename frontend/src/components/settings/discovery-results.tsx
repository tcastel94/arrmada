"use client";

/**
 * Résultats d'une détection réseau (Kodi via mDNS, amplis Yamaha via SSDP).
 * ----------------------------------------------------------------
 * Avant : seul le PREMIER appareil trouvé pré-remplissait le formulaire,
 * les autres étaient perdus. Ici chaque appareil est une tuile cliquable
 * (« Utiliser ») et ceux déjà configurés sont signalés.
 */
import { AnimatePresence, motion } from "framer-motion";
import { Check, CornerDownLeft, Radar, type LucideIcon } from "lucide-react";
import { stagger, scaleIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface DiscoveredDevice {
    /** Identifiant stable (URL en général). */
    key: string;
    name: string;
    url: string;
    /** Déjà présent dans la configuration ? */
    known?: boolean;
}

export function DiscoveryResults({
    devices,
    icon: Icon,
    selectedKey,
    onPick,
    scanning,
}: {
    devices: DiscoveredDevice[] | null;
    icon: LucideIcon;
    selectedKey?: string | null;
    onPick: (d: DiscoveredDevice) => void;
    scanning?: boolean;
}) {
    return (
        <AnimatePresence initial={false} mode="wait">
            {scanning ? (
                <motion.div
                    key="scanning"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/[0.06] px-4 py-3 text-sm text-primary"
                >
                    <ScanPulse />
                    Recherche sur ton réseau local…
                </motion.div>
            ) : devices && devices.length > 0 ? (
                <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-2">
                    <p className="eyebrow">
                        {devices.length > 1 ? `${devices.length} appareils trouvés — choisis-en un` : "1 appareil trouvé"}
                    </p>
                    <motion.ul variants={stagger(0, 0.05)} initial="hidden" animate="show" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {devices.map((d) => {
                            const selected = selectedKey === d.key;
                            return (
                                <motion.li key={d.key} variants={scaleIn}>
                                    <button
                                        type="button"
                                        onClick={() => onPick(d)}
                                        className={cn(
                                            "glass-hover flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-colors",
                                            selected
                                                ? "border-primary/40 bg-primary/10"
                                                : "border-white/[0.06] bg-background/40 hover:border-white/[0.14]",
                                        )}
                                    >
                                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] ring-1 ring-white/[0.08]">
                                            <Icon className="h-4 w-4 text-foreground/80" />
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <span className="block truncate text-sm font-medium">{d.name}</span>
                                            <span className="block truncate font-mono text-[11px] text-muted-foreground">{d.url}</span>
                                        </span>
                                        {d.known ? (
                                            <span className="flex shrink-0 items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold text-success">
                                                <Check className="h-3 w-3" /> Déjà ajouté
                                            </span>
                                        ) : (
                                            <span
                                                className={cn(
                                                    "flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                                    selected ? "bg-primary/20 text-primary" : "bg-white/[0.05] text-muted-foreground",
                                                )}
                                            >
                                                <CornerDownLeft className="h-3 w-3" /> {selected ? "Sélectionné" : "Utiliser"}
                                            </span>
                                        )}
                                    </button>
                                </motion.li>
                            );
                        })}
                    </motion.ul>
                </motion.div>
            ) : devices && devices.length === 0 ? (
                <motion.p
                    key="none"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-background/30 px-4 py-3 text-sm text-muted-foreground"
                >
                    <Radar className="h-4 w-4 shrink-0" />
                    Rien trouvé automatiquement : saisis l&apos;adresse à la main ci-dessous.
                </motion.p>
            ) : null}
        </AnimatePresence>
    );
}

/** Petit radar animé (ondes concentriques) pendant un scan. */
export function ScanPulse({ className }: { className?: string }) {
    return (
        <span className={cn("relative flex h-5 w-5 shrink-0 items-center justify-center", className)}>
            {[0, 1].map((i) => (
                <motion.span
                    key={i}
                    className="absolute inset-0 rounded-full border border-current"
                    initial={{ scale: 0.4, opacity: 0.8 }}
                    animate={{ scale: 1.6, opacity: 0 }}
                    transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.8, ease: "easeOut" }}
                />
            ))}
            <Radar className="relative h-3.5 w-3.5" />
        </span>
    );
}
