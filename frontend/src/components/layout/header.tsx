"use client";

/**
 * Barre du haut, copie de la « navigation bar » iOS.
 * ----------------------------------------------------------------
 * - En haut de page : transparente, sans titre (le grand titre de la page
 *   fait office d'en-tête, voir PageHeader).
 * - Dès qu'on défile : fond flouté + filet fin, et le petit titre de la
 *   page apparaît au centre (mobile) ou à gauche (ordinateur).
 * - Sous-page (fiche d'un film, réglage précis…) : bouton « ‹ Parent »
 *   à gauche. Sur mobile, une page rangée dans l'onglet « Plus »
 *   (Calendrier, Santé…) affiche « ‹ Plus ».
 * - À droite : recherche (⌘K), notifications ; menu (raccourcis,
 *   déconnexion) sur ordinateur seulement — sur mobile tout est dans « Plus ».
 * La prop `title` sert de titre quand l'URL ne correspond à aucun menu
 * (ex : titre d'une fiche média).
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
    AlertCircle,
    AlertTriangle,
    Bell,
    CheckCheck,
    CheckCircle2,
    ChevronLeft,
    ChevronRight,
    Ellipsis,
    Info,
    Keyboard,
    LogOut,
    Search,
    Settings,
    WifiOff,
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
import { useMarkAllRead, useMarkRead, useNotifications } from "@/hooks/use-notifications";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { useScrolled } from "@/hooks/use-scrolled";
import { useLiveState } from "@/lib/live-status";
import { findActiveItem, findMobileTab } from "@/lib/nav";
import { canGoBack } from "@/lib/nav-history";
import { logout } from "@/lib/api-client";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

interface HeaderProps {
    /** Titre de repli quand l'URL ne correspond à aucun menu (ex : fiche média). */
    title?: string;
}

const SEVERITY = {
    error: { icon: AlertCircle, cls: "text-destructive" },
    warning: { icon: AlertTriangle, cls: "text-warning" },
    success: { icon: CheckCircle2, cls: "text-success" },
    info: { icon: Info, cls: "text-primary" },
} as const;

export function Header({ title }: HeaderProps) {
    const pathname = usePathname();
    const router = useRouter();
    const item = findActiveItem(pathname);
    const live = useLiveState();
    const { notifications: unread } = useNavBadges();
    // Le grand titre de page mesure ~52 px : le petit titre apparaît quand il est sorti.
    const scrolled = useScrolled(44);

    // Sous-page (ex : /media/movie/12 sous « Médiathèque ») : retour vers le parent.
    const isSubPage = !!item && pathname !== item.href;
    const pageLabel = isSubPage && title ? title : item?.label ?? title ?? "";
    const back = isSubPage
        ? { href: item!.href, label: item!.label }
        : // Mobile : les pages de l'onglet « Plus » remontent vers « Plus »
          !findMobileTab(pathname) && pathname !== "/more"
          ? { href: "/more", label: "Plus", mobileOnly: true }
          : null;

    const goBack = (event: React.MouseEvent) => {
        // Comme le bouton retour d'iOS : on revient là d'où l'on vient
        // (filtres et défilement conservés) si on arrive de l'app.
        if (canGoBack()) {
            event.preventDefault();
            router.back();
        }
    };

    const openPalette = () => window.dispatchEvent(new Event("open-command-palette"));
    const openShortcuts = () => window.dispatchEvent(new Event("open-shortcuts"));

    return (
        <header
            className={cn(
                "sticky top-0 z-30 pt-[env(safe-area-inset-top)] transition-[background-color,box-shadow,backdrop-filter] duration-200",
                scrolled ? "material hairline-b" : "bg-transparent",
            )}
        >
            <div className="relative mx-auto flex h-[var(--navbar-h)] max-w-[1680px] items-center gap-1 px-2 md:px-4 lg:px-6">
                {/* Gauche : retour */}
                <div className="flex min-w-0 flex-1 basis-0 items-center">
                    {back && (
                        <Link
                            href={back.href}
                            onClick={goBack}
                            className={cn(
                                "-ml-1 flex min-w-0 items-center rounded-lg py-1 pr-2 text-[17px] text-primary transition-opacity active:opacity-50",
                                "mobileOnly" in back && "lg:hidden",
                            )}
                        >
                            <ChevronLeft className="h-[26px] w-[26px] shrink-0" strokeWidth={2.4} />
                            <span className="-ml-0.5 truncate">{back.label}</span>
                        </Link>
                    )}
                </div>

                {/* Centre : petit titre, visible une fois le grand titre défilé */}
                <AnimatePresence initial={false}>
                    {scrolled && pageLabel && (
                        <motion.p
                            key={pageLabel}
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.18 }}
                            aria-hidden
                            className="pointer-events-none absolute left-1/2 max-w-[52%] -translate-x-1/2 truncate text-[17px] font-semibold tracking-tight"
                        >
                            {pageLabel}
                        </motion.p>
                    )}
                </AnimatePresence>

                {/* Droite : actions */}
                <div className="flex flex-1 basis-0 items-center justify-end gap-0.5">
                    {live === "offline" && (
                        <span className="mr-1 flex items-center gap-1 rounded-full bg-destructive/15 px-2 py-1 text-[11px] font-semibold text-destructive">
                            <WifiOff className="h-3 w-3" />
                            <span className="hidden sm:inline">Hors ligne</span>
                        </span>
                    )}

                    {/* Recherche : champ sur ordinateur, loupe sur mobile */}
                    <button
                        onClick={openPalette}
                        className="hidden h-8 w-56 items-center gap-2 rounded-lg bg-white/[0.07] px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-white/[0.1] hover:text-foreground md:flex xl:w-72"
                        id="global-search-btn"
                    >
                        <Search className="h-3.5 w-3.5" />
                        <span>Rechercher</span>
                        <span className="kbd ml-auto">⌘K</span>
                    </button>
                    <Button variant="ghost" size="icon" className="text-primary md:hidden" onClick={openPalette} aria-label="Recherche rapide">
                        <Search className="!size-[21px]" strokeWidth={2.2} />
                    </Button>

                    <NotificationsPopover unread={unread} />

                    {/* Menu (ordinateur) */}
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="hidden lg:inline-flex" aria-label="Menu" id="user-menu-btn">
                                <Ellipsis className="h-4 w-4" />
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
                            <DropdownMenuItem onSelect={() => logout()} className="gap-2 text-destructive focus:text-destructive">
                                <LogOut className="h-4 w-4" /> Déconnexion
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
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
                <Button variant="ghost" size="icon" className="relative text-primary lg:text-foreground/80" aria-label="Notifications" id="notifications-btn">
                    <Bell className="!size-[20px] lg:!size-4" strokeWidth={2.1} />
                    {unread > 0 && (
                        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-white">
                            {unread > 99 ? "99+" : unread}
                        </span>
                    )}
                </Button>
            </PopoverTrigger>
            <PopoverContent align="end" sideOffset={8} className="w-[min(92vw,380px)] p-0">
                <div className="flex items-center justify-between px-4 pb-2 pt-3.5">
                    <div>
                        <p className="text-[15px] font-semibold">Notifications</p>
                        <p className="text-[12px] text-muted-foreground">
                            {unread > 0 ? `${unread} non lue${unread > 1 ? "s" : ""}` : "Tout est à jour"}
                        </p>
                    </div>
                    {unread > 0 && (
                        <Button size="sm" variant="ghost" onClick={() => markAll.mutate()} disabled={markAll.isPending} className="text-primary">
                            <CheckCheck /> Tout lire
                        </Button>
                    )}
                </div>
                <div className="max-h-[360px] overflow-y-auto px-1.5 pb-1.5">
                    {isLoading ? (
                        <div className="space-y-1.5 p-1">
                            {[0, 1, 2].map((i) => (
                                <div key={i} className="shimmer h-14 rounded-xl" />
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
                            <Bell className="h-7 w-7 opacity-30" />
                            <p className="text-[13px]">Aucune notification pour l&apos;instant</p>
                        </div>
                    ) : (
                        items.map((n) => {
                            const sev = SEVERITY[n.severity as keyof typeof SEVERITY] ?? SEVERITY.info;
                            const Icon = sev.icon;
                            return (
                                <button
                                    key={n.id}
                                    onClick={() => !n.is_read && markOne.mutate(n.id)}
                                    className="flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition-colors hover:bg-white/[0.05]"
                                >
                                    <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", sev.cls)} />
                                    <span className="min-w-0 flex-1">
                                        <span className="flex items-center gap-2">
                                            <span className="truncate text-[13px] font-semibold">{n.title}</span>
                                            {!n.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />}
                                        </span>
                                        <span className="line-clamp-2 text-[12px] text-muted-foreground">{n.message}</span>
                                        <span className="mt-0.5 block text-[11px] text-muted-foreground/70">{timeAgo(n.created_at)}</span>
                                    </span>
                                </button>
                            );
                        })
                    )}
                </div>
                <Link
                    href="/notifications"
                    className="hairline-t flex items-center justify-center gap-1 py-3 text-[13px] font-medium text-primary transition-colors hover:bg-white/[0.04]"
                >
                    Tout voir <ChevronRight className="h-3.5 w-3.5" />
                </Link>
            </PopoverContent>
        </Popover>
    );
}
