"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Film,
    Download,
    Search,
    Menu,
    LogOut,
} from "lucide-react";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { TOP_ITEM, NAV_GROUPS, BOTTOM_ITEMS } from "@/lib/nav";
import { logout } from "@/lib/api-client";
import { useUnreadCount } from "@/hooks/use-notifications";

// Thumb-reachable primary tabs; everything else lives in the "Plus" drawer.
const BOTTOM_TABS = [
    { href: "/dashboard", label: "Accueil", icon: LayoutDashboard },
    { href: "/media", label: "Médias", icon: Film },
    { href: "/search", label: "Chercher", icon: Search },
    { href: "/downloads", label: "DL", icon: Download },
];

export function MobileNav() {
    const pathname = usePathname();
    const [menuOpen, setMenuOpen] = useState(false);
    const { data: unreadData } = useUnreadCount();
    const unreadCount = unreadData?.unread_count ?? 0;

    const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

    return (
        <>
            <nav className="fixed bottom-0 left-0 right-0 z-40 flex h-16 items-stretch justify-around border-t border-border bg-card/95 backdrop-blur-sm lg:hidden pb-[env(safe-area-inset-bottom)]">
                {BOTTOM_TABS.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition-colors",
                                active ? "text-primary" : "text-muted-foreground",
                            )}
                        >
                            <Icon className={cn("h-5 w-5", active && "scale-110 transition-transform")} />
                            <span>{item.label}</span>
                        </Link>
                    );
                })}
                <button
                    onClick={() => setMenuOpen(true)}
                    className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] text-muted-foreground"
                >
                    <span className="relative">
                        <Menu className="h-5 w-5" />
                        {unreadCount > 0 && (
                            <span className="absolute -top-1.5 -right-2 h-3.5 min-w-3.5 flex items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white px-1">
                                {unreadCount > 9 ? "9+" : unreadCount}
                            </span>
                        )}
                    </span>
                    <span>Plus</span>
                </button>
            </nav>

            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
                <SheetContent
                    side="bottom"
                    className="max-h-[88vh] overflow-y-auto rounded-t-2xl px-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]"
                >
                    <SheetHeader className="text-left">
                        <SheetTitle>Menu</SheetTitle>
                    </SheetHeader>

                    <div className="mt-2 space-y-5">
                        {/* Dashboard standalone */}
                        <MenuTile item={TOP_ITEM} active={isActive(TOP_ITEM.href)} onNav={() => setMenuOpen(false)} full />

                        {NAV_GROUPS.map((group) => (
                            <div key={group.title} className="space-y-2">
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/55">
                                    {group.title}
                                </p>
                                <div className="grid grid-cols-3 gap-2">
                                    {group.items.map((item) => (
                                        <MenuTile
                                            key={item.href}
                                            item={item}
                                            active={isActive(item.href)}
                                            onNav={() => setMenuOpen(false)}
                                            badge={item.href === "/notifications" ? unreadCount : 0}
                                        />
                                    ))}
                                </div>
                            </div>
                        ))}

                        <div className="space-y-2">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/55">
                                Configuration
                            </p>
                            <div className="grid grid-cols-3 gap-2">
                                {BOTTOM_ITEMS.map((item) => (
                                    <MenuTile
                                        key={item.href}
                                        item={item}
                                        active={isActive(item.href)}
                                        onNav={() => setMenuOpen(false)}
                                    />
                                ))}
                                <button
                                    onClick={() => logout()}
                                    className="flex flex-col items-center justify-center gap-1.5 rounded-xl border border-border/50 bg-card/40 p-3 text-muted-foreground hover:text-red-400"
                                >
                                    <LogOut className="h-5 w-5" />
                                    <span className="text-[11px]">Déconnexion</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </SheetContent>
            </Sheet>
        </>
    );
}

function MenuTile({
    item,
    active,
    onNav,
    badge = 0,
    full = false,
}: {
    item: { href: string; label: string; icon: typeof Film };
    active: boolean;
    onNav: () => void;
    badge?: number;
    full?: boolean;
}) {
    const Icon = item.icon;
    return (
        <Link
            href={item.href}
            onClick={onNav}
            className={cn(
                "relative flex items-center gap-2 rounded-xl border p-3 transition-colors",
                full ? "justify-start" : "flex-col justify-center text-center",
                active
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border/50 bg-card/40 text-foreground hover:bg-card",
            )}
        >
            <Icon className="h-5 w-5 shrink-0" />
            <span className={cn("text-[11px] leading-tight", full && "text-sm font-medium")}>{item.label}</span>
            {badge > 0 && (
                <span className="absolute top-1.5 right-1.5 h-4 min-w-4 flex items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white px-1">
                    {badge > 9 ? "9+" : badge}
                </span>
            )}
        </Link>
    );
}
