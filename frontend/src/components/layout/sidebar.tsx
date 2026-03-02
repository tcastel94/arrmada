"use client";

import Link from "next/link";
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
    Skull,
    Container,
    FolderOpen,
    BookMarked,
    Bell,
} from "lucide-react";
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

const NAV_ITEMS = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/media", label: "Médiathèque", icon: Film },
    { href: "/downloads", label: "Downloads", icon: Download },
    { href: "/search", label: "Recherche", icon: Search },
    { href: "/requests", label: "Requêtes", icon: MessageSquarePlus },
    { href: "/recommendations", label: "Recommandations", icon: Sparkles },
    { href: "/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/duplicates", label: "Doublons", icon: Copy },
    { href: "/docker", label: "Docker", icon: Container },
    { href: "/fichiers", label: "Fichiers", icon: FolderOpen },
    { href: "/trash-guides", label: "TRaSH Guides", icon: BookMarked },
    { href: "/notifications", label: "Notifications", icon: Bell },
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
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                    <Skull className="h-5 w-5" />
                </div>
                <AnimatePresence>
                    {!collapsed && (
                        <motion.span
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: "auto" }}
                            exit={{ opacity: 0, width: 0 }}
                            className="text-lg font-bold tracking-tight overflow-hidden whitespace-nowrap"
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
                    {NAV_ITEMS.map((item) => {
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
