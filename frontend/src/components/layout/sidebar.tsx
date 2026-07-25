"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Film,
    Download,
    Search,
    MessageSquarePlus,
    Sparkles,
    BarChart3,
    Copy,
    Server,
    Settings,
    ChevronLeft,
    ChevronRight,
    Container,
    FolderOpen,
    BookMarked,
    Bell,
    CalendarDays,
    HardDrive,
    Radar,
    Gauge,
    Trash2,
} from "lucide-react";
// (icône Skull remplacée par l'emblème ArrMada dans l'en-tête)
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useUnreadCount } from "@/hooks/use-notifications";

// Dashboard stays standalone at the top; everything else is grouped.
const TOP_ITEM = { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard };

const NAV_GROUPS: { title: string; items: { href: string; label: string; icon: typeof Film }[] }[] = [
    {
        title: "Médias",
        items: [
            { href: "/media", label: "Médiathèque", icon: Film },
            { href: "/search", label: "Rechercher & Ajouter", icon: Search },
            { href: "/calendar", label: "Calendrier", icon: CalendarDays },
            { href: "/downloads", label: "Downloads", icon: Download },
        ],
    },
    {
        title: "Bibliothèque",
        items: [
            { href: "/duplicates", label: "Doublons", icon: Copy },
            { href: "/quality", label: "Qualité", icon: Gauge },
            { href: "/cleanup", label: "Nettoyage", icon: Trash2 },
            { href: "/fichiers", label: "Fichiers", icon: FolderOpen },
            { href: "/trash-guides", label: "TRaSH Guides", icon: BookMarked },
        ],
    },
    {
        title: "Système & Infra",
        items: [
            { href: "/analytics", label: "Analytics", icon: BarChart3 },
            { href: "/prowlarr", label: "Indexers", icon: Radar },
            { href: "/system", label: "Système", icon: HardDrive },
            { href: "/docker", label: "Docker", icon: Container },
            { href: "/notifications", label: "Notifications", icon: Bell },
        ],
    },
];

const BOTTOM_ITEMS = [
    { href: "/services", label: "Services", icon: Server },
    { href: "/settings", label: "Paramètres", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);
    const { data: unreadData } = useUnreadCount();
    const unreadCount = unreadData?.unread_count ?? 0;

    const renderNavItem = (item: { href: string; label: string; icon: typeof Film }) => {
        const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
        const Icon = item.icon;

        const button = (
            <Link href={item.href} key={item.href}>
                <Button
                    variant={isActive ? "secondary" : "ghost"}
                    className={cn(
                        "w-full justify-start gap-3 h-10 relative",
                        isActive &&
                        "bg-primary/10 text-primary hover:bg-primary/15 font-medium",
                        collapsed && "justify-center px-0"
                    )}
                    id={`nav-${item.href.slice(1)}`}
                >
                    <div className="relative">
                        <Icon className="h-4 w-4 shrink-0" />
                        {item.href === "/notifications" && unreadCount > 0 && (
                            <span className="absolute -top-1.5 -right-1.5 h-4 min-w-4 flex items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white px-1">
                                {unreadCount > 99 ? "99+" : unreadCount}
                            </span>
                        )}
                    </div>
                    {!collapsed && <span className="truncate">{item.label}</span>}
                </Button>
            </Link>
        );

        if (collapsed) {
            return (
                <Tooltip key={item.href}>
                    <TooltipTrigger asChild>{button}</TooltipTrigger>
                    <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
            );
        }
        return button;
    };

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? 68 : 260 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className={cn(
                "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border bg-card",
                "hidden lg:flex"
            )}
        >
            {/* Logo */}
            <div className="flex h-14 items-center gap-2 px-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1 ring-primary/25 shadow-[0_0_12px_-2px] shadow-primary/30">
                    <Image
                        src="/logo-mark.png"
                        alt="ArrMada"
                        width={36}
                        height={36}
                        priority
                        className="h-full w-full object-cover"
                    />
                </div>
                <AnimatePresence>
                    {!collapsed && (
                        <motion.span
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: "auto" }}
                            exit={{ opacity: 0, width: 0 }}
                            className="text-lg font-bold tracking-tight overflow-hidden whitespace-nowrap bg-gradient-to-r from-primary to-cyan-300 bg-clip-text text-transparent"
                        >
                            ArrMada
                        </motion.span>
                    )}
                </AnimatePresence>
            </div>

            <Separator />

            {/* Navigation */}
            <ScrollArea className="flex-1 py-2">
                <nav className="flex flex-col gap-1 px-2">
                    {renderNavItem(TOP_ITEM)}
                    {NAV_GROUPS.map((group) => (
                        <div key={group.title} className="mt-1.5">
                            {collapsed ? (
                                <div className="my-2 mx-1 border-t border-border/50" />
                            ) : (
                                <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/55">
                                    {group.title}
                                </p>
                            )}
                            <div className="flex flex-col gap-1">
                                {group.items.map((item) => renderNavItem(item))}
                            </div>
                        </div>
                    ))}
                </nav>
            </ScrollArea>

            {/* Bottom items */}
            <div className="mt-auto border-t border-border py-2 px-2">
                <nav className="flex flex-col gap-1">
                    {BOTTOM_ITEMS.map((item) => {
                        const isActive = pathname === item.href;
                        const Icon = item.icon;

                        const button = (
                            <Link href={item.href} key={item.href}>
                                <Button
                                    variant={isActive ? "secondary" : "ghost"}
                                    className={cn(
                                        "w-full justify-start gap-3 h-10",
                                        isActive && "bg-primary/10 text-primary hover:bg-primary/15 font-medium",
                                        collapsed && "justify-center px-0"
                                    )}
                                    id={`nav-${item.href.slice(1)}`}
                                >
                                    <Icon className="h-4 w-4 shrink-0" />
                                    {!collapsed && (
                                        <span className="truncate">{item.label}</span>
                                    )}
                                </Button>
                            </Link>
                        );

                        if (collapsed) {
                            return (
                                <Tooltip key={item.href}>
                                    <TooltipTrigger asChild>{button}</TooltipTrigger>
                                    <TooltipContent side="right">{item.label}</TooltipContent>
                                </Tooltip>
                            );
                        }

                        return button;
                    })}
                </nav>

                {/* Collapse button */}
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setCollapsed(!collapsed)}
                    className="w-full mt-1 h-9"
                    id="sidebar-collapse"
                >
                    {collapsed ? (
                        <ChevronRight className="h-4 w-4" />
                    ) : (
                        <ChevronLeft className="h-4 w-4" />
                    )}
                </Button>
            </div>
        </motion.aside>
    );
}
