"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Film,
    Download,
    Search,
    Server,
    Settings,
} from "lucide-react";

const MOBILE_NAV = [
    { href: "/dashboard", label: "Home", icon: LayoutDashboard },
    { href: "/media", label: "Médias", icon: Film },
    { href: "/search", label: "Chercher", icon: Search },
    { href: "/downloads", label: "DL", icon: Download },
    { href: "/services", label: "Services", icon: Server },
];

export function MobileNav() {
    const pathname = usePathname();

    return (
        <nav className="fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t border-border bg-card lg:hidden">
            {MOBILE_NAV.map((item) => {
                const isActive =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                const Icon = item.icon;

                return (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                            "flex flex-col items-center gap-1 px-3 py-2 text-xs transition-colors",
                            isActive
                                ? "text-primary"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Icon className="h-5 w-5" />
                        <span>{item.label}</span>
                    </Link>
                );
            })}
        </nav>
    );
}
