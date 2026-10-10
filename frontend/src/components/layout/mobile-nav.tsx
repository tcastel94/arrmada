"use client";

/**
 * Navigation mobile : barre flottante en verre (pouce-friendly) avec
 * indicateur animé + tiroir « Menu » qui reprend toute l'arborescence.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { LayoutDashboard, Film, Download, LayoutGrid, LogOut, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { TOP_ITEMS, NAV_GROUPS, BOTTOM_ITEMS, findActiveItem, type NavItem } from "@/lib/nav";
import { logout } from "@/lib/api-client";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { SPRING, stagger, scaleIn } from "@/lib/motion";

// Onglets accessibles au pouce ; tout le reste est dans le tiroir « Menu ».
const TABS = [
    { href: "/dashboard", label: "Accueil", icon: LayoutDashboard },
    { href: "/media", label: "Médias", icon: Film },
    { href: "/search", label: "Ajouter", icon: Search },
    { href: "/downloads", label: "Files", icon: Download, badge: "downloads" as const },
];

export function MobileNav() {
    const pathname = usePathname();
    const [menuOpen, setMenuOpen] = useState(false);
    const badges = useNavBadges();
    const active = findActiveItem(pathname);

    // Ferme le tiroir à chaque changement de page.
    useEffect(() => setMenuOpen(false), [pathname]);

    const tabActive = (href: string) =>
        active?.href === href || (href === "/media" && active?.href === "/media/missing");
    const menuActive = !TABS.some((t) => tabActive(t.href));

    return (
        <>
            <nav
                className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 lg:hidden"
                aria-label="Navigation mobile"
            >
                <div className="glass-strong flex h-16 items-stretch justify-around rounded-[22px] px-1.5">
                    {TABS.map((tab) => {
                        const Icon = tab.icon;
                        const on = tabActive(tab.href);
                        const count = tab.badge ? badges[tab.badge] : 0;
                        return (
                            <Link
                                key={tab.href}
                                href={tab.href}
                                className={cn(
                                    "relative flex flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
                                    on ? "text-primary" : "text-muted-foreground",
                                )}
                            >
                                {on && (
                                    <motion.span
                                        layoutId="mobile-tab-pill"
                                        transition={SPRING}
                                        className="absolute inset-x-1.5 inset-y-2 rounded-2xl bg-primary/[0.12] shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.25),0_0_24px_-6px_hsl(var(--primary)/0.7)]"
                                    />
                                )}
                                <span className="relative">
                                    <Icon className={cn("h-5 w-5 transition-transform duration-300 ease-spring", on && "scale-110")} strokeWidth={on ? 2.2 : 1.8} />
                                    {count > 0 && (
                                        <span className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground shadow-[0_0_8px_hsl(var(--primary))]">
                                            {count > 9 ? "9+" : count}
                                        </span>
                                    )}
                                </span>
                                <span className="relative">{tab.label}</span>
                            </Link>
                        );
                    })}
                    <button
                        onClick={() => setMenuOpen(true)}
                        className={cn(
                            "relative flex flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium",
                            menuActive ? "text-primary" : "text-muted-foreground",
                        )}
                        aria-label="Ouvrir le menu"
                    >
                        {menuActive && (
                            <motion.span
                                layoutId="mobile-tab-pill"
                                transition={SPRING}
                                className="absolute inset-x-1.5 inset-y-2 rounded-2xl bg-primary/[0.12] shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.25)]"
                            />
                        )}
                        <span className="relative">
                            <LayoutGrid className="h-5 w-5" />
                            {badges.notifications > 0 && (
                                <span className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white">
                                    {badges.notifications > 9 ? "9+" : badges.notifications}
                                </span>
                            )}
                        </span>
                        <span className="relative">Menu</span>
                    </button>
                </div>
            </nav>

            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
                <SheetContent
                    side="bottom"
                    className="max-h-[88dvh] overflow-y-auto rounded-t-[28px] px-4 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] pt-3"
                >
                    <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-white/20" />
                    <SheetHeader className="text-left">
                        <SheetTitle className="text-gradient text-xl">Navigation</SheetTitle>
                    </SheetHeader>

                    <motion.div className="mt-4 space-y-5" variants={stagger(0.05, 0.03)} initial="hidden" animate="show">
                        <div className="grid grid-cols-2 gap-2">
                            {TOP_ITEMS.map((item) => (
                                <MenuTile key={item.href} item={item} active={active?.href === item.href} wide />
                            ))}
                        </div>

                        {NAV_GROUPS.map((group) => (
                            <div key={group.title} className="space-y-2">
                                <p className="eyebrow">{group.title}</p>
                                <div className="grid grid-cols-3 gap-2">
                                    {group.items.map((item) => (
                                        <MenuTile
                                            key={item.href}
                                            item={item}
                                            active={active?.href === item.href}
                                            badge={item.badge ? badges[item.badge] : 0}
                                        />
                                    ))}
                                </div>
                            </div>
                        ))}

                        <div className="space-y-2">
                            <p className="eyebrow">Configuration</p>
                            <div className="grid grid-cols-3 gap-2">
                                {BOTTOM_ITEMS.map((item) => (
                                    <MenuTile key={item.href} item={item} active={active?.href === item.href} />
                                ))}
                                <motion.button
                                    variants={scaleIn}
                                    onClick={() => logout()}
                                    className="flex flex-col items-center justify-center gap-1.5 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3 text-muted-foreground transition-colors hover:text-red-400"
                                >
                                    <LogOut className="h-5 w-5" />
                                    <span className="text-[11px]">Déconnexion</span>
                                </motion.button>
                            </div>
                        </div>
                    </motion.div>
                </SheetContent>
            </Sheet>
        </>
    );
}

function MenuTile({ item, active, badge = 0, wide = false }: { item: NavItem; active: boolean; badge?: number; wide?: boolean }) {
    const Icon = item.icon;
    return (
        <motion.div variants={scaleIn}>
            <Link
                href={item.href}
                className={cn(
                    "relative flex h-full items-center gap-2 rounded-2xl border p-3 transition-all",
                    wide ? "justify-start" : "flex-col justify-center text-center",
                    active
                        ? "border-primary/40 bg-primary/[0.12] text-primary shadow-[0_0_24px_-8px_hsl(var(--primary)/0.7)]"
                        : "border-white/[0.06] bg-white/[0.02] text-foreground active:scale-95",
                )}
            >
                <Icon className="h-5 w-5 shrink-0" strokeWidth={1.8} />
                <span className={cn("leading-tight", wide ? "text-sm font-medium" : "text-[11px]")}>{item.label}</span>
                {badge > 0 && (
                    <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground">
                        {badge > 9 ? "9+" : badge}
                    </span>
                )}
            </Link>
        </motion.div>
    );
}
