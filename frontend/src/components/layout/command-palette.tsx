"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    CommandDialog,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
    CommandSeparator,
} from "@/components/ui/command";
import {
    Film,
    Tv,
    LayoutDashboard,
    Server,
    Download,
    Search,
    Settings,
    BarChart3,
    Sparkles,
    MessageSquarePlus,
    Copy,
} from "lucide-react";
import { useMediaSearch, type MediaItem } from "@/hooks/use-media";
import { Badge } from "@/components/ui/badge";

const NAV_COMMANDS = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/media", label: "Médiathèque", icon: Film },
    { href: "/downloads", label: "Downloads", icon: Download },
    { href: "/services", label: "Services", icon: Server },
    { href: "/recommendations", label: "Recommandations", icon: Sparkles },
    { href: "/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/requests", label: "Requêtes", icon: MessageSquarePlus },
    { href: "/duplicates", label: "Doublons", icon: Copy },
    { href: "/settings", label: "Paramètres", icon: Settings },
];

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const router = useRouter();
    const { data: searchResults } = useMediaSearch(query);

    // ⌘K / Ctrl+K shortcut
    useEffect(() => {
        const down = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                setOpen((v) => !v);
            }
        };
        document.addEventListener("keydown", down);
        return () => document.removeEventListener("keydown", down);
    }, []);

    const navigate = useCallback(
        (href: string) => {
            setOpen(false);
            setQuery("");
            router.push(href);
        },
        [router]
    );

    return (
        <CommandDialog open={open} onOpenChange={setOpen}>
            <CommandInput
                placeholder="Rechercher un média ou une page…"
                value={query}
                onValueChange={setQuery}
            />
            <CommandList>
                <CommandEmpty>Aucun résultat pour « {query} »</CommandEmpty>

                {/* Media results */}
                {searchResults && searchResults.items.length > 0 && (
                    <CommandGroup heading="Médias">
                        {searchResults.items.slice(0, 8).map((item) => (
                            <CommandItem
                                key={`${item.type}-${item.external_id}`}
                                onSelect={() =>
                                    navigate(
                                        `/media?search=${encodeURIComponent(item.title)}`
                                    )
                                }
                                className="flex items-center gap-3"
                            >
                                {item.type === "movie" ? (
                                    <Film className="h-4 w-4 shrink-0 text-yellow-500" />
                                ) : (
                                    <Tv className="h-4 w-4 shrink-0 text-blue-400" />
                                )}
                                <div className="flex-1 min-w-0">
                                    <span className="truncate">{item.title}</span>
                                    {item.year && (
                                        <span className="text-xs text-muted-foreground ml-2">
                                            ({item.year})
                                        </span>
                                    )}
                                </div>
                                <Badge variant="outline" className="text-[10px] shrink-0">
                                    {item.source_service}
                                </Badge>
                            </CommandItem>
                        ))}
                    </CommandGroup>
                )}

                <CommandSeparator />

                {/* Navigation */}
                <CommandGroup heading="Navigation">
                    {NAV_COMMANDS.map((cmd) => (
                        <CommandItem
                            key={cmd.href}
                            onSelect={() => navigate(cmd.href)}
                        >
                            <cmd.icon className="mr-2 h-4 w-4" />
                            {cmd.label}
                        </CommandItem>
                    ))}
                </CommandGroup>
            </CommandList>
        </CommandDialog>
    );
}
