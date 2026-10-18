"use client";

/**
 * Barre supérieure (collante, en verre).
 * ----------------------------------------------------------------
 * - Fil d'Ariane « Groupe › Page » calculé depuis lib/nav.ts
 *   (la prop `title` sert de repli, ex: titre d'une fiche média).
 * - Bouton de recherche ⌘K, voyant « Live » (connexion temps réel),
 *   cloche avec aperçu des notifications dans un popover.
 */
import Link from "next/link";
import { BrandIcon } from "@/components/brand/brand-mark";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
    Bell,
    CheckCheck,
    ChevronRight,
    Search,
    AlertTriangle,
    AlertCircle,
    CheckCircle2,
    Info,
    Keyboard,
    LogOut,
    Settings,
    MoreVertical,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMarkAllRead, useMarkRead, useNotifications } from "@/hooks/use-notifications";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { useLiveState } from "@/lib/live-status";
import { findActiveItem, findGroupTitle } from "@/lib/nav";
import { logout } from "@/lib/api-client";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

interface HeaderProps {
    /** Titre de repli quand l'URL ne correspond à aucun menu. */
    title?: string;
}

const SEVERITY = {
    error: { icon: AlertCircle, cls: "text-red-400 bg-red-500/10 ring-red-500/25" },
    warning: { icon: AlertTriangle, cls: "text-amber-400 bg-amber-500/10 ring-amber-500/25" },
    success: { icon: CheckCircle2, cls: "text-emerald-400 bg-emerald-500/10 ring-emerald-500/25" },
    info: { icon: Info, cls: "text-primary bg-primary/10 ring-primary/25" },
} as const;

export function Header({ title }: HeaderProps) {
    const pathname = usePathname();
    const item = findActiveItem(pathname);
    const group = findGroupTitle(item);
    const live = useLiveState();
    const { notifications: unread } = useNavBadges();

    // Sur une sous-page (ex: fiche média), on affiche « Médiathèque › Titre ».
    const isSubPage = item && pathname !== item.href;
    const pageLabel = isSubPage && title ? title : item?.label ?? title ?? "";
    const parent = isSubPage && title ? item : undefined;

    const openPalette = () => window.dispatchEvent(new Event("open-command-palette"));
    const openShortcuts = () => window.dispatchEvent(new Event("open-shortcuts"));

    return (
        <header className="sticky top-0 z-30 px-3 pt-3 md:px-5 lg:pl-0 lg:pr-5">
            <div className="glass mx-auto flex h-14 max-w-[1680px] items-center gap-2 rounded-2xl px-3 md:px-4">
                {/* Logo (mobile uniquement — la sidebar l'affiche sur desktop) */}
                <Link href="/dashboard" className="mr-1 shrink-0 lg:hidden" aria-label="Accueil">
                    <div className="h-8 w-8 overflow-hidden rounded-lg ring-1 ring-primary/30 shadow-[0_0_16px_-4px_hsl(var(--primary)/0.7)]">
                        <BrandIcon />
                    </div>
                </Link>

                {/* Fil d'Ariane */}
                <nav aria-label="Fil d'Ariane" className="flex min-w-0 items-center gap-1.5 text-sm">
                    {(parent || group) && (
                        <>
                            {parent ? (
                                <Link href={parent.href} className="hidden shrink-0 text-muted-foreground transition-colors hover:text-foreground sm:inline">
                                    {parent.label}
                                </Link>
                            ) : (
                                <span className="hidden shrink-0 text-muted-foreground/70 sm:inline">{group}</span>
                            )}
                            <ChevronRight className="hidden h-3.5 w-3.5 shrink-0 text-muted-foreground/40 sm:block" />
                        </>
                    )}
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.p
                            key={pageLabel}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            transition={{ duration: 0.2 }}
                            aria-current="page"
                            className="truncate font-semibold tracking-tight"
                        >
                            {pageLabel}
                        </motion.p>
                    </AnimatePresence>
                </nav>

                <div className="flex-1" />

                {/* Recherche (pilule desktop, icône mobile) */}
                <button
                    onClick={openPalette}
                    className="group hidden h-9 w-64 items-center gap-2 rounded-xl border border-white/[0.07] bg-background/40 px-3 text-xs text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground hover:shadow-[0_0_24px_-8px_hsl(var(--primary)/0.7)] md:flex xl:w-80"
                    id="global-search-btn"
                >
                    <Search className="h-3.5 w-3.5 transition-transform group-hover:scale-110" />
                    <span>Média, page, action…</span>
                    <span className="kbd ml-auto">⌘K</span>
                </button>
                <Button variant="ghost" size="icon" className="md:hidden" onClick={openPalette} aria-label="Recherche rapide">
                    <Search className="h-4 w-4" />
                </Button>

                {/* Voyant temps réel */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div
                            className={cn(
                                "hidden h-7 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-semibold uppercase tracking-wider sm:flex",
                                live === "online"
                                    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                                    : live === "offline"
                                      ? "border-red-500/25 bg-red-500/10 text-red-300"
                                      : "border-amber-500/25 bg-amber-500/10 text-amber-300",
                            )}
                        >
                            <span className="relative flex h-1.5 w-1.5">
                                {live === "online" && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-emerald-400" />}
                                <span
                                    className={cn(
                                        "relative h-1.5 w-1.5 rounded-full",
                                        live === "online" ? "bg-emerald-400" : live === "offline" ? "bg-red-400" : "bg-amber-400",
                                    )}
                                />
                            </span>
                            Live
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        {live === "online"
                            ? "Mises à jour en temps réel actives"
                            : live === "offline"
                              ? "Flux temps réel coupé — reconnexion automatique"
                              : "Connexion au flux temps réel…"}
                    </TooltipContent>
                </Tooltip>

                <NotificationsPopover unread={unread} />

                {/* Menu utilisateur */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="Menu" id="user-menu-btn">
                            <MoreVertical className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52">
                        <DropdownMenuItem asChild>
                            <Link href="/settings" className="gap-2">
                                <Settings className="h-4 w-4" /> Paramètres
                            </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={openShortcuts} className="gap-2">
                            <Keyboard className="h-4 w-4" /> Raccourcis clavier
                            <span className="kbd ml-auto">?</span>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => logout()} className="gap-2 text-red-400 focus:bg-red-500/10 focus:text-red-400">
                            <LogOut className="h-4 w-4" /> Déconnexion
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </header>
    );
}

/** Cloche + aperçu des 8 dernières notifications. */
function NotificationsPopover({ unread }: { unread: number }) {
    const { data, isLoading } = useNotifications(8);
    const markAll = useMarkAllRead();
    const markOne = useMarkRead();
    const items = data?.items ?? [];

    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="relative" aria-label="Notifications" id="notifications-btn">
                    <motion.span
                        key={unread}
                        animate={unread > 0 ? { rotate: [0, -14, 12, -8, 6, 0] } : {}}
                        transition={{ duration: 0.7 }}
                        className="inline-flex"
                    >
                        <Bell className="h-4 w-4" />
                    </motion.span>
                    <AnimatePresence>
                        {unread > 0 && (
                            <motion.span
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                exit={{ scale: 0 }}
                                transition={SPRING}
                                className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white shadow-[0_0_10px_rgb(239_68_68/0.7)]"
                            >
                                {unread > 99 ? "99+" : unread}
                            </motion.span>
                        )}
                    </AnimatePresence>
                </Button>
            </PopoverTrigger>
            <PopoverContent align="end" sideOffset={10} className="w-[min(92vw,380px)] p-0">
                <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                    <div>
                        <p className="text-sm font-semibold">Notifications</p>
                        <p className="text-[11px] text-muted-foreground">
                            {unread > 0 ? `${unread} non lue${unread > 1 ? "s" : ""}` : "Tout est à jour"}
                        </p>
                    </div>
                    {unread > 0 && (
                        <Button size="sm" variant="ghost" onClick={() => markAll.mutate()} disabled={markAll.isPending} className="h-7 text-xs">
                            <CheckCheck className="h-3.5 w-3.5" /> Tout lire
                        </Button>
                    )}
                </div>
                <div className="max-h-[360px] overflow-y-auto p-1.5">
                    {isLoading ? (
                        <div className="space-y-1.5 p-1">
                            {[0, 1, 2].map((i) => (
                                <div key={i} className="shimmer h-14 rounded-xl" />
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
                            <Bell className="h-7 w-7 opacity-30" />
                            <p className="text-xs">Aucune notification pour l&apos;instant</p>
                        </div>
                    ) : (
                        items.map((n) => {
                            const sev = SEVERITY[n.severity as keyof typeof SEVERITY] ?? SEVERITY.info;
                            const Icon = sev.icon;
                            return (
                                <button
                                    key={n.id}
                                    onClick={() => !n.is_read && markOne.mutate(n.id)}
                                    className={cn(
                                        "flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition-colors hover:bg-white/[0.04]",
                                        !n.is_read && "bg-primary/[0.04]",
                                    )}
                                >
                                    <span className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ring-1", sev.cls)}>
                                        <Icon className="h-3.5 w-3.5" />
                                    </span>
                                    <span className="min-w-0 flex-1">
                                        <span className="flex items-center gap-2">
                                            <span className="truncate text-xs font-semibold">{n.title}</span>
                                            {!n.is_read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary shadow-[0_0_6px_hsl(var(--primary))]" />}
                                        </span>
                                        <span className="line-clamp-2 text-[11px] text-muted-foreground">{n.message}</span>
                                        <span className="mt-0.5 block text-[10px] text-muted-foreground/60">{timeAgo(n.created_at)}</span>
                                    </span>
                                </button>
                            );
                        })
                    )}
                </div>
                <Link
                    href="/notifications"
                    className="flex items-center justify-center gap-1 border-t border-white/[0.06] py-2.5 text-xs font-medium text-primary transition-colors hover:bg-primary/5"
                >
                    Tout voir <ChevronRight className="h-3.5 w-3.5" />
                </Link>
            </PopoverContent>
        </Popover>
    );
}
