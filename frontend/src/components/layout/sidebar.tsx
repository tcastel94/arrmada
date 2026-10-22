"use client";

/**
 * Barre latérale (ordinateur, ≥ 1024 px), style macOS.
 * ----------------------------------------------------------------
 * Collée au bord gauche, fond gris très foncé séparé du contenu par un
 * filet. Sections à petits titres gris, lignes compactes ; la ligne
 * active est surlignée en gris clair (la surbrillance GLISSE d'une ligne
 * à l'autre grâce à framer-motion `layoutId` : la même forme est animée
 * entre deux positions au lieu d'apparaître / disparaître).
 * - Compteurs live : téléchargements, notifications non lues, manquants.
 * - Repliable (mémorisé), avec infobulles en mode replié.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { LogOut, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
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
                aria-current={isActive ? "page" : undefined}
                className={cn(
                    "group relative flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-[13px] outline-none transition-colors duration-150",
                    "focus-visible:ring-2 focus-visible:ring-primary/60",
                    isActive ? "font-medium text-foreground" : "text-foreground/75 hover:bg-white/[0.05] hover:text-foreground",
                    collapsed && "justify-center px-0",
                )}
            >
                {/* Surbrillance de la ligne active, animée d'une ligne à l'autre */}
                {isActive && (
                    <motion.span layoutId="sidebar-active" transition={SPRING} className="absolute inset-0 rounded-lg bg-white/[0.1]" />
                )}

                <span className="relative">
                    <Icon
                        className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground/80")}
                        strokeWidth={2}
                    />
                    {collapsed && count > 0 && (
                        <span
                            className={cn(
                                "absolute -right-1 -top-1 h-2 w-2 rounded-full",
                                item.badge === "notifications" ? "bg-destructive" : "bg-primary",
                            )}
                        />
                    )}
                </span>

                {!collapsed && <span className="relative truncate">{item.label}</span>}

                {/* Compteur : simple chiffre gris (rouge en pastille pour les notifications) */}
                {!collapsed && count > 0 && (
                    <span
                        className={cn(
                            "relative ml-auto text-[12px] tabular-nums",
                            item.badge === "notifications"
                                ? "min-w-[18px] rounded-full bg-destructive px-1.5 text-center font-semibold leading-[18px] text-white"
                                : "text-muted-foreground",
                        )}
                    >
                        {count > 99 ? "99+" : count}
                    </span>
                )}
            </Link>
        );

        if (!collapsed) return <div key={item.href}>{link}</div>;
        return (
            <Tooltip key={item.href}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right" sideOffset={10}>
                    {item.label}
                    {count > 0 && <span className="ml-1.5 text-muted-foreground">{count}</span>}
                </TooltipContent>
            </Tooltip>
        );
    };

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH }}
            transition={SPRING_SOFT}
            className="fixed inset-y-0 left-0 z-40 hidden flex-col overflow-hidden border-r border-white/[0.07] bg-[hsl(240_3%_6%)] lg:flex"
        >
            {/* ── Logo ─────────────────────────────────────────── */}
            <Link href="/dashboard" className={cn("flex h-14 shrink-0 items-center gap-2.5 px-4", collapsed && "justify-center px-0")}>
                <div className="h-7 w-7 shrink-0 overflow-hidden rounded-[8px]">
                    <BrandIcon title="ArrMada" />
                </div>
                {!collapsed && <span className="truncate text-[15px] font-semibold tracking-tight">ArrMada</span>}
            </Link>

            {/* ── Recherche rapide (⌘K) ────────────────────────── */}
            <div className={cn("px-3 pb-3", collapsed && "px-2.5")}>
                <button
                    onClick={openPalette}
                    className={cn(
                        "flex h-8 w-full items-center gap-2 rounded-lg bg-white/[0.07] px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-white/[0.1] hover:text-foreground",
                        collapsed && "justify-center px-0",
                    )}
                    aria-label="Recherche rapide"
                >
                    <Search className="h-3.5 w-3.5 shrink-0" />
                    {!collapsed && (
                        <>
                            <span className="truncate">Rechercher</span>
                            <span className="kbd ml-auto">⌘K</span>
                        </>
                    )}
                </button>
            </div>

            {/* ── Navigation ───────────────────────────────────── */}
            <nav className="scrollbar-none flex-1 overflow-y-auto px-2.5 pb-3" aria-label="Navigation principale">
                <div className="flex flex-col gap-px">{TOP_ITEMS.map(renderItem)}</div>
                {NAV_GROUPS.map((group) => (
                    <div key={group.title} className="mt-5">
                        {collapsed ? (
                            <div className="mx-2 mb-2 border-t border-white/[0.07]" />
                        ) : (
                            <p className="mb-1 px-2.5 text-[11px] font-semibold text-muted-foreground/80">{group.title}</p>
                        )}
                        <div className="flex flex-col gap-px">{group.items.map(renderItem)}</div>
                    </div>
                ))}
            </nav>

            {/* ── Bas : paramètres, état live, déconnexion, repli ── */}
            <div className="border-t border-white/[0.07] p-2.5">
                <div className="flex flex-col gap-px">{BOTTOM_ITEMS.map(renderItem)}</div>

                <div className={cn("mt-1.5 flex items-center gap-0.5", collapsed && "flex-col")}>
                    {!collapsed && (
                        <div className="flex min-w-0 flex-1 items-center gap-2 px-2.5 text-[12px] text-muted-foreground">
                            <StatusDot tone={live === "online" ? "online" : live === "offline" ? "offline" : "warning"} size="sm" />
                            <span className="truncate">
                                {live === "online" ? "Connecté" : live === "offline" ? "Hors ligne" : "Connexion…"}
                            </span>
                        </div>
                    )}
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => logout()}
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/[0.07] hover:text-foreground"
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
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/[0.07] hover:text-foreground"
                                aria-label={collapsed ? "Déplier le menu" : "Replier le menu"}
                            >
                                {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
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
