"use client";

/**
 * Sidebar flottante « verre » (desktop ≥ lg).
 * ----------------------------------------------------------------
 * - L'élément actif est surligné par une « pilule » qui GLISSE d'un item
 *   à l'autre (framer-motion `layoutId` : la même forme est animée entre
 *   deux positions au lieu d'apparaître/disparaître).
 * - Compteurs live : téléchargements, notifications non lues, manquants.
 * - Repliable (mémorisé), avec infobulles en mode replié.
 */
import Link from "next/link";
import { BrandIcon } from "@/components/brand/brand-mark";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronsLeft, ChevronsRight, LogOut, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { TOP_ITEMS, NAV_GROUPS, BOTTOM_ITEMS, findActiveItem, type NavItem } from "@/lib/nav";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { useSidebar, SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from "./sidebar-context";
import { useLiveState } from "@/lib/live-status";
import { StatusDot } from "@/components/fx/status-dot";
import { logout } from "@/lib/api-client";
import { SPRING, SPRING_SOFT } from "@/lib/motion";

export function Sidebar() {
    const pathname = usePathname();
    const { collapsed, toggle } = useSidebar();
    const badges = useNavBadges();
    const live = useLiveState();
    const active = findActiveItem(pathname);

    const openPalette = () => window.dispatchEvent(new Event("open-command-palette"));

    const renderItem = (item: NavItem) => {
        const isActive = active?.href === item.href;
        const Icon = item.icon;
        const count = item.badge ? badges[item.badge] : 0;

        const link = (
            <Link
                href={item.href}
                className={cn(
                    "group relative flex h-10 items-center gap-3 rounded-xl px-3 text-[13px] font-medium outline-none transition-colors duration-200",
                    "focus-visible:ring-2 focus-visible:ring-primary/50",
                    isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                    collapsed && "justify-center px-0",
                )}
            >
                {/* Pilule active animée entre les items */}
                {isActive && (
                    <motion.span
                        layoutId="sidebar-active-pill"
                        transition={SPRING}
                        className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary/[0.18] via-primary/[0.08] to-transparent shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.22),0_0_24px_-8px_hsl(var(--primary)/0.6)]"
                    >
                        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-primary to-brand shadow-[0_0_12px_hsl(var(--primary))]" />
                    </motion.span>
                )}
                {/* Survol */}
                {!isActive && (
                    <span className="absolute inset-0 rounded-xl bg-white/[0.04] opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
                )}

                <span className="relative">
                    <Icon
                        className={cn(
                            "h-[18px] w-[18px] shrink-0 transition-all duration-300 ease-spring",
                            isActive ? "text-primary drop-shadow-[0_0_8px_hsl(var(--primary)/0.8)]" : "group-hover:scale-110",
                        )}
                        strokeWidth={isActive ? 2.2 : 1.8}
                    />
                    {collapsed && count > 0 && (
                        <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-primary shadow-[0_0_8px_hsl(var(--primary))]" />
                    )}
                </span>

                {!collapsed && <span className="relative truncate">{item.label}</span>}

                {!collapsed && count > 0 && (
                    <motion.span
                        key={count}
                        initial={{ scale: 0.6, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={SPRING}
                        className={cn(
                            "relative ml-auto min-w-[20px] rounded-full px-1.5 py-px text-center text-[10px] font-bold tabular-nums",
                            item.badge === "notifications"
                                ? "bg-red-500/90 text-white shadow-[0_0_12px_rgb(239_68_68/0.6)]"
                                : item.badge === "missing"
                                  ? "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30"
                                  : "bg-primary/15 text-primary ring-1 ring-primary/30",
                        )}
                    >
                        {count > 99 ? "99+" : count}
                    </motion.span>
                )}
            </Link>
        );

        if (!collapsed) return <div key={item.href}>{link}</div>;
        return (
            <Tooltip key={item.href}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right" sideOffset={12}>
                    {item.label}
                    {count > 0 && <span className="ml-1.5 text-primary">({count})</span>}
                </TooltipContent>
            </Tooltip>
        );
    };

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH }}
            transition={SPRING_SOFT}
            className="glass fixed bottom-3 left-3 top-3 z-40 hidden flex-col overflow-hidden rounded-[26px] lg:flex"
        >
            {/* Halo décoratif en haut */}
            <div
                aria-hidden
                className="pointer-events-none absolute -left-20 -top-24 h-56 w-56 rounded-full opacity-50"
                style={{ background: "radial-gradient(closest-side, hsl(var(--primary) / 0.35), transparent)" }}
            />

            {/* ── Logo ─────────────────────────────────────────── */}
            <Link href="/dashboard" className={cn("relative flex h-[72px] items-center gap-3 px-4", collapsed && "justify-center px-0")}>
                <div className="border-beam relative h-10 w-10 shrink-0 rounded-xl p-[1.5px]">
                    <div className="h-full w-full overflow-hidden rounded-[10px]">
                        <BrandIcon title="ArrMada" />
                    </div>
                </div>
                <AnimatePresence initial={false}>
                    {!collapsed && (
                        <motion.div
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            transition={{ duration: 0.2 }}
                            className="min-w-0"
                        >
                            <p className="text-gradient-animated text-lg font-bold leading-none tracking-tight">ArrMada</p>
                            <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.22em] text-muted-foreground/70">Command Center</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </Link>

            {/* ── Recherche rapide ─────────────────────────────── */}
            <div className={cn("relative px-3 pb-2", collapsed && "px-2")}>
                <button
                    onClick={openPalette}
                    className={cn(
                        "group flex h-9 w-full items-center gap-2 rounded-xl border border-white/[0.07] bg-background/40 px-3 text-xs text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground hover:shadow-[0_0_20px_-8px_hsl(var(--primary)/0.7)]",
                        collapsed && "justify-center px-0",
                    )}
                    aria-label="Recherche rapide"
                >
                    <Search className="h-3.5 w-3.5 shrink-0 transition-transform group-hover:scale-110" />
                    {!collapsed && (
                        <>
                            <span className="truncate">Rechercher…</span>
                            <span className="kbd ml-auto">⌘K</span>
                        </>
                    )}
                </button>
            </div>

            {/* ── Navigation ───────────────────────────────────── */}
            <nav className="scrollbar-none relative flex-1 overflow-y-auto px-3 pb-3" aria-label="Navigation principale">
                <div className="flex flex-col gap-0.5">{TOP_ITEMS.map(renderItem)}</div>
                {NAV_GROUPS.map((group) => (
                    <div key={group.title} className="mt-4">
                        {collapsed ? (
                            <div className="mx-3 mb-2 border-t border-white/[0.06]" />
                        ) : (
                            <p className="eyebrow mb-1.5 px-3">{group.title}</p>
                        )}
                        <div className="flex flex-col gap-0.5">{group.items.map(renderItem)}</div>
                    </div>
                ))}
            </nav>

            {/* ── Bas : paramètres, état live, repli, déconnexion ── */}
            <div className="relative border-t border-white/[0.06] p-3">
                <div className="flex flex-col gap-0.5">{BOTTOM_ITEMS.map(renderItem)}</div>

                <div className={cn("mt-2 flex items-center gap-1", collapsed && "flex-col")}>
                    {!collapsed && (
                        <div className="flex min-w-0 flex-1 items-center gap-2 px-3 text-[11px] text-muted-foreground">
                            <StatusDot tone={live === "online" ? "online" : live === "offline" ? "offline" : "warning"} size="sm" />
                            <span className="truncate">
                                {live === "online" ? "Temps réel actif" : live === "offline" ? "Hors ligne" : "Connexion…"}
                            </span>
                        </div>
                    )}
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => logout()}
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-red-500/10 hover:text-red-400"
                                aria-label="Déconnexion"
                            >
                                <LogOut className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side={collapsed ? "right" : "top"}>Déconnexion</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={toggle}
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                                aria-label={collapsed ? "Déplier le menu" : "Replier le menu"}
                            >
                                {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side={collapsed ? "right" : "top"}>
                            {collapsed ? "Déplier" : "Replier"} <span className="kbd ml-1">[</span>
                        </TooltipContent>
                    </Tooltip>
                </div>
            </div>
        </motion.aside>
    );
}
