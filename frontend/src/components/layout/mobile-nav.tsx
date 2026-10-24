"use client";

/**
 * Barre d'onglets mobile (< 1024 px), copie fidèle de la « tab bar » iOS.
 * ----------------------------------------------------------------
 * - Collée en bas, pleine largeur, fond flouté (on devine le contenu qui
 *   défile dessous), filet fin en haut, marge pour la barre d'accueil de
 *   l'iPhone (safe area).
 * - 4 destinations + « Plus » (/more, la liste de tout le reste).
 * - Onglet actif : icône et libellé en bleu, icône pleine. Pas de pastille.
 * - Toucher l'onglet déjà actif remonte en haut de la page, comme sur iOS.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Ellipsis } from "lucide-react";
import { cn } from "@/lib/utils";
import { MOBILE_TABS, findMobileTab } from "@/lib/nav";
import { useNavBadges } from "@/hooks/use-nav-badges";

export function MobileNav() {
    const pathname = usePathname();
    const badges = useNavBadges();
    const current = findMobileTab(pathname);

    // Toucher l'onglet de la page déjà affichée : retour en haut, en douceur.
    const onTap = (active: boolean) => (event: React.MouseEvent) => {
        if (!active) return;
        if (window.scrollY > 0) {
            event.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    };

    return (
        <nav
            className="material hairline-t fixed inset-x-0 bottom-0 z-40 pb-[env(safe-area-inset-bottom)] lg:hidden"
            aria-label="Navigation principale"
        >
            <div className="mx-auto flex h-[var(--tabbar-h)] max-w-xl items-stretch">
                {MOBILE_TABS.map((tab) => {
                    const Icon = tab.icon;
                    const on = current?.href === tab.href;
                    const count = tab.badge ? badges[tab.badge] : 0;
                    return (
                        <TabLink key={tab.href} href={tab.href} label={tab.label} active={on} onClick={onTap(on && pathname === tab.href)} count={count}>
                            <Icon className="h-[22px] w-[22px]" strokeWidth={on ? 2.3 : 1.9} />
                        </TabLink>
                    );
                })}
                <TabLink href="/more" label="Plus" active={!current} onClick={onTap(pathname === "/more")} count={badges.notifications}>
                    <Ellipsis className="h-[22px] w-[22px]" strokeWidth={!current ? 2.3 : 1.9} />
                </TabLink>
            </div>
        </nav>
    );
}

function TabLink({
    href,
    label,
    active,
    count,
    onClick,
    children,
}: {
    href: string;
    label: string;
    active: boolean;
    /** Pastille rouge iOS (compteur). */
    count: number;
    onClick: (event: React.MouseEvent) => void;
    children: React.ReactNode;
}) {
    return (
        <Link
            href={href}
            onClick={onClick}
            aria-current={active ? "page" : undefined}
            className={cn(
                "relative flex flex-1 select-none flex-col items-center justify-center gap-[3px] pt-1 text-[10px] font-medium tracking-tight transition-colors duration-150 active:opacity-60",
                active ? "text-primary" : "text-[#98989F]",
            )}
        >
            <span className="relative">
                {children}
                {count > 0 && (
                    <span className="absolute -right-2.5 -top-1 flex h-[17px] min-w-[17px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-semibold leading-none text-white">
                        {count > 99 ? "99+" : count}
                    </span>
                )}
            </span>
            <span className="leading-none">{label}</span>
        </Link>
    );
}
