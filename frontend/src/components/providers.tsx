"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export function Providers({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 30 * 1000, // 30 secondes
                        retry: 2,
                        refetchOnWindowFocus: false,
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>
            {/* Thème sombre unique : le design « néon » est pensé pour la nuit
                (l'ancien mode clair était cassé sur la plupart des pages). */}
            <NextThemesProvider attribute="class" forcedTheme="dark" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
                {/* reducedMotion="user" : si l'OS demande moins d'animations,
                    framer-motion les coupe automatiquement. */}
                <MotionConfig reducedMotion="user">
                    <TooltipProvider delayDuration={250}>
                        {children}
                        <Toaster
                            position="bottom-right"
                            theme="dark"
                            closeButton
                            richColors
                            offset={20}
                            gap={10}
                            toastOptions={{
                                classNames: {
                                    toast: "!glass-strong !rounded-2xl !border-white/10 !font-sans !shadow-2xl",
                                    title: "!font-semibold",
                                    description: "!text-muted-foreground",
                                    actionButton: "!bg-primary !text-primary-foreground !rounded-lg",
                                },
                            }}
                        />
                    </TooltipProvider>
                </MotionConfig>
            </NextThemesProvider>
        </QueryClientProvider>
    );
}
