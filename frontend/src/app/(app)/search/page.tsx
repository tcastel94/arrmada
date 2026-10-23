"use client";

/**
 * Rechercher & Ajouter (/search) — point d'entrée unique pour trouver un
 * titre, l'ajouter à Radarr/Sonarr et suivre son arrivée.
 * ----------------------------------------------------------------
 * Fusionne les anciennes pages /requests (→ onglet Suivi + ajout manuel)
 * et /recommendations (→ onglet Découvrir), qui redirigent ici.
 * Onglets dans l'URL : ?tab=search|tracking|discover (+ ?q= pour la
 * recherche, utilisé par la palette ⌘K).
 *
 * Le découpage en composants vit dans src/components/library/ :
 * SearchTab, TrackingTab, DiscoverTab, ManualAddDialog, AdderProvider
 * (logique d'ajout partagée par tous les onglets) et AddPreviewDialog, qui
 * ouvre la fiche TMDB détaillée (components/media/recommendation-detail-modal :
 * casting, bande-annonce, ajout) au clic sur n'importe quelle affiche
 * ajoutable — résultats de recherche comme suggestions.
 */
import { Suspense, useCallback, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Download, Flame, ListChecks, PenLine, Search, SearchCheck } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { PageHeader, StatPill } from "@/components/shared/page-header";
import { PosterGridSkeleton, Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { useRequests } from "@/hooks/use-requests";
import { EASE_OUT } from "@/lib/motion";
import { useParamState } from "@/components/library/use-param-state";
import { SegmentedControl } from "@/components/library/segmented-control";
import { LiveCount } from "@/components/library/live-count";
import { AdderProvider, type AddableItem } from "@/components/library/adder";
import { AddPreviewDialog } from "@/components/library/add-preview-dialog";
import { ManualAddDialog } from "@/components/library/manual-add-dialog";
import { SearchTab } from "@/components/library/search-tab";
import { TrackingTab } from "@/components/library/tracking-tab";
import { DiscoverTab } from "@/components/library/discover-tab";
import { isActiveRequest } from "@/components/library/request-status";

const TABS = ["search", "tracking", "discover"] as const;
type Tab = (typeof TABS)[number];

export default function SearchHubPage() {
    return (
        <>
            <Header title="Rechercher" />
            {/* useSearchParams (onglet + requête dans l'URL) exige un Suspense au build. */}
            <Suspense
                fallback={
                    <PageContainer>
                        <Shimmer className="h-40 w-full rounded-3xl" />
                        <Shimmer className="h-36 w-full rounded-3xl" />
                        <PosterGridSkeleton count={8} />
                    </PageContainer>
                }
            >
                <SearchHub />
            </Suspense>
        </>
    );
}

function SearchHub() {
    // Onglet lu dans l'URL dès le premier rendu : un lien /search?tab=tracking
    // (ancienne page /requests) s'ouvre directement sur le bon onglet, et la
    // palette ⌘K qui pousse /search?q=… ramène automatiquement sur « Rechercher ».
    const [tab, setTab] = useParamState<Tab>("tab", "search", TABS);

    const { data: requests } = useRequests();
    const stats = useMemo(() => {
        const items = requests?.items ?? [];
        return {
            total: items.length,
            active: items.filter((r) => isActiveRequest(r.status)).length,
            available: items.filter((r) => r.status === "available").length,
        };
    }, [requests]);

    const [preview, setPreview] = useState<AddableItem | null>(null);
    const [manual, setManual] = useState<{ open: boolean; title: string }>({ open: false, title: "" });

    const openManual = useCallback((title = "") => setManual({ open: true, title }), []);
    const goTo = useCallback(
        (next: Tab) => {
            setTab(next);
            window.scrollTo({ top: 0, behavior: "smooth" });
        },
        [setTab],
    );
    const showTracking = useCallback(() => {
        setPreview(null);
        goTo("tracking");
    }, [goTo]);

    return (
        <AdderProvider onShowTracking={showTracking}>
            <PageContainer>
                <PageHeader
                    icon={SearchCheck}
                    accent="brand"
                    title="Rechercher"
                    description="Trouve un film ou une série, ajoute-le en un clic à Radarr ou Sonarr, puis suis son arrivée jusqu'à ta médiathèque."
                    actions={
                        <Button size="sm" variant="tinted" onClick={() => openManual()}>
                            <PenLine /> Ajout manuel
                        </Button>
                    }
                >
                    <StatPill label="en cours" value={<LiveCount value={requests ? stats.active : undefined} />} icon={Download} tone="primary" />
                    <StatPill label="disponibles" value={<LiveCount value={requests ? stats.available : undefined} />} icon={CheckCircle2} tone="success" />
                    <StatPill label="demandes suivies" value={<LiveCount value={requests ? stats.total : undefined} />} icon={ListChecks} />
                </PageHeader>

                <div className="-mx-1 overflow-x-auto px-1 scrollbar-none">
                    <SegmentedControl
                        role="tablist"
                        layoutId="search-hub-tab-pill"
                        ariaLabel="Sections"
                        value={tab}
                        onChange={goTo}
                        options={[
                            { value: "search", label: "Rechercher", icon: Search },
                            { value: "tracking", label: "Suivi", icon: ListChecks, count: stats.active || null },
                            { value: "discover", label: "Découvrir", icon: Flame },
                        ]}
                    />
                </div>

                <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                        key={tab}
                        role="tabpanel"
                        initial={{ opacity: 0, y: 14 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.3, ease: EASE_OUT }}
                    >
                        {tab === "search" && (
                            <SearchTab onPreview={setPreview} onOpenManual={openManual} onGoDiscover={() => goTo("discover")} />
                        )}
                        {tab === "tracking" && <TrackingTab onOpenManual={() => openManual()} onGoSearch={() => goTo("search")} />}
                        {tab === "discover" && <DiscoverTab onPreview={setPreview} />}
                    </motion.div>
                </AnimatePresence>
            </PageContainer>

            <AddPreviewDialog item={preview} onOpenChange={(open) => !open && setPreview(null)} onShowTracking={showTracking} />
            <ManualAddDialog
                open={manual.open}
                onOpenChange={(open) => setManual((m) => ({ ...m, open }))}
                initialTitle={manual.title}
            />
        </AdderProvider>
    );
}
