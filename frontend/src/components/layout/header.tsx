"use client";

import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "@/components/ui/button";
import { Search, Bell, LogOut } from "lucide-react";
import { logout } from "@/lib/api-client";
import { useUnreadCount } from "@/hooks/use-notifications";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";

interface HeaderProps {
    title?: string;
}

export function Header({ title }: HeaderProps) {
    const { data: unreadData } = useUnreadCount();
    const unreadCount = unreadData?.unread_count ?? 0;

    const openSearch = () => window.dispatchEvent(new Event("open-command-palette"));

    return (
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/80 backdrop-blur-sm px-4 md:px-6">
            {/* Title */}
            <h1 className="text-base md:text-lg font-semibold tracking-tight truncate">{title}</h1>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Actions */}
            <div className="flex items-center gap-0.5">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-9 w-9" id="global-search-btn" onClick={openSearch}>
                            <Search className="h-4 w-4" />
                            <span className="sr-only">Recherche rapide (⌘K)</span>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Recherche rapide (⌘K)</TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-9 w-9 relative" id="notifications-btn" asChild>
                            <Link href="/notifications">
                                <Bell className="h-4 w-4" />
                                {unreadCount > 0 && (
                                    <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 flex items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white px-1">
                                        {unreadCount > 99 ? "99+" : unreadCount}
                                    </span>
                                )}
                                <span className="sr-only">Notifications</span>
                            </Link>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Notifications</TooltipContent>
                </Tooltip>

                <ThemeToggle />

                {/* Logout — hidden on mobile (available in the Plus menu) */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-muted-foreground hover:text-destructive hidden md:inline-flex"
                            onClick={() => logout()}
                            id="logout-btn"
                        >
                            <LogOut className="h-4 w-4" />
                            <span className="sr-only">Déconnexion</span>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Déconnexion</TooltipContent>
                </Tooltip>
            </div>
        </header>
    );
}
