import {
    LayoutDashboard,
    Film,
    Download,
    Search,
    BarChart3,
    Copy,
    Server,
    Settings,
    Container,
    FolderOpen,
    BookMarked,
    Bell,
    CalendarDays,
    HardDrive,
    Radar,
    Gauge,
    Trash2,
    PackageX,
    Speaker,
    type LucideIcon,
} from "lucide-react";

export interface NavItem {
    href: string;
    label: string;
    icon: LucideIcon;
}

// Dashboard stays standalone at the top; everything else is grouped.
export const TOP_ITEM: NavItem = { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard };

export const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
    {
        title: "Médias",
        items: [
            { href: "/media", label: "Médiathèque", icon: Film },
            { href: "/media/missing", label: "Manquants", icon: PackageX },
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
            { href: "/settings/yamaha", label: "Ampli Yamaha", icon: Speaker },
            { href: "/system", label: "Système", icon: HardDrive },
            { href: "/docker", label: "Docker", icon: Container },
            { href: "/notifications", label: "Notifications", icon: Bell },
        ],
    },
];

export const BOTTOM_ITEMS: NavItem[] = [
    { href: "/services", label: "Services", icon: Server },
    { href: "/settings", label: "Paramètres", icon: Settings },
];

/** Flat list of every destination (used by the mobile full-menu drawer). */
export const ALL_NAV_ITEMS: NavItem[] = [
    TOP_ITEM,
    ...NAV_GROUPS.flatMap((g) => g.items),
    ...BOTTOM_ITEMS,
];
