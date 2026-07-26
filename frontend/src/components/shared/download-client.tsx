"use client";

import { Magnet, Newspaper, Server, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ClientMeta {
    label: string;
    icon: LucideIcon;
    color: string;
    bg: string;
    ring: string;
}

/** Map a download-client name / protocol to a display style (SABnzbd = usenet, Deluge = torrent…). */
export function getClientMeta(client?: string | null, protocol?: string | null): ClientMeta {
    const c = (client || "").toLowerCase();
    const p = (protocol || "").toLowerCase();
    const isUsenet = p === "usenet" || c.includes("sab") || c.includes("nzb");
    const isTorrent =
        p === "torrent" ||
        c.includes("deluge") ||
        c.includes("qbit") ||
        c.includes("transmission") ||
        c.includes("rtorrent") ||
        c.includes("torrent");

    if (isUsenet) {
        return { label: client || "Usenet", icon: Newspaper, color: "text-amber-400", bg: "bg-amber-500/15", ring: "ring-amber-500/30" };
    }
    if (isTorrent) {
        return { label: client || "Torrent", icon: Magnet, color: "text-sky-400", bg: "bg-sky-500/15", ring: "ring-sky-500/30" };
    }
    return { label: client || "Client ?", icon: Server, color: "text-slate-400", bg: "bg-slate-500/15", ring: "ring-slate-500/30" };
}

/** Small badge identifying which download app (SABnzbd / Deluge…) is handling an item. */
export function ClientBadge({
    client,
    protocol,
    className,
}: {
    client?: string | null;
    protocol?: string | null;
    className?: string;
}) {
    if (!client && !protocol) return null;
    const m = getClientMeta(client, protocol);
    const Icon = m.icon;
    return (
        <Badge
            variant="outline"
            className={cn("gap-1 border-0 px-1.5 py-0 h-4 text-[10px] font-medium", m.color, m.bg, className)}
        >
            <Icon className="h-2.5 w-2.5" />
            {m.label}
        </Badge>
    );
}
