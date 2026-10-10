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
 */
import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { RefreshCw, ServerCrash } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { CommandPalette } from "@/components/layout/command-palette";
import { KeyboardShortcuts } from "@/components/layout/keyboard-shortcuts";
import { MiniPlayer } from "@/components/layout/mini-player";
import { SidebarProvider, useSidebar, SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from "@/components/layout/sidebar-context";
import { AuroraBackground } from "@/components/fx/aurora-background";
import { Button } from "@/components/ui/button";
import { isAuthenticated } from "@/lib/api-client";
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
                <div className="flex flex-col items-center gap-3 text-center">
                    <ServerCrash className="h-8 w-8 text-red-400" />
                    <p className="text-lg font-semibold">Backend injoignable</p>
                    <p className="max-w-xs text-sm text-muted-foreground">
                        L&apos;API ArrMada ne répond pas. Vérifie que le conteneur <span className="font-mono text-foreground">arrmada-backend</span> tourne.
                    </p>
                    <Button onClick={() => refetch()} disabled={isFetching} className="mt-2">
                        <RefreshCw className={isFetching ? "animate-spin" : ""} /> Réessayer
                    </Button>
                </div>
            </Splash>
        );
    }

    if (setupLoading || !ready) {
        return (
            <Splash>
                <p className="text-sm text-muted-foreground">Hissez les voiles…</p>
            </Splash>
        );
    }

    return (
        <SidebarProvider>
            <AppContent>{children}</AppContent>
        </SidebarProvider>
    );
}

/** Écran de chargement / erreur de marque (logo pulsant sur fond aurora). */
function Splash({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-6">
            <AuroraBackground intense />
            <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 18 }}
                className="relative"
            >
                <div className="absolute inset-0 -m-8 animate-pulse-glow rounded-full bg-primary/30 blur-3xl" />
                <div className="border-beam relative h-24 w-24 rounded-3xl p-[2px]">
                    <div className="h-full w-full overflow-hidden rounded-[22px]">
                        <Image src="/logo-mark.png" alt="ArrMada" width={96} height={96} priority className="h-full w-full object-cover" />
                    </div>
                </div>
            </motion.div>
            {children}
        </div>
    );
}

/** Contenu une fois authentifié : active le flux temps réel (SSE). */
function AppContent({ children }: { children: React.ReactNode }) {
    useSSE();
    const { collapsed } = useSidebar();
    const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

    return (
        <div className="min-h-screen" style={{ ["--sb-w" as string]: `${sidebarWidth + 24}px` }}>
            <AuroraBackground />
            <Sidebar />
            <MobileNav />
            <CommandPalette />
            <KeyboardShortcuts />
            <MiniPlayer />
            <main className="pb-[calc(6.5rem+env(safe-area-inset-bottom))] transition-[padding] duration-300 ease-smooth lg:pb-8 lg:pl-[var(--sb-w)]">
                {children}
            </main>
        </div>
    );
}
