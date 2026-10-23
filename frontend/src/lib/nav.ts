/**
 * Arborescence de navigation — SOURCE UNIQUE pour la sidebar, la barre
 * mobile, la palette de commandes (⌘K), le fil d'Ariane du header et les
 * raccourcis clavier.
 * ----------------------------------------------------------------
 * Réorganisation (v2) :
 *  - Doublons / Qualité / Nettoyage   → un seul hub « Santé médiathèque » (/health)
 *  - Fichiers (imports bloqués)       → onglet « Imports » de /downloads
 *  - Docker                           → onglet de /system
 *  - Services + Kodi/Cast/Yamaha conf → hub /settings (sous-menu)
 *  - Profils par média + SABnzbd      → onglets de /trash-guides
 *  - Télécommandes Kodi + Yamaha      → nouvelle page « Salon » (/remote)
 * Les anciennes URLs redirigent (voir next.config.mjs).
 *
 * Refonte « Épuré » (2026) :
 *  - Mobile : barre d'onglets iOS à 4 destinations (MOBILE_TABS) + « Plus »
 *    (/more), qui liste tout le reste en listes groupées façon Réglages.
 *  - Chaque entrée a une teinte (`tint`) : couleur de sa vignette d'icône
 *    dans « Plus » (carré arrondi coloré, icône blanche, comme les Réglages
 *    de l'iPhone).
 */
import {
    House,
    Clapperboard,
    ArrowDownToLine,
    LayoutDashboard,
    Film,
    History,
    Download,
    Search,
    BarChart3,
    Settings,
    BookMarked,
    Bell,
    CalendarDays,
    HardDrive,
    Radar,
    PackageX,
    Activity,
    HeartPulse,
    Sofa,
    type LucideIcon,
} from "lucide-react";

export interface NavItem {
    href: string;
    label: string;
    icon: LucideIcon;
    /** Description courte (palette ⌘K). */
    description?: string;
    /** Touche du raccourci « g + touche ». */
    shortcut?: string;
    /** Mots-clés supplémentaires pour la recherche dans la palette. */
    keywords?: string[];
    /** Clé de badge dynamique (compteur affiché dans la sidebar). */
    badge?: "downloads" | "notifications" | "missing";
    /** Couleur de la vignette d'icône (écran « Plus »), classe Tailwind de fond. */
    tint?: string;
}

export interface NavGroup {
    title: string;
    items: NavItem[];
}

/** Entrées toujours visibles en haut de la sidebar. */
export const TOP_ITEMS: NavItem[] = [
    {
        href: "/dashboard",
        label: "Accueil",
        icon: LayoutDashboard,
        tint: "bg-[#0A84FF]",
        description: "Vue d'ensemble de la flotte",
        shortcut: "d",
        keywords: ["accueil", "home", "tableau de bord"],
    },
    {
        href: "/remote",
        label: "Salon",
        icon: Sofa,
        tint: "bg-[#FF9F0A]",
        description: "Télécommandes Kodi & ampli, lecture en cours",
        shortcut: "r",
        keywords: ["kodi", "yamaha", "ampli", "télécommande", "remote", "lecture", "cast"],
    },
];

export const NAV_GROUPS: NavGroup[] = [
    {
        title: "Bibliothèque",
        items: [
            {
                href: "/media",
                label: "Médiathèque",
                icon: Film,
        tint: "bg-[#0A84FF]",
                description: "Films et séries de ta collection",
                shortcut: "m",
                keywords: ["films", "séries", "library", "bibliothèque"],
            },
            {
                href: "/media/continue",
                label: "Reprendre",
                icon: History,
        tint: "bg-[#5E5CE6]",
                description: "Films et épisodes commencés sur tes TV",
                shortcut: "e",
                keywords: ["en cours", "reprise", "continuer", "vu", "kodi", "tv"],
            },
            {
                href: "/media/missing",
                label: "Manquants",
                icon: PackageX,
        tint: "bg-[#FF9F0A]",
                description: "Médias surveillés sans fichier",
                shortcut: "x",
                keywords: ["missing", "wanted", "absents"],
                badge: "missing",
            },
            {
                href: "/calendar",
                label: "Calendrier",
                icon: CalendarDays,
        tint: "bg-[#FF453A]",
                description: "Sorties à venir",
                shortcut: "c",
                keywords: ["agenda", "sorties", "épisodes"],
            },
            {
                href: "/search",
                label: "Rechercher",
                icon: Search,
        tint: "bg-[#8E8E93]",
                description: "Trouver un titre, l'ajouter, suivre les demandes",
                shortcut: "s",
                keywords: ["ajouter", "requests", "demandes", "suggestions", "tendances", "ia"],
            },
        ],
    },
    {
        title: "Activité",
        items: [
            {
                href: "/downloads",
                label: "Transferts",
                icon: Download,
        tint: "bg-[#30D158]",
                description: "Téléchargements en cours et imports",
                shortcut: "t",
                keywords: ["téléchargements", "downloads", "queue", "sabnzbd", "deluge", "imports", "fichiers"],
                badge: "downloads",
            },
            {
                href: "/activity",
                label: "Journal",
                icon: Activity,
        tint: "bg-[#8E8E93]",
                description: "Historique de toutes les actions",
                shortcut: "j",
                keywords: ["activité", "historique", "timeline", "log"],
            },
            {
                href: "/notifications",
                label: "Notifications",
                icon: Bell,
        tint: "bg-[#FF453A]",
                description: "Alertes et événements",
                shortcut: "n",
                keywords: ["alertes"],
                badge: "notifications",
            },
        ],
    },
    {
        title: "Maintenance",
        items: [
            {
                href: "/health",
                label: "Santé médiathèque",
                icon: HeartPulse,
        tint: "bg-[#FF375F]",
                description: "Qualité, doublons et nettoyage",
                shortcut: "h",
                keywords: ["qualité", "doublons", "nettoyage", "cleanup", "duplicates", "upgrade"],
            },
            {
                href: "/trash-guides",
                label: "TRaSH Guides",
                icon: BookMarked,
        tint: "bg-[#BF5AF2]",
                description: "Profils qualité, overrides par média, config SABnzbd",
                keywords: ["profils", "custom formats", "sabnzbd", "overrides"],
            },
            {
                href: "/prowlarr",
                label: "Indexers",
                icon: Radar,
        tint: "bg-[#64D2FF]",
                description: "Indexers Prowlarr et statistiques",
                shortcut: "i",
                keywords: ["prowlarr", "trackers"],
            },
        ],
    },
    {
        title: "Système",
        items: [
            {
                href: "/system",
                label: "Serveur & Docker",
                icon: HardDrive,
        tint: "bg-[#8E8E93]",
                description: "Ressources, disques et conteneurs",
                shortcut: "y",
                keywords: ["docker", "disques", "ram", "cpu", "conteneurs", "unraid"],
            },
            {
                href: "/analytics",
                label: "Statistiques",
                icon: BarChart3,
        tint: "bg-[#5E5CE6]",
                description: "Analyse de la médiathèque",
                keywords: ["analytics", "graphes", "stats"],
            },
        ],
    },
];

export const BOTTOM_ITEMS: NavItem[] = [
    {
        href: "/settings",
        label: "Paramètres",
        icon: Settings,
        tint: "bg-[#8E8E93]",
        description: "Services, appareils et configuration",
        shortcut: "p",
        keywords: ["services", "config", "kodi", "cast", "jellyfin", "yamaha", "telegram"],
    },
];

/** Liste à plat de toutes les destinations. */
export const ALL_NAV_ITEMS: NavItem[] = [
    ...TOP_ITEMS,
    ...NAV_GROUPS.flatMap((g) => g.items),
    ...BOTTOM_ITEMS,
];

/**
 * Élément de menu actif pour une URL : on retient le préfixe le plus long
 * (corrige l'ancien bug où « Médiathèque » ET « Manquants » s'allumaient
 * ensemble sur /media/missing).
 */
export function findActiveItem(pathname: string): NavItem | undefined {
    let best: NavItem | undefined;
    for (const item of ALL_NAV_ITEMS) {
        if (pathname === item.href || pathname.startsWith(item.href + "/")) {
            if (!best || item.href.length > best.href.length) best = item;
        }
    }
    return best;
}

/** Groupe parent d'un élément (pour le fil d'Ariane). */
export function findGroupTitle(item: NavItem | undefined): string | undefined {
    if (!item) return undefined;
    return NAV_GROUPS.find((g) => g.items.includes(item))?.title;
}

/**
 * Onglets de la barre du bas (mobile). Le 5e onglet, « Plus », mène à
 * /more et s'allume pour toute page qui n'est pas l'un de ces quatre.
 * `match` : préfixes d'URL qui allument l'onglet (ex : la fiche d'un film
 * reste sous l'onglet Médiathèque).
 */
export interface MobileTab {
    href: string;
    label: string;
    icon: LucideIcon;
    match: string[];
    badge?: NavItem["badge"];
}

export const MOBILE_TABS: MobileTab[] = [
    { href: "/dashboard", label: "Accueil", icon: House, match: ["/dashboard"] },
    { href: "/media", label: "Médiathèque", icon: Clapperboard, match: ["/media"] },
    { href: "/search", label: "Rechercher", icon: Search, match: ["/search"] },
    { href: "/downloads", label: "Transferts", icon: ArrowDownToLine, match: ["/downloads"], badge: "downloads" },
];

/** Onglet mobile allumé pour une URL (null : « Plus »). */
export function findMobileTab(pathname: string): MobileTab | null {
    return MOBILE_TABS.find((t) => t.match.some((m) => pathname === m || pathname.startsWith(m + "/"))) ?? null;
}
