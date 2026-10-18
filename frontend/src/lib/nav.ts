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
 */
import {
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
}

export interface NavGroup {
    title: string;
    items: NavItem[];
}

/** Entrées toujours visibles en haut de la sidebar. */
export const TOP_ITEMS: NavItem[] = [
    {
        href: "/dashboard",
        label: "Dashboard",
        icon: LayoutDashboard,
        description: "Vue d'ensemble de la flotte",
        shortcut: "d",
        keywords: ["accueil", "home", "tableau de bord"],
    },
    {
        href: "/remote",
        label: "Salon",
        icon: Sofa,
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
                description: "Films et séries de ta collection",
                shortcut: "m",
                keywords: ["films", "séries", "library", "bibliothèque"],
            },
            {
                href: "/media/continue",
                label: "Reprendre",
                icon: History,
                description: "Films et épisodes commencés sur tes TV",
                shortcut: "e",
                keywords: ["en cours", "reprise", "continuer", "vu", "kodi", "tv"],
            },
            {
                href: "/media/missing",
                label: "Manquants",
                icon: PackageX,
                description: "Médias surveillés sans fichier",
                shortcut: "x",
                keywords: ["missing", "wanted", "absents"],
                badge: "missing",
            },
            {
                href: "/calendar",
                label: "Calendrier",
                icon: CalendarDays,
                description: "Sorties à venir",
                shortcut: "c",
                keywords: ["agenda", "sorties", "épisodes"],
            },
            {
                href: "/search",
                label: "Rechercher & Ajouter",
                icon: Search,
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
                label: "Téléchargements",
                icon: Download,
                description: "File d'attente et imports",
                shortcut: "t",
                keywords: ["downloads", "queue", "sabnzbd", "deluge", "imports", "fichiers"],
                badge: "downloads",
            },
            {
                href: "/activity",
                label: "Journal",
                icon: Activity,
                description: "Historique de toutes les actions",
                shortcut: "j",
                keywords: ["activité", "historique", "timeline", "log"],
            },
            {
                href: "/notifications",
                label: "Notifications",
                icon: Bell,
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
                description: "Qualité, doublons et nettoyage",
                shortcut: "h",
                keywords: ["qualité", "doublons", "nettoyage", "cleanup", "duplicates", "upgrade"],
            },
            {
                href: "/trash-guides",
                label: "TRaSH Guides",
                icon: BookMarked,
                description: "Profils qualité, overrides par média, config SABnzbd",
                keywords: ["profils", "custom formats", "sabnzbd", "overrides"],
            },
            {
                href: "/prowlarr",
                label: "Indexers",
                icon: Radar,
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
                description: "Ressources, disques et conteneurs",
                shortcut: "y",
                keywords: ["docker", "disques", "ram", "cpu", "conteneurs", "unraid"],
            },
            {
                href: "/analytics",
                label: "Statistiques",
                icon: BarChart3,
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
