"use client";

/**
 * Salon : centre de contrôle du home cinéma.
 * ----------------------------------------------------------------
 * Regroupe ce qui était éparpillé (télécommande Yamaha dans les réglages,
 * télécommande Kodi seulement sur la fiche média) :
 *  - grand lecteur « En lecture » Kodi (progression déplaçable, volume…),
 *  - télécommande de l'ampli Yamaha,
 *  - appareils Cast.
 * Le mini-lecteur flottant est masqué sur cette page (doublon).
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Cast, MonitorPlay, Settings2, Sofa, Speaker } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { NowPlayingHero } from "@/components/remote/now-playing-hero";
import { AmpPanel } from "@/components/remote/amp-panel";
import { CastPanel } from "@/components/remote/cast-panel";
import { useKodiNowPlaying, useKodiSettings } from "@/hooks/use-kodi";
import { useYamahaSettings, useYamahaState } from "@/hooks/use-yamaha";
import { useCastDevices } from "@/hooks/use-cast";
import { fadeUp, stagger } from "@/lib/motion";

export default function RemotePage() {
    return (
        <>
            <Header title="Salon" />
            <PageContainer>
                <PageHeader
                    icon={Sofa}
                    accent="violet"
                    eyebrow="Home cinéma"
                    title="Salon"
                    description="Pilote la lecture Kodi, l'ampli et tes appareils Cast depuis un seul écran."
                    actions={
                        <Button asChild variant="outline" size="sm">
                            <Link href="/settings/kodi">
                                <Settings2 /> Réglages des appareils
                            </Link>
                        </Button>
                    }
                >
                    <HeaderStats />
                </PageHeader>

                <motion.div variants={stagger(0.05, 0.08)} initial="hidden" animate="show" className="space-y-6">
                    <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
                        <motion.div variants={fadeUp} className="min-w-0">
                            <NowPlayingHero />
                        </motion.div>
                        <motion.div variants={fadeUp} className="min-w-0">
                            <AmpPanel />
                        </motion.div>
                    </div>
                    <motion.div variants={fadeUp}>
                        <CastPanel />
                    </motion.div>
                </motion.div>
            </PageContainer>
        </>
    );
}

/** Pastilles d'état du bandeau : Kodi, ampli, Cast. */
function HeaderStats() {
    const kodis = useKodiSettings();
    const kodiConfigured = (kodis.data?.length ?? 0) > 0;
    const np = useKodiNowPlaying(kodiConfigured);
    const amps = useYamahaSettings();
    const ampConfigured = (amps.data?.length ?? 0) > 0;
    const amp = useYamahaState(ampConfigured);
    const cast = useCastDevices();

    const kodiStatus = !kodis.data
        ? "—"
        : !kodiConfigured
          ? "Non configuré"
          : np.data?.playing
            ? np.data.paused
                ? "En pause"
                : "En lecture"
            : (np.data as { error?: string } | undefined)?.error || np.isError
              ? "Injoignable"
              : "Prêt";
    const kodiTone = kodiStatus === "En lecture" ? "primary" : kodiStatus === "Injoignable" ? "danger" : kodiStatus === "Non configuré" ? "warning" : "default";

    const firstAmp = amp.data?.devices[0];
    const ampStatus = !amps.data
        ? "—"
        : !ampConfigured
          ? "Non configuré"
          : !firstAmp
            ? "—"
            : !firstAmp.online
              ? "Hors ligne"
              : firstAmp.power === "on"
                ? firstAmp.mute
                    ? "Sourdine"
                    : `${firstAmp.volume_pct ?? 0} %`
                : "En veille";
    const ampTone = ampStatus === "Hors ligne" ? "danger" : ampStatus === "Non configuré" ? "warning" : firstAmp?.power === "on" ? "success" : "default";

    return (
        <>
            <StatPill icon={MonitorPlay} label="Kodi" value={kodiStatus} tone={kodiTone} />
            <StatPill icon={Speaker} label="ampli" value={ampStatus} tone={ampTone} />
            <StatPill icon={Cast} label={(cast.data?.length ?? 0) > 1 ? "appareils Cast" : "appareil Cast"} value={cast.data?.length ?? "—"} />
        </>
    );
}
