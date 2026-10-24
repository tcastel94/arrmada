"use client";

/**
 * Hub « Paramètres » : en-tête commun + sous-navigation + contenu.
 * ----------------------------------------------------------------
 * Toutes les pages /settings/* partagent ce cadre : elles n'affichent plus
 * leur propre bandeau, seulement leur contenu.
 *
 * Fil d'Ariane : le <Header> (barre collante du haut) est rendu ICI et non
 * dans les pages enfants — sinon il apparaîtrait sous le bandeau, au milieu
 * de la mise en page. Son titre (« Paramètres › Kodi ») est déduit de l'URL
 * via SETTINGS_SECTIONS, source unique partagée avec la navigation.
 *
 * Analogie infra : un layout Next.js est comme un reverse-proxy qui garde
 * la même « coquille » et ne remplace que le contenu ; la navigation entre
 * sous-pages ne recharge donc ni l'en-tête ni le menu (d'où l'animation
 * fluide de la pilule active).
 */
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Cog, MonitorSmartphone, Server, Tag } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { AnimatedNumber } from "@/components/fx/animated-number";
import { SettingsNav, NavCount, findSection } from "@/components/settings/settings-nav";
import { useServices } from "@/hooks/use-services";
import { useKodiSettings } from "@/hooks/use-kodi";
import { useYamahaSettings } from "@/hooks/use-yamaha";
import { useCastDevices, useJellyfinConfig } from "@/hooks/use-cast";
import { useVideoRoots } from "@/hooks/use-video-roots";
import { EASE_OUT } from "@/lib/motion";
import { APP_VERSION } from "@/components/settings/app-version";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const section = findSection(pathname);

    // Compteurs de la navigation et du bandeau (requêtes légères, en cache).
    const { data: services } = useServices();
    const { data: kodis } = useKodiSettings();
    const { data: amps } = useYamahaSettings();
    const { data: castDevices } = useCastDevices();
    const { data: jellyfin } = useJellyfinConfig();
    const { data: videoRoots } = useVideoRoots();

    const enabled = services?.filter((s) => s.is_enabled) ?? [];
    const online = enabled.filter((s) => s.last_status === "online").length;
    const devicesCount = (kodis?.length ?? 0) + (amps?.length ?? 0) + (castDevices?.length ?? 0);

    const badges: Record<string, React.ReactNode> = {
        "/settings/services": services ? (
            <NavCount tone={enabled.length === 0 ? "default" : online === enabled.length ? "success" : "warning"}>
                {online}/{enabled.length}
            </NavCount>
        ) : undefined,
        "/settings/kodi": kodis ? <NavCount>{kodis.length}</NavCount> : undefined,
        "/settings/cast": castDevices ? (
            <NavCount tone={jellyfin && !jellyfin.configured ? "warning" : "default"}>{castDevices.length}</NavCount>
        ) : undefined,
        "/settings/yamaha": amps ? <NavCount>{amps.length}</NavCount> : undefined,
        "/settings/dossiers": videoRoots ? (
            <NavCount tone={videoRoots.some((r) => !r.available) ? "warning" : "default"}>{videoRoots.length}</NavCount>
        ) : undefined,
    };

    return (
        <>
            <Header title={section.href === "/settings" ? "Paramètres" : section.label} />
            <PageContainer size="narrow" className="max-w-6xl">
                <PageHeader
                    icon={Cog}
                    accent="slate"
                    title={section.href === "/settings" ? "Paramètres" : section.label}
                    description={
                        <AnimatePresence mode="wait" initial={false}>
                            <motion.span
                                key={section.href}
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                transition={{ duration: 0.2 }}
                                className="block"
                            >
                                {section.description}
                            </motion.span>
                        </AnimatePresence>
                    }
                >
                    <StatPill
                        icon={Server}
                        label="services en ligne"
                        tone={enabled.length > 0 && online === enabled.length ? "success" : enabled.length > 0 ? "warning" : "default"}
                        value={
                            services ? (
                                <>
                                    <AnimatedNumber value={online} />/{enabled.length}
                                </>
                            ) : (
                                "—"
                            )
                        }
                    />
                    <StatPill icon={MonitorSmartphone} label="appareils du salon" value={<AnimatedNumber value={devicesCount} />} />
                    <StatPill icon={Tag} label="version" value={`v${APP_VERSION}`} />
                </PageHeader>

                {/* minmax(0,1fr) : sans lui, la rangée d'onglets mobile (plus large que
                    l'écran) élargirait la colonne → défilement horizontal de la page. */}
                <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[232px_minmax(0,1fr)] lg:items-start">
                    <SettingsNav badges={badges} />
                    {/* Le contenu change avec un léger fondu à chaque sous-page. */}
                    <motion.div
                        key={pathname}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0, transitionEnd: { transform: "none" } }}
                        transition={{ duration: 0.4, ease: EASE_OUT }}
                        className="min-w-0 space-y-6"
                    >
                        {children}
                    </motion.div>
                </div>
            </PageContainer>
        </>
    );
}
