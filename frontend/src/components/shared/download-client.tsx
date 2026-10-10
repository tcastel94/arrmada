"use client";

/**
 * Identité visuelle des clients de téléchargement.
 * ----------------------------------------------------------------
 * SABnzbd / NZBGet = Usenet (ambre, icône journal), Deluge / qBittorrent /
 * Transmission = Torrent (bleu ciel, icône aimant). Utilisé par la file de
 * téléchargement et le dashboard : `getClientMeta()` et `<ClientBadge>`
 * gardent leur signature ; les champs `kind`, `solid` et `glow` sont
 * nouveaux (barres de répartition, halos).
 */
import { Magnet, Newspaper, Server, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ClientMeta {
    label: string;
    icon: LucideIcon;
    /** Couleur du texte / de l'icône. */
    color: string;
    /** Fond translucide (badges, chips). */
    bg: string;
    /** Liseré (ring) assorti. */
    ring: string;
    /** Famille du client. */
    kind: "usenet" | "torrent" | "other";
    /** Fond plein (segments de barre de répartition). */
    solid: string;
    /** Couleur CSS du halo (box-shadow). */
    glow: string;
}

/** Associe un nom de client / protocole à son style (SABnzbd = usenet, Deluge = torrent…). */
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
        return {
            label: client || "Usenet",
            icon: Newspaper,
            color: "text-amber-300",
            bg: "bg-amber-500/15",
            ring: "ring-amber-400/25",
            kind: "usenet",
            solid: "bg-amber-400",
            glow: "hsl(38 95% 58% / 0.55)",
        };
    }
    if (isTorrent) {
        return {
            label: client || "Torrent",
            icon: Magnet,
            color: "text-sky-300",
            bg: "bg-sky-500/15",
            ring: "ring-sky-400/25",
            kind: "torrent",
            solid: "bg-sky-400",
            glow: "hsl(199 89% 60% / 0.55)",
        };
    }
    return {
        label: client || "Client inconnu",
        icon: Server,
        color: "text-slate-300",
        bg: "bg-slate-500/15",
        ring: "ring-slate-400/25",
        kind: "other",
        solid: "bg-slate-400",
        glow: "hsl(215 20% 60% / 0.5)",
    };
}

/** Petite pastille indiquant quel client (SABnzbd / Deluge…) traite l'élément. */
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
        <span
            title={protocol ? `${m.label} · ${protocol === "usenet" ? "Usenet" : protocol === "torrent" ? "Torrent" : protocol}` : m.label}
            className={cn(
                "inline-flex h-[18px] items-center gap-1 rounded-md px-1.5 text-[10px] font-semibold leading-none ring-1 ring-inset",
                m.color,
                m.bg,
                m.ring,
                className,
            )}
        >
            <Icon className="h-2.5 w-2.5" strokeWidth={2.25} />
            {m.label}
        </span>
    );
}
