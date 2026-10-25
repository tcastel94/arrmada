"use client";

/**
 * « Plus » : tout ce qui n'a pas d'onglet dans la barre du bas (mobile).
 * ----------------------------------------------------------------
 * Présenté comme l'app Réglages de l'iPhone : listes groupées, chaque
 * ligne avec sa vignette colorée (carré arrondi, icône blanche), un
 * compteur éventuel et un chevron. Les entrées viennent de lib/nav.ts
 * (source unique) : ajouter une page au menu l'ajoute ici aussi.
 */
import Link from "next/link";
import { ChevronRight, LogOut, Search } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { BOTTOM_ITEMS, MOBILE_TABS, NAV_GROUPS, TOP_ITEMS, type NavItem } from "@/lib/nav";
import { useNavBadges } from "@/hooks/use-nav-badges";
import { useModuleEnabled } from "@/hooks/use-modules";
import { logout } from "@/lib/api-client";
import { cn } from "@/lib/utils";

// Les destinations déjà présentes dans la barre d'onglets ne sont pas répétées.
const IN_TABS = new Set(MOBILE_TABS.map((t) => t.href));

export default function MorePage() {
    const badges = useNavBadges();
    // Équipement absent (pas de TV, pas d'ampli…) → entrées masquées
    const moduleOn = useModuleEnabled();
    const visible = (items: NavItem[]) => items.filter((i) => !IN_TABS.has(i.href) && moduleOn(i.module));
    const openPalette = () => window.dispatchEvent(new Event("open-command-palette"));

    const sections = [
        { title: "", items: visible(TOP_ITEMS) },
        ...NAV_GROUPS.map((g) => ({ title: g.title, items: visible(g.items) })),
        { title: "", items: visible(BOTTOM_ITEMS) },
    ].filter((s) => s.items.length > 0);

    return (
        <>
            <Header title="Plus" />
            <PageContainer size="narrow" className="space-y-6">
                <PageHeader title="Plus" />

                {/* Champ de recherche iOS : ouvre la recherche globale */}
                <button
                    onClick={openPalette}
                    className="flex h-10 w-full items-center gap-2 rounded-xl bg-white/[0.08] px-3 text-[17px] text-muted-foreground active:bg-white/[0.12]"
                >
                    <Search className="h-[18px] w-[18px]" />
                    Rechercher une page, un média…
                </button>

                {sections.map((section, i) => (
                    <section key={section.title || i}>
                        {section.title && <h2 className="mb-1.5 px-4 text-[13px] uppercase text-muted-foreground">{section.title}</h2>}
                        <div className="grouped">
                            {section.items.map((item) => (
                                <Row key={item.href} item={item} count={item.badge ? badges[item.badge] : 0} />
                            ))}
                        </div>
                    </section>
                ))}

                <div className="grouped">
                    <button
                        onClick={() => logout()}
                        className="flex h-12 w-full items-center justify-center text-[17px] text-destructive transition-colors active:bg-white/[0.06]"
                    >
                        <LogOut className="mr-2 h-[18px] w-[18px]" /> Déconnexion
                    </button>
                </div>
            </PageContainer>
        </>
    );
}

/** Ligne de liste iOS : vignette colorée, libellé, compteur, chevron. */
function Row({ item, count }: { item: NavItem; count: number }) {
    const Icon = item.icon;
    return (
        <Link href={item.href} className="flex min-h-[48px] items-center gap-3 pl-4 pr-3 transition-colors active:bg-white/[0.06]">
            <span className={cn("flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[8px] text-white", item.tint ?? "bg-[#8E8E93]")}>
                <Icon className="h-[18px] w-[18px]" strokeWidth={2.1} />
            </span>
            <span className="min-w-0 flex-1 py-3">
                <span className="block truncate text-[17px] leading-tight">{item.label}</span>
                {item.description && <span className="block truncate text-[13px] text-muted-foreground">{item.description}</span>}
            </span>
            {count > 0 && (
                <span
                    className={cn(
                        "text-[15px] tabular-nums",
                        item.badge === "notifications"
                            ? "min-w-[22px] rounded-full bg-destructive px-1.5 text-center text-[13px] font-semibold leading-[22px] text-white"
                            : "text-muted-foreground",
                    )}
                >
                    {count > 99 ? "99+" : count}
                </span>
            )}
            <ChevronRight className="h-[18px] w-[18px] shrink-0 text-white/25" strokeWidth={2.5} />
        </Link>
    );
}
