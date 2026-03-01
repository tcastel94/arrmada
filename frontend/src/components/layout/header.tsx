"use client";

import { ThemeToggle } from "./theme-toggle";
import { Button } from "@/components/ui/button";
import { Search, Bell, LogOut } from "lucide-react";
import { logout } from "@/lib/api-client";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";

interface HeaderProps {
    title?: string;
}

export function Header({ title }: HeaderProps) {
    return (
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-background/80 backdrop-blur-sm px-6">
            {/* Title */}
            <h1 className="text-lg font-semibold tracking-tight">{title}</h1>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Actions */}
            <div className="flex items-center gap-1">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-9 w-9" id="global-search-btn">
                            <Search className="h-4 w-4" />
                            <span className="sr-only">Recherche (⌘K)</span>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Recherche (⌘K)</TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-9 w-9" id="notifications-btn">
                            <Bell className="h-4 w-4" />
                            <span className="sr-only">Notifications</span>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Notifications</TooltipContent>
                </Tooltip>

                <ThemeToggle />

                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-muted-foreground hover:text-destructive"
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
