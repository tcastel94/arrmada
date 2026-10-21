"use client";

/**
 * Sous-navigation du hub « Paramètres ».
 * ----------------------------------------------------------------
 * - Desktop (≥ lg) : colonne latérale en verre, collante au défilement.
 * - Mobile : rangée d'onglets défilante horizontalement (pouce-friendly).
 * La pilule de l'élément actif glisse d'un onglet à l'autre (`layoutId`
 * de framer-motion) — deux identifiants distincts car les deux variantes
 * sont montées en même temps (l'une masquée en CSS).
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
    ArrowUpRight,
    BookMarked,
    Cast,
    MonitorPlay,
    Server,
    SlidersHorizontal,
    Sofa,
    Speaker,
    Users,
    type LucideIcon,
} from "lucide-react";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface SettingsSection {
    href: string;
    label: string;
    /** Libellé court pour les onglets mobiles. */
    short: string;
    icon: LucideIcon;
    description: string;
}

/** Sections du hub, dans l'ordre d'affichage. Source unique (nav + en-tête). */
export const SETTINGS_SECTIONS: SettingsSection[] = [
    {
        href: "/settings",
        label: "Général",
        short: "Général",
        icon: SlidersHorizontal,
        description: "Vue d'ensemble, notifications Telegram et configuration de l'application.",
    },
    {
        href: "/settings/services",
        label: "Services *arr",
        short: "Services",
        icon: Server,
        description: "Connecte Sonarr, Radarr, Prowlarr… teste-les et active-les en un clic.",
    },
    {
        href: "/settings/kodi",
        label: "Kodi",
        short: "Kodi",
        icon: MonitorPlay,
        description: "Tes TV appairées et tes lecteurs Kodi : pièce et ampli, scans de bibliothèque, cohérence avec Radarr.",
    },
    {
        href: "/settings/cast",
        label: "Cast & Jellyfin",
        short: "Cast",
        icon: Cast,
        description: "Jellyfin transcode tes films pour les Chromecast et Google TV de la maison.",
    },
    {
        href: "/settings/yamaha",
        label: "Ampli Yamaha",
        short: "Yamaha",
        icon: Speaker,
        description: "Ton ampli home cinéma MusicCast et ses profils audio Salon / Cinéma, pilotés depuis le Salon.",
    },
    {
        href: "/settings/profils",
        label: "Profils famille",
        short: "Profils",
        icon: Users,
        description: "Qui regarde sur les TV : chacun sa rangée Reprendre, ses vus, son « Pour toi » et ses demandes.",
    },
];

/** Section active pour une URL (préfixe le plus long). */
export function findSection(pathname: string): SettingsSection {
    let best = SETTINGS_SECTIONS[0];
    for (const s of SETTINGS_SECTIONS) {
        if ((pathname === s.href || pathname.startsWith(s.href + "/")) && s.href.length > best.href.length) best = s;
    }
    return best;
}

/** Liens « voir aussi » affichés sous la navigation desktop. */
const RELATED = [
    { href: "/remote", label: "Salon (télécommandes)", icon: Sofa },
    { href: "/trash-guides", label: "TRaSH Guides", icon: BookMarked },
];

export function SettingsNav({ badges = {} }: { badges?: Record<string, React.ReactNode> }) {
    const pathname = usePathname();
    const active = findSection(pathname);

    return (
        <>
            {/* ── Mobile : onglets défilants ─────────────────────── */}
            <nav aria-label="Sections des paramètres" className="-mx-3 min-w-0 lg:hidden">
                <div className="scrollbar-none mask-fade-x flex gap-1.5 overflow-x-auto px-3 pb-1">
                    {SETTINGS_SECTIONS.map((s) => {
                        const isActive = s.href === active.href;
                        return (
                            <Link
                                key={s.href}
                                href={s.href}
                                aria-current={isActive ? "page" : undefined}
                                className={cn(
                                    "relative flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-medium transition-colors",
                                    isActive ? "text-primary" : "text-muted-foreground hover:text-foreground",
                                )}
                            >
                                {isActive && (
                                    <motion.span
                                        layoutId="settings-pill-mobile"
                                        transition={SPRING}
                                        className="absolute inset-0 rounded-full border border-primary/35 bg-primary/10 shadow-[0_0_20px_-6px_hsl(var(--primary)/0.6)]"
                                    />
                                )}
                                <s.icon className="relative h-3.5 w-3.5" />
                                <span className="relative">{s.short}</span>
                            </Link>
                        );
                    })}
                </div>
            </nav>

            {/* ── Desktop : colonne latérale ─────────────────────── */}
            <nav aria-label="Sections des paramètres" className="hidden lg:block">
                <div className="glass sticky top-24 space-y-1 rounded-2xl p-2">
                    <p className="eyebrow px-3 pb-1 pt-2">Configuration</p>
                    {SETTINGS_SECTIONS.map((s) => {
                        const isActive = s.href === active.href;
                        return (
                            <Link
                                key={s.href}
                                href={s.href}
                                aria-current={isActive ? "page" : undefined}
                                className={cn(
                                    "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                                    isActive ? "text-foreground" : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground",
                                )}
                            >
                                {isActive && (
                                    <motion.span
                                        layoutId="settings-pill-desktop"
                                        transition={SPRING}
                                        className="absolute inset-0 rounded-xl border border-primary/25 bg-gradient-to-r from-primary/15 to-primary/[0.03] shadow-[0_0_24px_-10px_hsl(var(--primary)/0.8)]"
                                    >
                                        {/* Liseré lumineux à gauche */}
                                        <span className="absolute inset-y-2 left-0 w-[3px] rounded-full bg-primary shadow-[0_0_10px_hsl(var(--primary))]" />
                                    </motion.span>
                                )}
                                <s.icon
                                    className={cn(
                                        "relative h-4 w-4 shrink-0 transition-transform group-hover:scale-110",
                                        isActive ? "text-primary" : "",
                                    )}
                                />
                                <span className="relative flex-1 truncate font-medium">{s.label}</span>
                                {badges[s.href] !== undefined && badges[s.href] !== null && (
                                    <span className="relative">{badges[s.href]}</span>
                                )}
                            </Link>
                        );
                    })}

                    <div className="mx-3 my-2 h-px bg-white/[0.06]" />
                    <p className="eyebrow px-3 pb-1">Voir aussi</p>
                    {RELATED.map((r) => (
                        <Link
                            key={r.href}
                            href={r.href}
                            className="group flex items-center gap-3 rounded-xl px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-white/[0.04] hover:text-foreground"
                        >
                            <r.icon className="h-3.5 w-3.5" />
                            <span className="flex-1">{r.label}</span>
                            <ArrowUpRight className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
                        </Link>
                    ))}
                </div>
            </nav>
        </>
    );
}

/** Petit compteur de la navigation (ex: « 5/6 »), coloré selon l'état. */
export function NavCount({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "success" | "warning" | "danger" }) {
    return (
        <span
            className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums",
                tone === "success" && "bg-emerald-500/10 text-emerald-300",
                tone === "warning" && "bg-amber-500/10 text-amber-300",
                tone === "danger" && "bg-red-500/10 text-red-300",
                tone === "default" && "bg-white/[0.06] text-muted-foreground",
            )}
        >
            {children}
        </span>
    );
}
