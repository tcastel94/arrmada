"use client";

/**
 * Coquille applicative (toutes les pages après connexion).
 * ----------------------------------------------------------------
 * Contrôles d'accès :
 *  - setup non fait          → /setup
 *  - pas de jeton            → /login
 *  - backend injoignable     → écran d'erreur avec « Réessayer »
 *    (avant : redirection vers l'assistant d'installation, ce qui
 *    renvoyait un utilisateur DÉJÀ configuré dans le wizard → erreur 409).
 *
 * Mise en page (refonte « Épuré ») :
 *  - ordinateur : barre latérale fixe à gauche, contenu décalé de sa largeur ;
 *  - mobile : barre d'onglets en bas, contenu qui s'arrête au-dessus
 *    (hauteur de la barre + zone de la barre d'accueil de l'iPhone).
 */
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, RefreshCw, ServerCrash } from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { CommandPalette } from "@/components/layout/command-palette";
import { KeyboardShortcuts } from "@/components/layout/keyboard-shortcuts";
import { MiniPlayer } from "@/components/layout/mini-player";
import { SidebarProvider, useSidebar, SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from "@/components/layout/sidebar-context";
import { Button } from "@/components/ui/button";
import { isAuthenticated } from "@/lib/api-client";
import { markNavigation } from "@/lib/nav-history";
import { useSetupStatus } from "@/hooks/use-setup";
import { useSSE } from "@/hooks/use-sse";

export default function AppLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const [ready, setReady] = useState(false);
    const { data: setupStatus, isLoading: setupLoading, isError, refetch, isFetching } = useSetupStatus();

    useEffect(() => {
        if (setupLoading || isError) return;
        if (setupStatus && !setupStatus.is_configured) {
            router.replace("/setup");
            return;
        }
        if (!isAuthenticated()) {
            router.replace("/login");
        } else {
            setReady(true);
        }
    }, [router, setupStatus, setupLoading, isError]);

    if (isError) {
        return (
            <Splash>
                <div className="flex flex-col items-center gap-2 text-center">
                    <ServerCrash className="h-7 w-7 text-destructive" />
                    <p className="text-[17px] font-semibold">Serveur injoignable</p>
                    <p className="max-w-xs text-[14px] text-muted-foreground">
                        L&apos;API ArrMada ne répond pas. Vérifie que le conteneur <span className="font-mono text-foreground">arrmada-backend</span> tourne.
                    </p>
                    <Button onClick={() => refetch()} disabled={isFetching} className="mt-3">
                        <RefreshCw className={isFetching ? "animate-spin" : ""} /> Réessayer
                    </Button>
                </div>
            </Splash>
        );
    }

    if (setupLoading || !ready) {
        return (
            <Splash>
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </Splash>
        );
    }

    return (
        <SidebarProvider>
            <AppContent>{children}</AppContent>
        </SidebarProvider>
    );
}

/** Écran de chargement / erreur : logo sur fond noir, comme le lancement d'une app iOS. */
function Splash({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-6 px-6">
            <motion.div
                initial={{ scale: 0.92, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.35, ease: [0.25, 1, 0.5, 1] }}
                className="h-20 w-20 overflow-hidden rounded-[22px]"
            >
                <BrandIcon title="ArrMada" />
            </motion.div>
            {children}
        </div>
    );
}

/** Contenu une fois authentifié : active le flux temps réel (SSE). */
function AppContent({ children }: { children: React.ReactNode }) {
    useSSE();
    const pathname = usePathname();
    const { collapsed } = useSidebar();
    const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

    // Compte les navigations internes (bouton « ‹ Retour » de la barre du haut).
    useEffect(() => markNavigation(), [pathname]);

    return (
        <div className="min-h-[100dvh]" style={{ ["--sb-w" as string]: `${sidebarWidth}px` }}>
            <Sidebar />
            <MobileNav />
            <CommandPalette />
            <KeyboardShortcuts />
            <MiniPlayer />
            <main className="pb-[calc(var(--tabbar-h)+env(safe-area-inset-bottom)+var(--miniplayer-h,0px)+1rem)] transition-[padding] duration-300 ease-smooth lg:pb-[calc(var(--miniplayer-h,0px)+2.5rem)] lg:pl-[var(--sb-w)]">
                {children}
            </main>
        </div>
    );
}
